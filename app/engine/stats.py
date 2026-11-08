"""Platform and player statistics & leaderboard engine for Ottomate Battleship."""

from __future__ import annotations

from typing import Any
from ottomate_core.db import normalize_email, resolve_user_display_names
from ottomate_core.stats import (
    SCOPE_ALL,
    SCOPE_HUMAN_ONLY,
    StreakTracker,
    calculate_win_rate,
)
from app.engine.bot import is_bot_email


def is_match_human_only(match: dict[str, Any]) -> bool:
    """Returns True if both players in the match are human accounts (no bots)."""
    p1 = match.get("player1_email") or ""
    p2 = match.get("player2_email") or ""
    mode = match.get("mode") or ""
    if mode == "pve":
        return False
    if is_bot_email(p1) or is_bot_email(p2):
        return False
    return True


def compute_leaderboard_and_stats(
    matches: list[dict[str, Any]],
    scope: str = SCOPE_ALL,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Computes sorted leaderboard standings and per-player statistical breakdowns.

    Args:
        matches: List of raw match documents.
        scope: "all" (includes PvE bot games) or "human_only" (strict PvP matches only).

    Returns:
        tuple of (leaderboard_list, player_stats_map)
    """
    # Sort matches chronologically for accurate streak calculation
    chronological_matches = sorted(
        [m for m in matches if m.get("status") == "completed"],
        key=lambda x: x.get("completed_at") or x.get("created_at") or "",
    )

    player_records: dict[str, dict[str, Any]] = {}
    player_outcomes: dict[str, list[bool]] = {}
    winning_shots_counts: dict[str, list[int]] = {}

    def _ensure_player(email: str, name: str | None = None) -> dict[str, Any]:
        norm = normalize_email(email)
        if norm not in player_records:
            player_records[norm] = {
                "email": norm,
                "display_name": name or norm,
                "is_bot": is_bot_email(norm),
                "total_matches": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_shots": 0,
                "hits": 0,
                "misses": 0,
                "hit_pct": 0.0,
                "ships_sunk": 0,
                "ships_lost": 0,
                "flawless_victories": 0,
                "avg_shots_to_win": 0.0,
                "current_win_streak": 0,
                "max_win_streak": 0,
            }
            player_outcomes[norm] = []
            winning_shots_counts[norm] = []
        return player_records[norm]

    for m in chronological_matches:
        if scope == SCOPE_HUMAN_ONLY and not is_match_human_only(m):
            continue

        p1 = m.get("player1_email")
        p2 = m.get("player2_email")
        if not p1 or not p2:
            continue

        # In human_only mode, skip recording bot stats
        if scope == SCOPE_HUMAN_ONLY and (is_bot_email(p1) or is_bot_email(p2)):
            continue

        p1_stats = _ensure_player(p1, m.get("player1_name"))
        p2_stats = _ensure_player(p2, m.get("player2_name"))

        winner = m.get("winner_email")
        p1_won = winner == p1
        p2_won = winner == p2

        p1_stats["total_matches"] += 1
        p2_stats["total_matches"] += 1

        if p1_won:
            p1_stats["wins"] += 1
            p2_stats["losses"] += 1
            player_outcomes[p1].append(True)
            player_outcomes[p2].append(False)
        elif p2_won:
            p2_stats["wins"] += 1
            p1_stats["losses"] += 1
            player_outcomes[p2].append(True)
            player_outcomes[p1].append(False)

        # Count ships lost from board states
        p1_lost = len(m.get("player1_board", {}).get("sunk_ships", []))
        p2_lost = len(m.get("player2_board", {}).get("sunk_ships", []))
        p1_stats["ships_lost"] += p1_lost
        p2_stats["ships_lost"] += p2_lost

        if p1_won and p1_lost == 0:
            p1_stats["flawless_victories"] += 1
        if p2_won and p2_lost == 0:
            p2_stats["flawless_victories"] += 1

        # Process shot history
        p1_match_shots = 0
        p2_match_shots = 0

        for shot in m.get("history", []):
            shooter = normalize_email(shot.get("player_email", ""))
            if shooter == p1:
                p1_match_shots += 1
                p1_stats["total_shots"] += 1
                if shot.get("result") == "hit":
                    p1_stats["hits"] += 1
                else:
                    p1_stats["misses"] += 1
                if shot.get("sunk"):
                    p1_stats["ships_sunk"] += 1
            elif shooter == p2:
                p2_match_shots += 1
                p2_stats["total_shots"] += 1
                if shot.get("result") == "hit":
                    p2_stats["hits"] += 1
                else:
                    p2_stats["misses"] += 1
                if shot.get("sunk"):
                    p2_stats["ships_sunk"] += 1

        if p1_won and p1_match_shots > 0:
            winning_shots_counts[p1].append(p1_match_shots)
        if p2_won and p2_match_shots > 0:
            winning_shots_counts[p2].append(p2_match_shots)

    # Resolve display nicknames for human players
    human_emails = [e for e in player_records if not is_bot_email(e)]
    display_names = resolve_user_display_names(human_emails)

    for email, rec in player_records.items():
        if email in display_names:
            rec["display_name"] = display_names[email]

        # Win rate
        rec["win_rate"] = calculate_win_rate(rec["wins"], rec["total_matches"])

        # Hit accuracy
        if rec["total_shots"] > 0:
            rec["hit_pct"] = round((rec["hits"] / rec["total_shots"]) * 100, 1)

        # Average shots to win
        wins_shots = winning_shots_counts.get(email, [])
        if wins_shots:
            rec["avg_shots_to_win"] = round(sum(wins_shots) / len(wins_shots), 1)

        # Streaks
        outcomes = player_outcomes.get(email, [])
        streak_info = StreakTracker.compute_streak(outcomes)
        rec["current_win_streak"] = streak_info["count"] if streak_info["type"] == "W" else 0
        rec["max_win_streak"] = StreakTracker.compute_best_win_streak(outcomes)

    # Sort leaderboard: Wins desc, Win Rate desc, Hit % desc, Ships Sunk desc
    leaderboard = list(player_records.values())

    if scope == SCOPE_HUMAN_ONLY:
        leaderboard = [r for r in leaderboard if not r["is_bot"]]

    leaderboard.sort(
        key=lambda x: (
            x["wins"],
            x["win_rate"],
            x["hit_pct"],
            x["ships_sunk"],
            -x["losses"],
        ),
        reverse=True,
    )

    # Add rank index
    for idx, r in enumerate(leaderboard, start=1):
        r["rank"] = idx

    return leaderboard, player_records

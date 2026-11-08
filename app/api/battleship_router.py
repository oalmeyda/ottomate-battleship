"""FastAPI router for Ottomate Battleship matches and gameplay."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ottomate_core.auth import User
from ottomate_core.db import (
    database,
    normalize_email,
    resolve_user_display_names,
)
from ottomate_core.deps import (
    can_act_as_proxy,
    get_authenticated_user,
    is_game_admin,
    is_session_admin,
    is_super_admin,
)

from app.config import SERVICE_NAME
from app.engine.bot import (
    BOT_PROFILES,
    decide_bot_shot,
    is_bot_email,
)
from app.engine.domain import (
    BoardState,
    generate_random_fleet,
    validate_fleet_placement,
)
from app.models import (
    BattleshipMatch,
    CreateMatchRequest,
    DeployFleetRequest,
    FireShotRequest,
)

router = APIRouter(prefix="/api", tags=["battleship"])
MATCHES_COLLECTION = "battleship_matches"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_effective_player(user: User, target_email: str | None) -> str:
    """Resolves actor email taking proxy delegation into account."""
    if not target_email:
        return normalize_email(user.email)
    target = normalize_email(target_email)
    actor = normalize_email(user.email)
    if actor == target:
        return target
    if can_act_as_proxy(actor, target) or is_super_admin(user) or is_game_admin(user, SERVICE_NAME):
        return target
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"You are not authorized to act as a proxy for '{target_email}'",
    )


def _get_match_or_404(match_id: str) -> dict[str, Any]:
    db = database()
    doc = db.collection(MATCHES_COLLECTION).document(match_id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match '{match_id}' not found",
        )
    data = doc.to_dict() or {}
    data["id"] = doc.id
    return data


def _save_match(match_data: dict[str, Any]) -> None:
    db = database()
    match_id = match_data["id"]
    match_data["updated_at"] = _now_iso()
    db.collection(MATCHES_COLLECTION).document(match_id).set(match_data)


def _run_bot_turns_if_active(match: dict[str, Any]) -> list[dict[str, Any]]:
    """Executes bot shots sequentially as long as bot hits and game is in progress."""
    bot_logs: list[dict[str, Any]] = []
    turn_player = match.get("turn_player")
    if not turn_player or not is_bot_email(turn_player):
        return bot_logs

    # The bot is shooting at player1
    p1_board_data = match.get("player1_board", {})
    p1_board = BoardState(**p1_board_data)
    difficulty = match.get("bot_difficulty", "medium")

    while match["status"] == "in_progress" and match["turn_player"] == turn_player:
        shot_coord = decide_bot_shot(
            p1_board.shots_received,
            p1_board.sunk_ships,
            difficulty=difficulty,
        )
        shot_res = p1_board.fire_shot(shot_coord)

        log_entry = {
            "turn": match["turn_number"],
            "player_email": turn_player,
            "coordinate": shot_coord,
            "result": shot_res.result,
            "ship_name": shot_res.ship_name,
            "sunk": shot_res.sunk,
            "timestamp": _now_iso(),
        }
        match["turn_number"] += 1
        match["history"].append(log_entry)
        bot_logs.append(log_entry)

        if shot_res.game_over:
            match["status"] = "completed"
            match["winner_email"] = turn_player
            match["winner_name"] = match.get("player2_name", "Bot")
            match["completed_at"] = _now_iso()
            break
        elif shot_res.result == "hit":
            # Bot streak on hit!
            continue
        else:
            # Miss: bot turn ends, passes back to player1
            match["turn_player"] = match["player1_email"]
            break

    match["player1_board"] = p1_board.model_dump()
    return bot_logs


@router.get("/matches")
def list_matches(
    status_filter: str | None = Query(None, alias="status"),
    user: User = Depends(get_authenticated_user),
) -> dict[str, Any]:
    """Lists matches for the current user, open lobby matches, or all matches for admins."""
    db = database()
    user_email = normalize_email(user.email)
    admin = is_super_admin(user) or is_game_admin(user, SERVICE_NAME)

    docs = db.collection(MATCHES_COLLECTION).stream()
    matches: list[dict[str, Any]] = []
    participant_emails: set[str] = set()

    for doc in docs:
        m = doc.to_dict() or {}
        m["id"] = doc.id
        p1 = m.get("player1_email")
        p2 = m.get("player2_email")

        if admin or p1 == user_email or p2 == user_email or (p2 is None and m.get("status") == "setup"):
            if status_filter and m.get("status") != status_filter:
                continue
            matches.append(m)
            if p1:
                participant_emails.add(p1)
            if p2 and not is_bot_email(p2):
                participant_emails.add(p2)

    # Resolve display names
    display_names = resolve_user_display_names(list(participant_emails))
    for m in matches:
        p1 = m.get("player1_email")
        p2 = m.get("player2_email")
        if p1 and not m.get("player1_name"):
            m["player1_name"] = display_names.get(p1, p1)
        if p2 and not m.get("player2_name") and not is_bot_email(p2):
            m["player2_name"] = display_names.get(p2, p2)

    # Sort newest first
    matches.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"matches": matches}


@router.post("/matches", status_code=status.HTTP_201_CREATED)
def create_match(
    req: CreateMatchRequest,
    user: User = Depends(get_authenticated_user),
) -> dict[str, Any]:
    """Creates a new Battleship match against an AI bot or for PvP."""
    p1_email = normalize_email(user.email)
    match_id = f"btl_{uuid.uuid4().hex[:12]}"
    now = _now_iso()

    display_names = resolve_user_display_names([p1_email])
    p1_name = display_names.get(p1_email, p1_email)

    match = BattleshipMatch(
        id=match_id,
        title=req.title.strip() or "Battleship Duel",
        mode=req.mode,
        bot_difficulty=req.bot_difficulty if req.mode == "pve" else None,
        player1_email=p1_email,
        player1_name=p1_name,
        player1_ready=False,
        player1_board={},
        status="setup",
        created_by=p1_email,
        created_by_name=p1_name,
        admins=[p1_email],
        created_at=now,
        updated_at=now,
    )

    if req.mode == "pve":
        bot_info = BOT_PROFILES.get(req.bot_difficulty, BOT_PROFILES["medium"])
        bot_email = bot_info["email"]
        bot_name = bot_info["name"]

        # Deploy bot fleet immediately
        bot_fleet = generate_random_fleet()
        bot_coords_map = validate_fleet_placement(bot_fleet)
        bot_board = BoardState(player_email=bot_email, ships=bot_coords_map)

        match.player2_email = bot_email
        match.player2_name = bot_name
        match.player2_ready = True
        match.player2_board = bot_board.model_dump()
    elif req.opponent_email:
        opp_email = normalize_email(req.opponent_email)
        opp_names = resolve_user_display_names([opp_email])
        match.player2_email = opp_email
        match.player2_name = opp_names.get(opp_email, opp_email)

    match_dict = match.model_dump()
    _save_match(match_dict)
    return {"match": match_dict}


@router.get("/matches/{match_id}")
def get_match(
    match_id: str,
    user: User = Depends(get_authenticated_user),
) -> dict[str, Any]:
    """Retrieves the match state with masked fog-of-war radar for the requesting player."""
    match = _get_match_or_404(match_id)
    user_email = normalize_email(user.email)

    p1 = match.get("player1_email")
    p2 = match.get("player2_email")
    is_admin = (
        is_super_admin(user)
        or is_game_admin(user, SERVICE_NAME)
        or is_session_admin(user, match, SERVICE_NAME)
    )

    # Check participation or proxy
    is_p1 = (p1 == user_email) or can_act_as_proxy(user_email, p1 or "")
    is_p2 = (p2 == user_email) or can_act_as_proxy(user_email, p2 or "")

    if not (is_p1 or is_p2 or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant or authorized observer in this match",
        )

    # Build fog-of-war response
    p1_board_raw = match.get("player1_board") or {}
    p2_board_raw = match.get("player2_board") or {}
    p1_board = BoardState(**p1_board_raw) if p1_board_raw else None
    p2_board = BoardState(**p2_board_raw) if p2_board_raw else None

    is_completed = match.get("status") == "completed"

    if is_p1 and not is_p2:
        my_role = "player1"
        my_board = p1_board.reveal_full() if p1_board else {}
        radar_board = (
            (p2_board.reveal_full() if is_completed else p2_board.mask_for_opponent())
            if p2_board
            else {}
        )
    elif is_p2 and not is_p1:
        my_role = "player2"
        my_board = p2_board.reveal_full() if p2_board else {}
        radar_board = (
            (p1_board.reveal_full() if is_completed else p1_board.mask_for_opponent())
            if p1_board
            else {}
        )
    else:
        # Non-playing Admin or spectator: full visibility
        my_role = "admin" if is_admin else "player1"
        my_board = p1_board.reveal_full() if p1_board else {}
        radar_board = p2_board.reveal_full() if p2_board else {}

    turn_player = match.get("turn_player")
    is_my_turn = (
        match.get("status") == "in_progress"
        and (
            (my_role == "player1" and turn_player == p1)
            or (my_role == "player2" and turn_player == p2)
            or (is_admin and turn_player is not None)
        )
    )

    return {
        "id": match["id"],
        "title": match.get("title", "Battleship Duel"),
        "status": match.get("status", "setup"),
        "mode": match.get("mode", "pve"),
        "bot_difficulty": match.get("bot_difficulty"),
        "my_role": my_role,
        "is_my_turn": is_my_turn,
        "turn_player": turn_player,
        "turn_number": match.get("turn_number", 1),
        "player1": {
            "email": p1,
            "name": match.get("player1_name", p1),
            "ready": match.get("player1_ready", False),
        },
        "player2": {
            "email": p2,
            "name": match.get("player2_name", p2 or "Waiting for opponent..."),
            "ready": match.get("player2_ready", False),
        },
        "my_board": my_board,
        "radar_board": radar_board,
        "history": match.get("history", []),
        "winner_email": match.get("winner_email"),
        "winner_name": match.get("winner_name"),
        "completed_at": match.get("completed_at"),
    }


@router.post("/matches/{match_id}/join")
def join_match(
    match_id: str,
    user: User = Depends(get_authenticated_user),
) -> dict[str, Any]:
    """Joins an open PvP match."""
    match = _get_match_or_404(match_id)
    if match.get("status") != "setup":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Match is not open for joining",
        )
    if match.get("player2_email") is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Match already has two players",
        )

    user_email = normalize_email(user.email)
    if user_email == match.get("player1_email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot join your own match as player 2",
        )

    display_names = resolve_user_display_names([user_email])
    p2_name = display_names.get(user_email, user_email)

    match["player2_email"] = user_email
    match["player2_name"] = p2_name
    _save_match(match)
    return {"message": "Joined match successfully", "match": match}


@router.post("/matches/{match_id}/deploy")
def deploy_fleet(
    match_id: str,
    req: DeployFleetRequest,
    user: User = Depends(get_authenticated_user),
) -> dict[str, Any]:
    """Submits ship placements for the player."""
    match = _get_match_or_404(match_id)
    if match.get("status") != "setup":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fleet can only be deployed during setup phase",
        )

    effective_player = _resolve_effective_player(user, req.target_email)
    p1 = match.get("player1_email")
    p2 = match.get("player2_email")

    if effective_player == p1:
        role = "player1"
    elif effective_player == p2:
        role = "player2"
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a player in this match",
        )

    try:
        coords_map = validate_fleet_placement(req.ships)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    board = BoardState(player_email=effective_player, ships=coords_map)

    if role == "player1":
        match["player1_board"] = board.model_dump()
        match["player1_ready"] = True
    else:
        match["player2_board"] = board.model_dump()
        match["player2_ready"] = True

    # If both players are now ready, start the battle!
    if match.get("player1_ready") and match.get("player2_ready"):
        match["status"] = "in_progress"
        match["turn_player"] = match["player1_email"]  # Player 1 opens fire

    _save_match(match)
    return {
        "message": "Fleet deployed successfully",
        "ready": True,
        "status": match["status"],
        "turn_player": match.get("turn_player"),
    }


@router.post("/matches/{match_id}/fire")
def fire_shot(
    match_id: str,
    req: FireShotRequest,
    user: User = Depends(get_authenticated_user),
) -> dict[str, Any]:
    """Fires a shot at the opponent's waters."""
    match = _get_match_or_404(match_id)
    if match.get("status") != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Match is not in progress (current status: {match.get('status')})",
        )

    effective_player = _resolve_effective_player(user, req.target_email)
    turn_player = match.get("turn_player")

    if effective_player != turn_player and not (
        is_super_admin(user) or is_game_admin(user, SERVICE_NAME)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"It is not your turn. Current turn: {turn_player}",
        )

    p1 = match.get("player1_email")
    p2 = match.get("player2_email")

    if effective_player == p1:
        target_board_key = "player2_board"
        next_player = p2
    elif effective_player == p2:
        target_board_key = "player1_board"
        next_player = p1
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this match",
        )

    target_board_raw = match.get(target_board_key) or {}
    target_board = BoardState(**target_board_raw)

    try:
        shot_res = target_board.fire_shot(req.coordinate)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    match[target_board_key] = target_board.model_dump()

    log_entry = {
        "turn": match["turn_number"],
        "player_email": effective_player,
        "coordinate": shot_res.coordinate,
        "result": shot_res.result,
        "ship_name": shot_res.ship_name,
        "sunk": shot_res.sunk,
        "timestamp": _now_iso(),
    }
    match["turn_number"] += 1
    match["history"].append(log_entry)

    # Turn logic & Victory
    if shot_res.game_over:
        match["status"] = "completed"
        match["winner_email"] = effective_player
        match["winner_name"] = (
            match.get("player1_name") if effective_player == p1 else match.get("player2_name")
        )
        match["completed_at"] = _now_iso()
    elif shot_res.result == "hit":
        # STREAK ON HIT: Keep current player active!
        pass
    else:
        # MISS: Switch turn to opponent
        match["turn_player"] = next_player

        # If opponent is a bot, execute bot turns until miss or victory!
        if match["turn_player"] and is_bot_email(match["turn_player"]):
            _run_bot_turns_if_active(match)

    _save_match(match)

    return {
        "shot": shot_res.model_dump(),
        "turn_player": match.get("turn_player"),
        "status": match["status"],
        "winner_email": match.get("winner_email"),
        "history": match.get("history", []),
    }


@router.post("/matches/{match_id}/surrender")
def surrender_match(
    match_id: str,
    user: User = Depends(get_authenticated_user),
) -> dict[str, Any]:
    """Forfeits the match, awarding victory to the opponent."""
    match = _get_match_or_404(match_id)
    if match.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Match is already completed",
        )

    user_email = normalize_email(user.email)
    p1 = match.get("player1_email")
    p2 = match.get("player2_email")

    if user_email == p1:
        winner = p2
        winner_name = match.get("player2_name")
    elif user_email == p2:
        winner = p1
        winner_name = match.get("player1_name")
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this match",
        )

    match["status"] = "completed"
    match["winner_email"] = winner
    match["winner_name"] = winner_name
    match["completed_at"] = _now_iso()
    _save_match(match)
    return {"message": "Forfeited match", "winner": winner}


@router.delete("/matches/{match_id}")
def delete_match(
    match_id: str,
    user: User = Depends(get_authenticated_user),
) -> dict[str, Any]:
    """Deletes a match. Allowed for match creator or admins."""
    match = _get_match_or_404(match_id)
    if not (
        is_super_admin(user)
        or is_game_admin(user, SERVICE_NAME)
        or is_session_admin(user, match, SERVICE_NAME)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this match",
        )

    db = database()
    db.collection(MATCHES_COLLECTION).document(match_id).delete()
    return {"message": f"Match '{match_id}' deleted successfully"}


@router.get("/me/stats")
def get_user_stats(
    user: User = Depends(get_authenticated_user),
) -> dict[str, Any]:
    """Computes personal win/loss and shot accuracy statistics for the user."""
    db = database()
    user_email = normalize_email(user.email)

    docs = db.collection(MATCHES_COLLECTION).stream()
    total_matches = 0
    wins = 0
    losses = 0
    total_shots = 0
    hits = 0

    for doc in docs:
        m = doc.to_dict() or {}
        p1 = m.get("player1_email")
        p2 = m.get("player2_email")

        if p1 != user_email and p2 != user_email:
            continue

        if m.get("status") == "completed":
            total_matches += 1
            if m.get("winner_email") == user_email:
                wins += 1
            else:
                losses += 1

        for shot in m.get("history", []):
            if shot.get("player_email") == user_email:
                total_shots += 1
                if shot.get("result") == "hit":
                    hits += 1

    accuracy = round((hits / total_shots) * 100, 1) if total_shots > 0 else 0.0

    return {
        "email": user_email,
        "total_matches": total_matches,
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / total_matches) * 100, 1) if total_matches > 0 else 0.0,
        "total_shots": total_shots,
        "hits": hits,
        "accuracy_pct": accuracy,
    }

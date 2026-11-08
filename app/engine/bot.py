"""NPC Bot AI for Ottomate Battleship."""

from __future__ import annotations

import random
from typing import Any
from app.engine.domain import (
    GRID_SIZE,
    FLEET_SPECS,
    format_coordinate,
    parse_coordinate,
)

BOT_PROFILES = {
    "easy": {
        "email": "bot:cadet_clueless@ottomate.games",
        "name": "Cadet Clueless",
        "description": "Fires randomly across the water.",
    },
    "medium": {
        "email": "bot:captain_cannon@ottomate.games",
        "name": "Captain Cannon",
        "description": "Uses parity hunt and targets adjacent cells upon hitting.",
    },
    "hard": {
        "email": "bot:admiral_otto@ottomate.games",
        "name": "Admiral Otto",
        "description": "Calculates probability density heatmaps to corner your fleet.",
    },
}


def is_bot_email(email: str) -> bool:
    return email.startswith("bot:") or email.endswith("@ottomate.internal")


def get_all_coordinates() -> list[str]:
    coords: list[str] = []
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            coords.append(format_coordinate(r, c))
    return coords


def get_unfired_coordinates(shots_received: dict[str, dict[str, Any]]) -> list[str]:
    all_coords = get_all_coordinates()
    return [c for c in all_coords if c not in shots_received]


def get_orthogonal_neighbors(row: int, col: int) -> list[tuple[int, int]]:
    neighbors: list[tuple[int, int]] = []
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = row + dr, col + dc
        if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
            neighbors.append((nr, nc))
    return neighbors


def decide_bot_shot(
    shots_received: dict[str, dict[str, Any]],
    sunk_ships: list[str],
    difficulty: str = "medium",
) -> str:
    """Decides the next coordinate for the bot to fire at based on difficulty."""
    unfired = get_unfired_coordinates(shots_received)
    if not unfired:
        raise ValueError("No valid coordinates remaining to fire upon.")

    norm_diff = difficulty.strip().lower()
    if norm_diff == "easy":
        return random.choice(unfired)

    # Find hits that do NOT belong to already sunk ships
    # For sunk ships, their hit cells are considered resolved.
    unsunk_hits: list[tuple[int, int]] = []
    for coord, shot in shots_received.items():
        if shot.get("result") == "hit":
            ship_id = shot.get("ship_id")
            if ship_id and ship_id in sunk_ships:
                continue
            r, c = parse_coordinate(coord)
            unsunk_hits.append((r, c))

    # --- TARGET MODE ---
    # If there are active unsunk hits, pursue them!
    if unsunk_hits:
        # If there are 2 or more unsunk hits, check if they form a line
        if len(unsunk_hits) >= 2:
            rows = {r for r, _ in unsunk_hits}
            cols = {c for _, c in unsunk_hits}

            # Horizontal line: same row
            if len(rows) == 1:
                r = list(rows)[0]
                min_c = min(c for _, c in unsunk_hits)
                max_c = max(c for _, c in unsunk_hits)
                candidates: list[tuple[int, int]] = []
                if min_c > 0:
                    candidates.append((r, min_c - 1))
                if max_c < GRID_SIZE - 1:
                    candidates.append((r, max_c + 1))

                valid_line_shots = [
                    format_coordinate(cr, cc)
                    for cr, cc in candidates
                    if format_coordinate(cr, cc) in unfired
                ]
                if valid_line_shots:
                    return random.choice(valid_line_shots)

            # Vertical line: same column
            elif len(cols) == 1:
                c = list(cols)[0]
                min_r = min(r for r, _ in unsunk_hits)
                max_r = max(r for r, _ in unsunk_hits)
                candidates = []
                if min_r > 0:
                    candidates.append((min_r - 1, c))
                if max_r < GRID_SIZE - 1:
                    candidates.append((max_r + 1, c))

                valid_line_shots = [
                    format_coordinate(cr, cc)
                    for cr, cc in candidates
                    if format_coordinate(cr, cc) in unfired
                ]
                if valid_line_shots:
                    return random.choice(valid_line_shots)

        # Fallback target mode: probe adjacent orthogonal cells of any unsunk hit
        target_candidates: list[str] = []
        for r, c in unsunk_hits:
            for nr, nc in get_orthogonal_neighbors(r, c):
                n_coord = format_coordinate(nr, nc)
                if n_coord in unfired and n_coord not in target_candidates:
                    target_candidates.append(n_coord)

        if target_candidates:
            return random.choice(target_candidates)

    # --- HUNT MODE ---
    if norm_diff == "hard":
        # Probability Density Heatmap
        # Determine remaining unsunk ships and their lengths
        remaining_ships = [
            spec for ship_id, spec in FLEET_SPECS.items()
            if ship_id not in sunk_ships
        ]
        if not remaining_ships:
            return random.choice(unfired)

        heatmap: dict[tuple[int, int], int] = {
            (r, c): 0 for r in range(GRID_SIZE) for c in range(GRID_SIZE)
        }

        unfired_set = set(unfired)

        for spec in remaining_ships:
            size = spec["size"]

            # Horizontal checks
            for r in range(GRID_SIZE):
                for c in range(GRID_SIZE - size + 1):
                    coords = [format_coordinate(r, c + i) for i in range(size)]
                    # Can fit if none of the coords are misses or sunk ship cells
                    can_fit = True
                    for coord in coords:
                        shot = shots_received.get(coord)
                        if shot and (shot.get("result") == "miss" or (shot.get("ship_id") in sunk_ships)):
                            can_fit = False
                            break
                    if can_fit:
                        for i in range(size):
                            if coords[i] in unfired_set:
                                heatmap[(r, c + i)] += 1

            # Vertical checks
            for r in range(GRID_SIZE - size + 1):
                for c in range(GRID_SIZE):
                    coords = [format_coordinate(r + i, c) for i in range(size)]
                    can_fit = True
                    for coord in coords:
                        shot = shots_received.get(coord)
                        if shot and (shot.get("result") == "miss" or (shot.get("ship_id") in sunk_ships)):
                            can_fit = False
                            break
                    if can_fit:
                        for i in range(size):
                            if coords[i] in unfired_set:
                                heatmap[(r + i, c)] += 1

        # Pick the coordinate with the maximum score from unfired
        best_coord = unfired[0]
        max_score = -1
        for coord in unfired:
            r, c = parse_coordinate(coord)
            score = heatmap[(r, c)]
            if score > max_score:
                max_score = score
                best_coord = coord

        return best_coord

    # Medium Hunt Mode: Parity (checkerboard)
    parity_unfired = [
        c for c in unfired
        if (parse_coordinate(c)[0] + parse_coordinate(c)[1]) % 2 == 0
    ]
    if parity_unfired:
        return random.choice(parity_unfired)

    return random.choice(unfired)

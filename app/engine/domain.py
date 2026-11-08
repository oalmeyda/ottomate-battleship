"""Core domain rules and grid engine for Ottomate Battleship."""

from __future__ import annotations

import random
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

GRID_SIZE = 10
COLUMNS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
ROWS = [str(i) for i in range(1, 11)]

FLEET_SPECS: dict[str, dict[str, Any]] = {
    "carrier": {"id": "carrier", "name": "Carrier", "size": 5, "symbol": "C"},
    "battleship": {"id": "battleship", "name": "Battleship", "size": 4, "symbol": "B"},
    "cruiser": {"id": "cruiser", "name": "Cruiser", "size": 3, "symbol": "R"},
    "submarine": {"id": "submarine", "name": "Submarine", "size": 3, "symbol": "S"},
    "destroyer": {"id": "destroyer", "name": "Destroyer", "size": 2, "symbol": "D"},
}
TOTAL_FLEET_CELLS = sum(spec["size"] for spec in FLEET_SPECS.values())  # 17


def parse_coordinate(coord: str) -> tuple[int, int]:
    """Parses standard coordinate string (e.g. 'A1', 'J10', 'B5') into (row, col) 0-indexed indices.

    Raises ValueError if invalid.
    """
    if not isinstance(coord, str):
        raise ValueError("Coordinate must be a string")
    trimmed = coord.strip().upper()
    if len(trimmed) < 2 or len(trimmed) > 3:
        raise ValueError(f"Invalid coordinate format: {coord}")

    col_char = trimmed[0]
    row_part = trimmed[1:]

    if col_char not in COLUMNS:
        raise ValueError(f"Invalid column '{col_char}' in coordinate '{coord}'. Must be A-J.")

    try:
        row_num = int(row_part)
    except ValueError as exc:
        raise ValueError(f"Invalid row number '{row_part}' in coordinate '{coord}'") from exc

    if row_num < 1 or row_num > 10:
        raise ValueError(f"Row number must be between 1 and 10, got {row_num}")

    row_idx = row_num - 1
    col_idx = COLUMNS.index(col_char)
    return row_idx, col_idx


def format_coordinate(row: int, col: int) -> str:
    """Formats (row, col) 0-indexed indices into standard coordinate string (e.g. (0, 0) -> 'A1')."""
    if not (0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE):
        raise ValueError(f"Coordinates out of bounds: row={row}, col={col}")
    return f"{COLUMNS[col]}{row + 1}"


class ShipPlacement(BaseModel):
    """Specification for placing a single ship on the grid."""

    ship_id: str
    row: int = Field(ge=0, lt=GRID_SIZE)
    col: int = Field(ge=0, lt=GRID_SIZE)
    orientation: Literal["horizontal", "vertical"]

    @model_validator(mode="after")
    def validate_ship_id(self) -> ShipPlacement:
        norm_id = self.ship_id.strip().lower()
        if norm_id not in FLEET_SPECS:
            raise ValueError(f"Unknown ship_id: '{self.ship_id}'. Valid ships: {list(FLEET_SPECS.keys())}")
        self.ship_id = norm_id
        return self

    def occupied_coordinates(self) -> list[str]:
        """Returns the list of coordinates occupied by this ship (e.g. ['A1', 'A2', ...])."""
        size = FLEET_SPECS[self.ship_id]["size"]
        coords: list[str] = []
        for i in range(size):
            r = self.row + (i if self.orientation == "vertical" else 0)
            c = self.col + (i if self.orientation == "horizontal" else 0)
            if not (0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE):
                raise ValueError(
                    f"Ship '{self.ship_id}' with orientation '{self.orientation}' "
                    f"at ({self.row}, {self.col}) extends outside the 10x10 board at ({r}, {c})."
                )
            coords.append(format_coordinate(r, c))
        return coords


def validate_fleet_placement(placements: list[ShipPlacement | dict[str, Any]]) -> dict[str, list[str]]:
    """Validates that a full fleet of 5 ships is correctly placed without overlap or boundaries issues.

    Returns a dict mapping ship_id to its list of occupied coordinate strings.
    """
    if len(placements) != len(FLEET_SPECS):
        raise ValueError(f"Fleet must have exactly {len(FLEET_SPECS)} ships, got {len(placements)}")

    parsed_placements: list[ShipPlacement] = []
    for p in placements:
        if isinstance(p, dict):
            parsed_placements.append(ShipPlacement(**p))
        else:
            parsed_placements.append(p)

    seen_ships: set[str] = set()
    occupied_cells: dict[str, str] = {}  # coord -> ship_id
    ship_coordinates: dict[str, list[str]] = {}

    for p in parsed_placements:
        if p.ship_id in seen_ships:
            raise ValueError(f"Duplicate ship placed: '{p.ship_id}'")
        seen_ships.add(p.ship_id)

        coords = p.occupied_coordinates()
        for c in coords:
            if c in occupied_cells:
                prev_ship = occupied_cells[c]
                raise ValueError(f"Ship '{p.ship_id}' overlaps with '{prev_ship}' at coordinate '{c}'.")
            occupied_cells[c] = p.ship_id

        ship_coordinates[p.ship_id] = coords

    missing = set(FLEET_SPECS.keys()) - seen_ships
    if missing:
        raise ValueError(f"Missing required ships in fleet placement: {missing}")

    return ship_coordinates


def generate_random_fleet() -> list[dict[str, Any]]:
    """Generates a random valid non-overlapping fleet placement for all 5 ships."""
    placements: list[dict[str, Any]] = []
    occupied: set[tuple[int, int]] = set()

    for ship_id, spec in FLEET_SPECS.items():
        size = spec["size"]
        placed = False
        attempts = 0
        while not placed and attempts < 1000:
            attempts += 1
            orientation = random.choice(["horizontal", "vertical"])
            if orientation == "horizontal":
                row = random.randint(0, GRID_SIZE - 1)
                col = random.randint(0, GRID_SIZE - size)
                cells = [(row, col + i) for i in range(size)]
            else:
                row = random.randint(0, GRID_SIZE - size)
                col = random.randint(0, GRID_SIZE - 1)
                cells = [(row + i, col) for i in range(size)]

            if any(cell in occupied for cell in cells):
                continue

            for cell in cells:
                occupied.add(cell)

            placements.append({
                "ship_id": ship_id,
                "row": row,
                "col": col,
                "orientation": orientation,
            })
            placed = True

        if not placed:
            # Retry entire generation if unlucky
            return generate_random_fleet()

    return placements


class ShotResult(BaseModel):
    """Outcome of firing at a coordinate."""

    coordinate: str
    result: Literal["hit", "miss"]
    ship_id: str | None = None
    ship_name: str | None = None
    sunk: bool = False
    game_over: bool = False
    turn_continues: bool = False  # Streak on hit


class BoardState(BaseModel):
    """The authoritative server-side state of a player's waters."""

    player_email: str
    ships: dict[str, list[str]] = Field(default_factory=dict)  # ship_id -> list of coord strings
    shots_received: dict[str, dict[str, Any]] = Field(default_factory=dict)  # coord -> {"result": "hit"|"miss", "ship_id": str|None}
    sunk_ships: list[str] = Field(default_factory=list)

    @property
    def is_fleet_sunk(self) -> bool:
        return len(self.sunk_ships) == len(FLEET_SPECS)

    def fire_shot(self, coord: str) -> ShotResult:
        """Processes an incoming shot at `coord`.

        Raises ValueError if coordinate is invalid or already fired upon.
        """
        r, c = parse_coordinate(coord)
        normalized_coord = format_coordinate(r, c)

        if normalized_coord in self.shots_received:
            raise ValueError(f"Coordinate '{normalized_coord}' has already been fired upon.")

        # Check if shot hit any ship
        hit_ship_id: str | None = None
        for ship_id, cells in self.ships.items():
            if normalized_coord in cells:
                hit_ship_id = ship_id
                break

        if hit_ship_id is not None:
            # Hit!
            self.shots_received[normalized_coord] = {
                "result": "hit",
                "ship_id": hit_ship_id,
            }
            # Check if all cells of hit_ship_id are now hit
            ship_cells = self.ships[hit_ship_id]
            is_sunk = all(cell in self.shots_received for cell in ship_cells)
            if is_sunk and hit_ship_id not in self.sunk_ships:
                self.sunk_ships.append(hit_ship_id)

            game_over = self.is_fleet_sunk
            return ShotResult(
                coordinate=normalized_coord,
                result="hit",
                ship_id=hit_ship_id,
                ship_name=FLEET_SPECS[hit_ship_id]["name"],
                sunk=is_sunk,
                game_over=game_over,
                turn_continues=not game_over,  # streak on hit unless match ended
            )
        else:
            # Miss!
            self.shots_received[normalized_coord] = {
                "result": "miss",
                "ship_id": None,
            }
            return ShotResult(
                coordinate=normalized_coord,
                result="miss",
                turn_continues=False,
            )

    def mask_for_opponent(self) -> dict[str, Any]:
        """Returns the masked 'Radar' view for the opponent.

        Strict Anti-Cheating: Un-hit ship locations are NEVER revealed.
        Only fired shots (hits/misses) and sunk ship designations are visible.
        """
        # Collect sunk ship coordinates so opponent radar can highlight fully sunk ships
        sunk_ships_coords: dict[str, list[str]] = {}
        for ship_id in self.sunk_ships:
            sunk_ships_coords[ship_id] = self.ships.get(ship_id, [])

        return {
            "player_email": self.player_email,
            "shots_received": self.shots_received,
            "sunk_ships": self.sunk_ships,
            "sunk_ships_coords": sunk_ships_coords,
            "is_fleet_sunk": self.is_fleet_sunk,
        }

    def reveal_full(self) -> dict[str, Any]:
        """Returns the full unmasked board view (for the owner or match admin)."""
        return {
            "player_email": self.player_email,
            "ships": self.ships,
            "shots_received": self.shots_received,
            "sunk_ships": self.sunk_ships,
            "is_fleet_sunk": self.is_fleet_sunk,
        }

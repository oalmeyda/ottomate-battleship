"""Data and API models for Ottomate Battleship."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field
from ottomate_core.models import BaseSessionObject
from app.engine.domain import ShipPlacement


class CreateMatchRequest(BaseModel):
    title: str = "Battleship Duel"
    mode: Literal["pvp", "pve"] = "pve"
    bot_difficulty: Literal["easy", "medium", "hard"] = "medium"
    opponent_email: str | None = None


class DeployFleetRequest(BaseModel):
    ships: list[ShipPlacement]
    target_email: str | None = None  # For proxy delegation


class FireShotRequest(BaseModel):
    coordinate: str
    target_email: str | None = None  # For proxy delegation


class ShotLogEntry(BaseModel):
    turn: int
    player_email: str
    coordinate: str
    result: Literal["hit", "miss"]
    ship_name: str | None = None
    sunk: bool = False
    timestamp: str | None = None


class BattleshipMatch(BaseSessionObject):
    """Full database representation of a Battleship match."""

    mode: Literal["pvp", "pve"] = "pve"
    bot_difficulty: Literal["easy", "medium", "hard"] | None = "medium"

    player1_email: str
    player1_name: str | None = None
    player1_ready: bool = False
    player1_board: dict[str, Any] = Field(default_factory=dict)

    player2_email: str | None = None
    player2_name: str | None = None
    player2_ready: bool = False
    player2_board: dict[str, Any] = Field(default_factory=dict)

    turn_player: str | None = None
    turn_number: int = 1
    history: list[dict[str, Any]] = Field(default_factory=list)

    winner_email: str | None = None
    winner_name: str | None = None
    completed_at: str | None = None

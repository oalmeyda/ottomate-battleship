"""Configuration and environment settings for Ottomate Battleship."""

from __future__ import annotations

import os
from pathlib import Path

from ottomate_core.config import configure_service

VERSION = "0.1.1"
SERVICE_NAME = "ottomate-battleship"
APP_TITLE = "Ottomate Battleship"

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

FIRESTORE_DATABASE = os.environ.get("FIRESTORE_DATABASE", "battleship")

SERVICE_CARD_METADATA = {
    "service_id": "battleship",
    "title": "Ottomate Battleship",
    "category": "challenges",
    "category_label": "Tactical Strategy",
    "tagline": "Classic 1v1 Naval Strategy & Artillery Duels",
    "url": "https://ottomate-battleship.web.app",
    "icon": "⚓",
    "description": "Classic 1v1 turn-based naval battle game. Deploy your 5 warships across a 10x10 tactical ocean grid, fire artillery strikes with 'streak on hit' rules, and sink the enemy fleet in PvP or against AI commanders.",
    "tags": ["1v1 Duel", "AI Commanders", "Tactical Radar", "Streak on Hit"],
    "highlight": "New",
    "color": "#0284c7",
    "launched_at": "2026-11-08",
}

# Register service identity and catalog metadata with ottomate-core
configure_service(SERVICE_NAME, FIRESTORE_DATABASE, metadata=SERVICE_CARD_METADATA)


def dev_mode_enabled() -> bool:
    return os.getenv("DEV_MODE", "0").lower() in ("1", "true", "yes")


def google_client_id() -> str:
    return os.getenv(
        "GOOGLE_CLIENT_ID",
        "579098179038-qpe2ofekqke3apb5g6u3jm8o377uhfam.apps.googleusercontent.com",
    )


def organizer_emails() -> list[str]:
    raw = os.getenv("ORGANIZER_EMAILS", "admin@example.com")
    return [e.strip().lower() for e in raw.split(",") if e.strip()]


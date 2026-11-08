"""Configuration and environment settings for Ottomate Battleship."""

from __future__ import annotations

import os
from pathlib import Path

VERSION = "0.1.0"
SERVICE_NAME = "battleship"
APP_TITLE = "Ottomate Battleship"

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


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

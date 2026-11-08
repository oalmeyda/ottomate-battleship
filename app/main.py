"""FastAPI entry point for Ottomate Battleship."""

from __future__ import annotations

from ottomate_core.api import create_ottomate_app

from app.api.battleship_router import router as battleship_router
from app.config import APP_TITLE, SERVICE_NAME, STATIC_DIR, VERSION

app = create_ottomate_app(
    title=APP_TITLE,
    description="Ottomate Battleship: Classic 1v1 Naval Strategy Game",
    version=VERSION,
    service_name=SERVICE_NAME,
    static_dir=STATIC_DIR,
    routers=[battleship_router],
)


from pathlib import Path
from ottomate_core.testing import verify_service_version_consistency
from app.config import VERSION
from app.main import app

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_service_version_consistency():
    verify_service_version_consistency(
        REPO_ROOT,
        VERSION,
        app=app,
        index_file=REPO_ROOT / "app" / "static" / "index.html",
    )

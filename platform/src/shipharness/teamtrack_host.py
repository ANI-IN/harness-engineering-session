"""Run the bundled TeamTrack base app on the host (`shipharness up`). Trusted base code only;
agent-built code always runs in a container."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from shipharness.config.prices import REPO_ROOT
from shipharness.layout import APP_DIR

TEAMTRACK_DIR = REPO_ROOT / APP_DIR


def _ensure_importable() -> None:
    if str(TEAMTRACK_DIR) not in sys.path:
        sys.path.insert(0, str(TEAMTRACK_DIR))


def database_url(db_path: Path) -> str:
    return f"sqlite:///{Path(db_path).resolve().as_posix()}"


def prepare_database(db_path: Path) -> None:
    """`alembic upgrade head` on the file, then insert the Acme/Globex demo data if empty."""
    from alembic import command
    from alembic.config import Config

    _ensure_importable()
    url = database_url(db_path)
    config = Config(str(TEAMTRACK_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(TEAMTRACK_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    session_module = importlib.import_module("app.db.session")
    seed_module = importlib.import_module("app.seed")
    engine = session_module.make_engine(url)
    with session_module.make_session_factory(engine)() as session:
        seed_module.seed(session)
    engine.dispose()


def serve(db_path: Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    _ensure_importable()
    prepare_database(db_path)
    os.environ["TEAMTRACK_DATABASE_URL"] = database_url(db_path)
    os.environ.setdefault("TEAMTRACK_LOG_REQUESTS", "true")
    uvicorn.run(
        "app.main:create_app", factory=True, host=host, port=port, app_dir=str(TEAMTRACK_DIR)
    )

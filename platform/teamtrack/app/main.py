"""Application factory: `uvicorn app.main:create_app --factory`."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import audit, auth, health, issues, legacy_v1, members, projects, users, watchers
from app.api.errors import install_error_handlers
from app.api.middleware import RequestIdMiddleware
from app.db.base import Base
from app.db.session import make_engine, make_session_factory
from app.seed import seed
from app.settings import TeamTrackSettings
from app.web import routes as board


def create_app(settings: TeamTrackSettings | None = None) -> FastAPI:
    settings = settings or TeamTrackSettings()
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    if settings.create_schema:
        Base.metadata.create_all(engine)
    if settings.seed:
        with session_factory() as session:
            seed(session)

    app = FastAPI(title="TeamTrack", version="1.0.0", description="Multi-tenant issue tracker.")
    app.state.session_factory = session_factory
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    for module in (auth, users, projects, members, issues, audit, health, legacy_v1, watchers):
        app.include_router(module.router)
    app.include_router(board.router)
    app.mount("/board/static", StaticFiles(directory=board.STATIC_DIR), name="board-static")
    return app

"""TeamTrack settings (environment variables prefixed TEAMTRACK_)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class TeamTrackSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEAMTRACK_", extra="ignore")

    database_url: str = "sqlite:///./teamtrack.db"
    create_schema: bool = (
        False  # tests only; real databases are created with `alembic upgrade head`
    )
    seed: bool = False  # insert the Acme and Globex demo data if the database is empty
    log_json: bool = False
    log_requests: bool = False  # one line per request; shipharness up turns it on

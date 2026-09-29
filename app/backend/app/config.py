"""Runtime configuration.

Database URL comes from the environment so the same code can run against
PostgreSQL in production and SQLite for isolated unit checks.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PUMPING_", env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg2://pumpapp:pumpapp_dev@127.0.0.1:5432/pumpingdb"
    )
    # Aquifer validity ranges used for plausibility diagnostics (not as fit bounds).
    storativity_plausible_min: float = 1.0e-6
    storativity_plausible_max: float = 1.0e-3
    # Time/drawdown sanity gates.
    min_points_for_fit: int = 4


settings = Settings()

"""SQLAlchemy engine/session and ORM models.

Primary target is PostgreSQL; JSON columns map to JSONB there.  The same
models run unchanged on SQLite for tests / offline demos.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, Float, Integer, String, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import DATABASE_URL

# JSONB on PostgreSQL (indexable, canonical storage), plain JSON elsewhere
# (SQLite tests / offline demos) — identical ORM code on both dialects.
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")

_connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    """One saved input bundle + its fitted result.

    Saving is done as a *single* row per analysis so that the stored
    snapshot is exactly sufficient to reproduce the fit: refitting the
    stored ``input_json`` must yield the stored parameters.
    """

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="未命名试验")

    # Full reproducible input snapshot (units, distance, Q, bounds,
    # weights, raw time/drawdown arrays with null gaps preserved).
    input_json: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)

    # Fitted result (parameters, CIs, residuals, warnings, limitations).
    result_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)

    # Denormalised scalar columns for quick listing / sanity checks.
    transmissivity_m2_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    storativity: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow
    )


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

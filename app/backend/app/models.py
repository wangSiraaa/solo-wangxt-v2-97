"""SQLAlchemy models.

A ``run`` is one saved input batch: geometry, pumping rate with its unit
selectors, parameter bounds and the raw observations (missing readings kept as
NULL). The fit output is stored on the same row as JSON so a saved run can be
reloaded and re-fitted to reproduce the original result.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_name: Mapped[str] = mapped_column(String(200), default="未命名试验")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Geometry / pumping — original values AND selectors are both stored.
    distance: Mapped[float] = mapped_column(Float)
    distance_unit: Mapped[str] = mapped_column(String(8), default="m")
    rate: Mapped[float] = mapped_column(Float)
    rate_unit: Mapped[str] = mapped_column(String(8), default="m3/h")
    time_unit: Mapped[str] = mapped_column(String(8), default="min")
    head_unit: Mapped[str] = mapped_column(String(8), default="m")

    static_water_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    level_datum: Mapped[str] = mapped_column(String(16), default="above_msl")
    datum_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Parameter bounds as entered (SI physical units).
    bounds: Mapped[dict] = mapped_column(JSON, default=dict)
    # Fit output, diagnostics and input checks (set after fitting).
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    observations: Mapped[list["Observation"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Observation.id"
    )


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)  # original import order
    t_raw: Mapped[float | None] = mapped_column(Float, nullable=True)
    drawdown_raw: Mapped[float | None] = mapped_column(Float, nullable=True)

    run: Mapped[Run] = relationship(back_populates="observations")

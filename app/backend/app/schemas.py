"""Pydantic schemas for the API boundary."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ObservationPoint(BaseModel):
    """One time/drawdown pair. Either field may be null for a missing reading."""

    t: float | None = Field(default=None, description="time since pump start")
    drawdown: float | None = Field(default=None, description="observed drawdown")


class Bounds(BaseModel):
    """Parameter search bounds (physical units, SI)."""

    t_min_m2_s: float = 1.0e-9
    t_max_m2_s: float = 1.0e1
    s_min: float = 1.0e-8
    s_max: float = 1.0e-1

    @field_validator("t_max_m2_s")
    @classmethod
    def t_order(cls, v, info):
        if "t_min_m2_s" in info.data and v <= info.data["t_min_m2_s"]:
            raise ValueError("t_max_m2_s must exceed t_min_m2_s")
        return v

    @field_validator("s_max")
    @classmethod
    def s_order(cls, v, info):
        if "s_min" in info.data and v <= info.data["s_min"]:
            raise ValueError("s_max must exceed s_min")
        return v


class FitRequest(BaseModel):
    project_name: str = Field(default="未命名试验", max_length=200)
    distance: float = Field(gt=0, description="distance pumping well -> observation well")
    distance_unit: Literal["m", "ft"] = "m"
    rate: float = Field(gt=0, description="constant pumping rate")
    rate_unit: Literal["m3/s", "m3/h", "m3/d", "L/s", "gpm_us"] = "m3/h"
    time_unit: Literal["s", "min", "h", "d"] = "min"
    head_unit: Literal["m", "ft"] = "m"
    # Static water level and the measurement datum the readings are referred to.
    static_water_level: float | None = Field(
        default=None, description="pre-pumping static level, positive number"
    )
    level_datum: Literal["above_msl", "below_ground"] = "above_msl"
    datum_note: str | None = Field(default=None, max_length=400)
    observations: list[ObservationPoint] = Field(min_length=1)
    bounds: Bounds = Field(default_factory=Bounds)
    # When true, persist the run and return an id for later reproduction.
    save: bool = False


class FitCurvePoint(BaseModel):
    t_s: float
    drawdown_model_m: float | None


class FitResponse(BaseModel):
    run_id: int | None = None
    converged: bool
    message: str
    transmissivity_m2_s: float | None = None
    storativity: float | None = None
    transmissivity_display: dict | None = None
    storativity_display: dict | None = None
    rmse_head: dict | None = None
    r_squared: float | None
    n_points: int
    n_missing: int
    diagnostics: list[dict]
    input_checks: list[dict]
    # Echoed back in SI for plotting, plus the model curve.
    observations_si: list[dict]
    curve: list[FitCurvePoint]
    meta: dict


class RunSummary(BaseModel):
    id: int
    project_name: str
    created_at: str
    distance_m: float
    rate_m3_s: float
    transmissivity_m2_s: float | None
    storativity: float | None
    converged: bool

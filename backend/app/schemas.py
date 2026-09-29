"""Pydantic request/response schemas."""
from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .units import (
    DISTANCE_TO_METRES,
    RATE_TO_SI,
    TIME_TO_SECONDS,
)

DistanceUnit = Literal["m", "cm", "ft"]
RateUnit = Literal["m3/s", "m3/min", "m3/h", "L/s", "gpm"]
TimeUnit = Literal["s", "min", "h", "d"]
Weights = Literal["log", "linear"]


class FitRequest(BaseModel):
    name: str = Field(default="未命名试验", max_length=200)

    # Geometry / stress
    distance: float = Field(gt=0, description="抽水井到观测井的距离")
    distance_unit: DistanceUnit = "m"
    pumping_rate: float = Field(gt=0, description="恒定抽水流量")
    pumping_rate_unit: RateUnit = "m3/h"

    # Data.  Null entries represent missing measurements and MUST stay
    # missing — they are neither imputed nor dropped from the raw input.
    times: list[float | None] = Field(min_length=1)
    drawdowns: list[float | None] = Field(min_length=1)
    time_unit: TimeUnit = "min"

    # Parameter search bounds (SI): T in m^2/s, S dimensionless.
    t_min: float = 1.0e-9
    t_max: float = 1.0e3
    s_min: float = 1.0e-10
    s_max: float = 1.0e0

    weights: Weights = "log"

    @field_validator("times", "drawdowns")
    @classmethod
    def reject_nan_inf(cls, v):
        for x in v:
            if x is not None and (math.isnan(x) or math.isinf(x)):
                raise ValueError("NaN / Inf are not allowed; use null for missing.")
        return v

    @model_validator(mode="after")
    def _checks(self):
        if len(self.times) != len(self.drawdowns):
            raise ValueError("times 与 drawdowns 长度必须一致。")
        valid_pairs = sum(
            t is not None and d is not None and t > 0
            for t, d in zip(self.times, self.drawdowns)
        )
        if valid_pairs < 3:
            raise ValueError(
                "至少需要 3 个时间为正的有效（时间, 降深）数据对。"
            )
        for d in self.drawdowns:
            if d is not None and d < 0:
                raise ValueError(
                    "降深不能为负。请检查基准水位（应使用抽水前的稳定水位），"
                    "恢复阶段的数据不适用 Theis 模型。"
                )
        if not (self.t_min < self.t_max and self.s_min < self.s_max):
            raise ValueError("参数下界必须严格小于上界。")
        return self


class Point(BaseModel):
    time_s: float | None
    drawdown_m: float | None
    model_drawdown_m: float | None = None
    residual_m: float | None = None
    used_in_fit: bool


class FitResponse(BaseModel):
    name: str
    # SI inputs actually used in the fit:
    distance_m: float
    pumping_rate_m3_s: float

    transmissivity_m2_s: float
    storativity: float
    t_bounds: list[float]
    s_bounds: list[float]
    t_se: float
    s_se: float
    t_ci95: list[float]
    s_ci95: list[float]

    rmse_m: float
    mae_m: float
    max_abs_residual_m: float
    r_squared: float
    residual_trend_slope: float
    hit_bounds: list[str]

    points: list[Point]
    # Dense modelled curve for plotting:
    curve_time_s: list[float]
    curve_drawdown_m: list[float]

    warnings: list[str]
    limitations: list[str]

    # The exact input to persist for one-shot reproducibility:
    input_json: dict

    saved_id: int | None = None


class AnalysisSummary(BaseModel):
    id: int
    name: str
    transmissivity_m2_s: float | None
    storativity: float | None
    created_at: str


class AnalysisDetail(BaseModel):
    id: int
    name: str
    input_json: dict
    result_json: dict
    created_at: str

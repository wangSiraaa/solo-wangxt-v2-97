"""Input sanity checks: units, datum, duplicates and missing-value policy.

These checks never rewrite the user's numbers — they report findings. Missing
readings (null time or drawdown) are carried through and shown as gaps.
"""
from __future__ import annotations

import numpy as np

from .units import (
    TimeUnit,
    head_to_metres,
    length_to_metres,
    rate_to_m3_s,
    time_to_seconds,
    HeadUnit,
    LengthUnit,
    RateUnit,
)


def check_request(req) -> tuple[dict, list[dict]]:
    """Convert a FitRequest to SI arrays and produce input-check findings.

    Returns (converted, checks) where converted has keys:
      t_s (list[float|None]), drawdown_m (list[float|None]),
      distance_m, rate_m3_s, static_level_m
    """
    checks: list[dict] = []

    distance_m = length_to_metres(req.distance, LengthUnit(req.distance_unit))
    rate_m3_s = rate_to_m3_s(req.rate, RateUnit(req.rate_unit))
    static_m = (
        head_to_metres(req.static_water_level, HeadUnit(req.head_unit))
        if req.static_water_level is not None
        else None
    )

    t_s: list[float | None] = []
    dd_m: list[float | None] = []
    for p in req.observations:
        if p.t is None or p.drawdown is None:
            t_s.append(None if p.t is None else time_to_seconds(p.t, TimeUnit(req.time_unit)))
            dd_m.append(
                None
                if p.drawdown is None
                else head_to_metres(p.drawdown, HeadUnit(req.head_unit))
            )
        else:
            t_s.append(time_to_seconds(p.t, TimeUnit(req.time_unit)))
            dd_m.append(head_to_metres(p.drawdown, HeadUnit(req.head_unit)))

    def add(severity: str, code: str, message: str) -> None:
        checks.append({"severity": severity, "code": code, "message": message})

    n_total = len(req.observations)
    n_missing = sum(1 for t, d in zip(t_s, dd_m) if t is None or d is None)
    valid = [(t, d) for t, d in zip(t_s, dd_m) if t is not None and d is not None]

    add(
        "info",
        "UNIT_CONVERSION",
        f"已按所选单位换算为 SI：井距 {distance_m:g} m，流量 {rate_m3_s:g} m³/s，"
        f"时间以 s 计，降深以 m 计。请确认单位下拉框与原始记录一致。",
    )

    if n_missing:
        add(
            "info",
            "MISSING_VALUES",
            f"共 {n_total} 行，其中 {n_missing} 个测点缺时间或缺降深，"
            "保持缺失状态并在图中以缺口显示，不参与拟合。",
        )

    # Datum / static-level check.
    if static_m is None:
        add(
            "warning",
            "NO_STATIC_LEVEL",
            "未提供抽水前静水位。降深必须以同一静水位为基准计算（s = 静水位 − 实测水位）；"
            "若导入的是绝对水位而非降深，请先在前端或原始表格中换算后重新导入。",
        )
    else:
        if req.level_datum == "above_msl" and static_m < 0:
            add(
                "warning",
                "DATUM_SUSPICIOUS",
                "静水位按海拔（高于平均海平面）录入却为负值，请确认基准与符号约定。",
            )
        add(
            "info",
            "STATIC_LEVEL",
            f"抽水前静水位为 {static_m:g} m（{('海拔' if req.level_datum == 'above_msl' else '地面以下')} 基准）。"
            "确认所有降深均以该静水位为基准。",
        )

    if valid:
        tv = np.array([v[0] for v in valid], dtype=float)
        dv = np.array([v[1] for v in valid], dtype=float)

        if np.any(tv <= 0):
            add("error", "NONPOSITIVE_TIME", "存在 t ≤ 0 的测点，抽水时间必须严格为正，已剔除。")
        if np.any(dv < 0):
            add(
                "warning",
                "NEGATIVE_DRAWDOWN",
                "存在负降深（水位高于静水位）。若不是噪声，请检查水位基准/符号。",
            )
        if len(set(np.round(tv, 9))) < len(tv):
            add("warning", "DUPLICATE_TIME", "存在重复时间点，拟合时各自保留，请核对原始记录。")
        # Strictly increasing check.
        if np.any(np.diff(tv) < 0):
            add("warning", "TIME_NOT_SORTED", "观测时间不是递增排列；图中仍按原始顺序展示，拟合不受影响。")
        # Plausibility envelopes (rough engineering ranges).
        if not (1.0e-3 <= distance_m <= 1.0e5):
            add("error", "DISTANCE_RANGE", f"换算后井距 {distance_m:g} m 超出合理量级，请核对距离单位。")
        if not (1.0e-8 <= rate_m3_s <= 1.0e1):
            add("error", "RATE_RANGE", f"换算后流量 {rate_m3_s:g} m³/s 超出合理量级，请核对流量单位。")
        if np.max(dv) > 500:
            add("warning", "DRAWDOWN_HUGE", f"最大降深 {np.max(dv):g} m 异常大，请检查降深单位。")
        if len(valid) < 4:
            add(
                "error",
                "TOO_FEW_VALID",
                f"有效测点仅 {len(valid)} 个，少于 Theis 拟合所需的最少 4 个。",
            )
    else:
        add("error", "NO_VALID_POINTS", "没有任何完整的（时间, 降深）测点，无法拟合。")

    converted = {
        "t_s": t_s,
        "drawdown_m": dd_m,
        "distance_m": distance_m,
        "rate_m3_s": rate_m3_s,
        "static_level_m": static_m,
        "n_missing": n_missing,
        "n_total": n_total,
    }
    return converted, checks

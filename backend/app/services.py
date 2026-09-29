"""Service layer: convert request units -> SI, fit, build response."""
from __future__ import annotations

import math

import numpy as np

from .theis import fit_theis, theis_drawdown
from .units import distance_to_metres, rate_to_si, time_to_seconds


def _input_checks(times_s: list[float | None], s_m: list[float | None]) -> list[str]:
    """Data-level checks independent of the fit (baseline / monotonicity)."""
    warns: list[str] = []
    pairs = [
        (t, s)
        for t, s in zip(times_s, s_m)
        if t is not None and s is not None
    ]
    if pairs:
        first_s = pairs[0][1]
        if abs(first_s) > 0.02 * max(p[1] for p in pairs):
            warns.append(
                f"首个有效测点已有 {first_s:.3g} m 降深。请确认基准水位取的是"
                "抽水前稳定水位、且 t=0 对应开泵时刻。"
            )
        # gross non-monotonicity (allow 1 cm / 2% jitter)
        tol = max(0.01, 0.02 * max(p[1] for p in pairs))
        reversals = sum(
            1
            for (_, s0), (_, s1) in zip(pairs, pairs[1:])
            if s1 < s0 - tol
        )
        if reversals > len(pairs) * 0.2:
            warns.append(
                "降深序列存在大量非单调回落（超过允许的测量噪声），可能混入"
                "水位恢复数据或基准水位漂移，Theis 模型要求持续抽水。"
            )
    if len(times_s) - len(pairs) > 0:
        warns.append(
            f"存在 {len(times_s) - len(pairs)} 个缺测测点，已保持缺失、不"
            "参与拟合，也未做插补。"
        )
    return warns


def run_fit(req) -> dict:
    """Convert a FitRequest to SI and run the Theis fit.

    Returns a dict shaped like FitResponse (minus persistence fields).
    Raises ValueError with a Chinese message on invalid data.
    """
    r = distance_to_metres(req.distance, req.distance_unit)
    Q = rate_to_si(req.pumping_rate, req.pumping_rate_unit)
    times_s = [
        None if t is None else time_to_seconds(t, req.time_unit)
        for t in req.times
    ]
    s_m = list(req.drawdowns)

    result, t_used, s_obs, s_model_used = fit_theis(
        times_s=times_s,
        drawdowns_m=s_m,
        Q=Q,
        r=r,
        t_bounds=(req.t_min, req.t_max),
        s_bounds=(req.s_min, req.s_max),
        weights=req.weights,
    )

    warnings = _input_checks(times_s, s_m) + result.warnings

    # Per-point table: missing stays null; modelled value / residual are
    # reported only for points actually used in the fit.
    used_iter = iter(zip(t_used, s_obs, s_model_used))
    used_map: dict[float, tuple[float, float, float]] = {
        float(t): (o, m, o - m) for t, o, m in zip(t_used, s_obs, s_model_used)
    }
    points = []
    for t, s in zip(times_s, s_m):
        if t is None or s is None or t <= 0:
            points.append(
                dict(
                    time_s=t,
                    drawdown_m=s,
                    model_drawdown_m=None,
                    residual_m=None,
                    used_in_fit=False,
                )
            )
        else:
            o, m, res = used_map[float(t)]
            points.append(
                dict(
                    time_s=float(t),
                    drawdown_m=float(o),
                    model_drawdown_m=float(m),
                    residual_m=float(res),
                    used_in_fit=True,
                )
            )

    # Dense model curve across the observed range (log-spaced) for plot.
    tmin = max(float(np.min(t_used)), 1e-3)
    tmax = float(np.max(t_used))
    curve_t = np.logspace(math.log10(tmin), math.log10(tmax), 300)
    curve_s = theis_drawdown(
        curve_t, Q, r, result.transmissivity_m2_s, result.storativity
    )

    return dict(
        name=req.name,
        distance_m=r,
        pumping_rate_m3_s=Q,
        transmissivity_m2_s=result.transmissivity_m2_s,
        storativity=result.storativity,
        t_bounds=result.t_bounds,
        s_bounds=result.s_bounds,
        t_se=result.t_se,
        s_se=result.s_se,
        t_ci95=result.t_ci95,
        s_ci95=result.s_ci95,
        rmse_m=result.rmse_m,
        mae_m=result.mae_m,
        max_abs_residual_m=result.max_abs_residual_m,
        r_squared=result.r_squared,
        residual_trend_slope=result.residual_trend_slope,
        hit_bounds=result.hit_bounds,
        points=points,
        curve_time_s=[float(x) for x in curve_t],
        curve_drawdown_m=[float(x) for x in curve_s],
        warnings=warnings,
        limitations=result.limitations,
        input_json=req.model_dump(),
    )

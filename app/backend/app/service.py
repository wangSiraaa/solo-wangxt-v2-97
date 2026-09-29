"""Fit orchestration: unit conversion -> checks -> SciPy fit -> response shape."""
from __future__ import annotations

import numpy as np

from .fit import fit_theis
from .theis import theis_drawdown
from .units import head_to_metres, HeadUnit
from .validation import check_request


def _curve_times(t_s: np.ndarray, n: int = 300) -> np.ndarray:
    """Log-spaced model curve spanning the valid observation window."""
    if t_s.size == 0:
        return np.array([])
    lo = max(float(t_s.min()) * 0.8, 1e-30)
    hi = float(t_s.max()) * 1.2
    if hi <= lo:
        hi = lo * 10.0
    return np.geomspace(lo, hi, n)


def run_analysis(req) -> dict:
    """Pure function: takes a FitRequest-like object, returns response dict."""
    converted, input_checks = check_request(req)

    t_all = converted["t_s"]
    d_all = converted["drawdown_m"]
    valid_t = np.array([t for t in t_all if t is not None], dtype=float)
    valid_d = np.array(
        [d for t, d in zip(t_all, d_all) if t is not None and d is not None],
        dtype=float,
    )
    # Align times for valid_d
    valid_pairs = [
        (t, d) for t, d in zip(t_all, d_all) if t is not None and d is not None
    ]
    valid_t = np.array([p[0] for p in valid_pairs], dtype=float)
    valid_d = np.array([p[1] for p in valid_pairs], dtype=float)

    b = req.bounds
    fit = fit_theis(
        valid_t,
        valid_d,
        converted["distance_m"],
        converted["rate_m3_s"],
        t_bounds=(b.t_min_m2_s, b.t_max_m2_s),
        s_bounds=(b.s_min, b.s_max),
    )

    curve: list[dict] = []
    observations_si: list[dict] = []

    if fit.converged:
        ct = _curve_times(valid_t)
        cd = theis_drawdown(
            ct,
            fit.transmissivity_m2_s,
            fit.storativity,
            converted["distance_m"],
            converted["rate_m3_s"],
        )
        curve = [
            {"t_s": float(x), "drawdown_model_m": (None if not np.isfinite(y) else float(y))}
            for x, y in zip(ct, cd)
        ]

    per_point_pred: list[float | None] = []
    if fit.converged:
        for t, d in zip(t_all, d_all):
            if t is None:
                per_point_pred.append(None)
            else:
                # A missing drawdown still has a model value at that time,
                # which lets the chart show the gap against the curve.
                per_point_pred.append(
                    float(
                        theis_drawdown(
                            np.array([t]),
                            fit.transmissivity_m2_s,
                            fit.storativity,
                            converted["distance_m"],
                            converted["rate_m3_s"],
                        )[0]
                    )
                )
    else:
        per_point_pred = [None] * len(t_all)

    for idx, ((t, d), pred) in enumerate(zip(zip(t_all, d_all), per_point_pred)):
        observations_si.append(
            {
                "seq": idx,
                "t_s": t,
                "drawdown_m": d,
                "drawdown_model_m": pred,
                "residual_m": (None if (d is None or pred is None) else d - pred),
                "missing": t is None or d is None,
            }
        )

    rmse_head: dict | None = None
    if fit.rmse_m is not None:
        rmse_head = {
            "m": fit.rmse_m,
            "ft": fit.rmse_m / 0.3048,
        }

    transmissivity_display = (
        {"m2_s": fit.transmissivity_m2_s, "m2_d": fit.transmissivity_m2_s * 86400.0}
        if fit.transmissivity_m2_s is not None
        else None
    )
    storativity_display = {"value": fit.storativity} if fit.storativity is not None else None

    return {
        "converged": fit.converged,
        "message": fit.message,
        "transmissivity_m2_s": fit.transmissivity_m2_s,
        "storativity": fit.storativity,
        "transmissivity_display": transmissivity_display,
        "storativity_display": storativity_display,
        "rmse_head": rmse_head,
        "r_squared": fit.r_squared,
        "n_points": fit.n_points,
        "n_missing": converted["n_missing"],
        "diagnostics": fit.diagnostics,
        "input_checks": input_checks,
        "observations_si": observations_si,
        "curve": curve,
        "meta": {
            "distance_m": converted["distance_m"],
            "rate_m3_s": converted["rate_m3_s"],
            "time_unit": req.time_unit,
            "head_unit": req.head_unit,
            "distance_unit": req.distance_unit,
            "rate_unit": req.rate_unit,
            "static_level_m": converted["static_level_m"],
            "level_datum": req.level_datum,
            "bounds": b.model_dump(),
        },
    }

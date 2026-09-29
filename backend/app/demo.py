"""Synthetic verification datasets served to the UI.

Same generator as scripts/synth_data.py, kept importable by the API.
"""
from __future__ import annotations

import numpy as np

from .theis import theis_drawdown
from .units import rate_to_si, time_to_seconds

T_TRUE = 5.0e-3
S_TRUE = 2.0e-4
R_TRUE = 100.0
Q_M3H = 120.0


def _schedule() -> list[float]:
    return np.logspace(np.log10(1), np.log10(2880), 40).tolist()


def _drawdowns(t_minutes, noise_std=0.0, seed=42, missing=()):
    rng = np.random.default_rng(seed)
    Q = rate_to_si(Q_M3H, "m3/h")
    t_s = np.array([time_to_seconds(t, "min") for t in t_minutes])
    s = theis_drawdown(t_s, Q, R_TRUE, T_TRUE, S_TRUE)
    if noise_std:
        s = s + rng.normal(0.0, noise_std, size=s.shape)
    out = [round(float(x), 4) for x in s]
    for i in missing:
        out[i] = None
    return out


def demo_payload(kind: str) -> dict:
    t = _schedule()
    base = dict(
        pumping_rate=Q_M3H,
        pumping_rate_unit="m3/h",
        time_unit="min",
        weights="log",
        t_min=1e-9, t_max=1e3, s_min=1e-10, s_max=1e0,
    )
    if kind == "exact":
        return dict(
            base,
            name="核对1：合成已知参数（无噪声）",
            distance=R_TRUE, distance_unit="m",
            times=t, drawdowns=_drawdowns(t),
            _truth={"T_m2_s": T_TRUE, "S": S_TRUE},
        )
    if kind == "noisy":
        return dict(
            base,
            name="核对2：含 1 cm 噪声 + 2 个缺测",
            distance=R_TRUE, distance_unit="m",
            times=t, drawdowns=_drawdowns(t, 0.01, missing=(7, 21)),
            _truth={"T_m2_s": T_TRUE, "S": S_TRUE},
        )
    if kind == "wrong_unit":
        # Physical truth: r = 100 m.  Operator mistypes the unit as feet,
        # so the API treats the distance as 30.48 m -> S biased ~10.76x.
        return dict(
            base,
            name="核对3：井距 100 m 被误标为 ft",
            distance=R_TRUE, distance_unit="ft",
            times=t, drawdowns=_drawdowns(t),
            _truth={
                "T_m2_s": T_TRUE, "S": S_TRUE,
                "note": "真实井距 100 m，界面误选 ft；拟合仍完美但 S 被高估。",
            },
        )
    raise KeyError(kind)

"""Theis (1935) model for a homogeneous confined aquifer, constant pumping rate.

s(t) = Q / (4 pi T) * W(u)
u    = r^2 S / (4 T t)
W(u) = exp1(u)

All quantities are SI internally: seconds, metres, cubic metres per second,
metres of drawdown. Conversion to/from the user's display units happens in
``units.py``.
"""
from __future__ import annotations

import numpy as np
from scipy.special import exp1

# Numerical guard: scipy.exp1 overflows below ~ -745; u is always positive here
# but we clamp the tiny-u side where W(u) ~ -gamma - ln(u).
_U_FLOOR = 1.0e-300


def theis_drawdown(
    t_s: np.ndarray | float,
    transmissivity_m2_s: float,
    storativity: float,
    distance_m: float,
    rate_m3_s: float,
) -> np.ndarray:
    """Return Theis drawdown in metres for times in seconds."""
    t = np.asarray(t_s, dtype=float)
    if transmissivity_m2_s <= 0 or storativity <= 0 or distance_m <= 0:
        return np.full_like(t, np.nan, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        u = distance_m**2 * storativity / (4.0 * transmissivity_m2_s * t)
        u = np.where(np.isfinite(u), np.maximum(u, _U_FLOOR), u)
        w = exp1(u)  # well function E1
    return rate_m3_s / (4.0 * np.pi * transmissivity_m2_s) * w

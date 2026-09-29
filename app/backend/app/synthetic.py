"""Generate synthetic Theis datasets for verification and the demo button.

Known true parameters -> exact Theis drawdown -> optional Gaussian noise ->
optional missing readings. Times are in minutes, drawdown in metres by
default, matching common field record formats.
"""
from __future__ import annotations

import numpy as np
from scipy.special import exp1

MIN = 60.0
HOUR = 3600.0


def theis_s(t_s, T, S, r, Q):
    u = r**2 * S / (4.0 * T * t_s)
    return Q / (4.0 * np.pi * T) * exp1(u)


def synthetic_dataset(
    T=1.2e-3,            # m^2/s (~104 m^2/d)
    S=2.0e-4,
    r=50.0,              # m
    Q=80.0 / 3600.0,     # 80 m^3/h in m^3/s
    times_min=None,
    noise_std_m=0.0,
    missing_seq=(),
    rng_seed=42,
):
    """Return list of dicts {t_min, drawdown_m (or None)} plus true params."""
    if times_min is None:
        times_min = np.array(
            [1, 2, 3, 5, 8, 12, 20, 30, 45, 60, 90, 120, 180, 240, 360, 480, 720, 960, 1440],
            dtype=float,
        )
    rng = np.random.default_rng(rng_seed)
    t_s = np.asarray(times_min, dtype=float) * MIN
    d = theis_s(t_s, T, S, r, Q)
    if noise_std_m:
        d = d + rng.normal(0.0, noise_std_m, size=d.shape)
    out = []
    for i, (tm, dm) in enumerate(zip(times_min, d)):
        if i in missing_seq:
            out.append({"t": float(tm), "drawdown": None})
        else:
            out.append({"t": float(tm), "drawdown": float(dm)})
    return {
        "observations": out,
        "true": {"T": T, "S": S, "r": r, "Q_m3_h": Q * 3600.0},
    }


def standard_clean():
    return synthetic_dataset(noise_std_m=0.0)


def standard_noisy(noise_std_m=0.01, rng_seed=7):
    # Drop two middle readings to demonstrate the missing-value policy.
    return synthetic_dataset(
        noise_std_m=noise_std_m, missing_seq=(7, 13), rng_seed=rng_seed
    )

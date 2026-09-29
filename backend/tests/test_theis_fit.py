"""Verification cases requested for the first release:

1. synthetic data with KNOWN parameters  -> T, S recovered;
2. same data + small Gaussian noise + gaps -> still recovered,
   missing points stay missing (no imputation);
3. distance-unit mistake (m declared as ft) -> the mathematical
   r^2 <-> S coupling demonstrated; gross unit errors surface a warning;
4. persistence: one saved input reproduces the fitted result exactly.
"""
from __future__ import annotations

import numpy as np

from app.schemas import FitRequest
from app.services import run_fit
from app.theis import theis_drawdown
from app.units import rate_to_si, time_to_seconds

T_TRUE = 5.0e-3       # m^2/s
S_TRUE = 2.0e-4       # -
R_TRUE = 100.0        # m
Q_M3H = 120.0         # m^3/h

T_MINUTES = np.logspace(np.log10(1), np.log10(2880), 40).tolist()
MISSING_IDX = (7, 21)


def _synthetic(noise_std: float = 0.0, seed: int = 42):
    rng = np.random.default_rng(seed)
    Q = rate_to_si(Q_M3H, "m3/h")
    t_s = np.array([time_to_seconds(t, "min") for t in T_MINUTES])
    s = theis_drawdown(t_s, Q, R_TRUE, T_TRUE, S_TRUE)
    if noise_std:
        s = s + rng.normal(0.0, noise_std, size=s.shape)
    return t_s, np.round(s, 4)


def _base_request(**overrides) -> FitRequest:
    payload = dict(
        name="核对试验",
        distance=R_TRUE,
        distance_unit="m",
        pumping_rate=Q_M3H,
        pumping_rate_unit="m3/h",
        times=T_MINUTES,
        drawdowns=None,
        time_unit="min",
    )
    payload.update(overrides)
    return FitRequest(**payload)


# ---------------------------------------------------------------- case 1
def test_exact_synthetic_parameters_recovered():
    _, s = _synthetic()
    req = _base_request(drawdowns=s.tolist())
    out = run_fit(req)
    rt_T = out["transmissivity_m2_s"] / T_TRUE
    rt_S = out["storativity"] / S_TRUE
    assert 0.98 < rt_T < 1.02, rt_T
    assert 0.95 < rt_S < 1.05, rt_S
    assert out["r_squared"] > 0.999
    assert out["rmse_m"] < 1e-3
    # A correct confined-aquifer dataset produces no physics warnings.
    assert out["warnings"] == [], out["warnings"]
    # The non-permit disclaimer is always carried with every result.
    assert any("开采许可" in x for x in out["limitations"])


# ---------------------------------------------------------------- case 2
def test_noisy_data_and_missing_points_preserved():
    _, s = _synthetic(noise_std=0.01)
    draws = s.tolist()
    draws[MISSING_IDX[0]] = None
    draws[MISSING_IDX[1]] = None
    req = _base_request(drawdowns=draws)
    out = run_fit(req)
    rt_T = out["transmissivity_m2_s"] / T_TRUE
    rt_S = out["storativity"] / S_TRUE
    # 1 cm noise vs decimetre-scale drawdown: tight on T, looser on S.
    assert 0.95 < rt_T < 1.05, rt_T
    assert 0.70 < rt_S < 1.30, rt_S
    assert out["r_squared"] > 0.98

    # Missing points are returned verbatim as null, never imputed.
    pts = out["points"]
    for i in MISSING_IDX:
        assert pts[i]["drawdown_m"] is None
        assert pts[i]["model_drawdown_m"] is None
        assert pts[i]["residual_m"] is None
        assert pts[i]["used_in_fit"] is False
    n_used = sum(p["used_in_fit"] for p in pts)
    assert n_used == len(T_MINUTES) - len(MISSING_IDX)
    assert any("缺测" in w for w in out["warnings"])


# ------------------------------------------- case 3a: subtle unit error
def test_distance_unit_error_shows_r2_S_coupling():
    """100 m declared as 100 ft: fit is 'perfect' yet S is biased by
    (r_true/r_used)^2 — a single well cannot detect this by itself."""
    _, s = _synthetic()
    req = _base_request(distance=100.0, distance_unit="ft", drawdowns=s.tolist())
    out = run_fit(req)

    r_used = 100.0 * 0.3048
    # u = r^2 S / (4Tt) must stay the same -> S_fit = S_true*(r_true/r_used)^2
    expected_ratio = (R_TRUE / r_used) ** 2  # ~10.76
    ratio = out["storativity"] / S_TRUE
    assert abs(ratio - expected_ratio) / expected_ratio < 0.02, (ratio, expected_ratio)
    # T is unaffected by the r^2 scaling (it is fixed by the late-time slope).
    assert 0.98 < out["transmissivity_m2_s"] / T_TRUE < 1.02
    # The fit itself looks excellent...
    assert out["r_squared"] > 0.999
    # ...so 2.15e-3 stays inside the plausible band and no warning fires;
    # the API must instead always carry the coupling caveat for the user.
    assert not any("井距单位" in w for w in out["warnings"])
    assert any("耦合" in x for x in out["limitations"])


# ------------------------------------------- case 3b: gross unit error
def test_gross_distance_unit_error_warns():
    """Declaring 100 m as 100 cm makes r 100x too small; fitting then
    requires S ~ 2.0 (1e4-fold bias), which is pinned against the search
    bound and outside the confined-aquifer band -> explicit warning to
    re-check distance units / baseline."""
    _, s = _synthetic()
    req = _base_request(distance=100.0, distance_unit="cm", drawdowns=s.tolist())
    out = run_fit(req)
    # The optimizer cannot leave the 10x.. band; S sits on the upper bound.
    assert "S" in out["hit_bounds"]
    assert any("井距单位" in w for w in out["warnings"]), out["warnings"]


# ---------------------------------------------------------------- misc.
def test_negative_drawdown_rejected_with_baseline_message():
    _, s = _synthetic()
    draws = s.tolist()
    draws[5] = -0.05
    try:
        _base_request(drawdowns=draws)
    except Exception as exc:  # pydantic ValidationError wraps the message
        assert "基准水位" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("negative drawdown must be rejected")


def test_bounds_hit_is_flagged():
    _, s = _synthetic()
    # Impossibly narrow bounds force the optimizer onto the boundary.
    req = _base_request(
        drawdowns=s.tolist(), t_min=1e-9, t_max=1e-6, s_min=1e-10, s_max=1e0
    )
    out = run_fit(req)
    assert "T" in out["hit_bounds"]
    assert any("边界" in w for w in out["warnings"])


def test_short_record_warns():
    t = [10.0, 12.0, 15.0, 18.0]
    Q = rate_to_si(Q_M3H, "m3/h")
    ts = np.array([time_to_seconds(x, "min") for x in t])
    s = theis_drawdown(ts, Q, R_TRUE, T_TRUE, S_TRUE)
    req = _base_request(times=t, drawdowns=s.tolist())
    out = run_fit(req)
    assert any("时间跨度" in w for w in out["warnings"])

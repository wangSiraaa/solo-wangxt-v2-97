"""Verification cases required for first release:

1. Synthetic data from KNOWN parameters -> fit must recover T and S.
2. The same data with small Gaussian noise + missing readings -> still close,
   missing points stay missing.
3. Distance-unit mistake (true geometry in feet, declared as metres) -> the
   fit converges to a physically implausible S and the app must raise a
   unit/plausibility diagnostic.
4. A saved run reproduces the identical result when reloaded and refitted.
"""
from __future__ import annotations

import os

# Isolated SQLite DB so the suite does not need the PostgreSQL instance.
os.environ.setdefault(
    "PUMPING_DATABASE_URL", "sqlite:///./test_pumping.db"
)

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.synthetic import standard_clean, standard_noisy  # noqa: E402

init_db()
client = TestClient(app)


def _payload(ds, **overrides):
    p = {
        "project_name": "核对案例",
        "distance": ds["true"]["r"],
        "distance_unit": "m",
        "rate": ds["true"]["Q_m3_h"],
        "rate_unit": "m3/h",
        "time_unit": "min",
        "head_unit": "m",
        "static_water_level": 12.5,
        "level_datum": "above_msl",
        "observations": ds["observations"],
        "bounds": {
            "t_min_m2_s": 1e-9,
            "t_max_m2_s": 1e1,
            "s_min": 1e-8,
            "s_max": 1e-1,
        },
    }
    p.update(overrides)
    return p


def test_clean_synthetic_recovers_true_parameters():
    ds = standard_clean()
    r = client.post("/api/fit", json=_payload(ds)).json()
    assert r["converged"], r["message"]
    tT, tS = ds["true"]["T"], ds["true"]["S"]
    fT, fS = r["transmissivity_m2_s"], r["storativity"]
    # Exact data: better than 1% on T, a few percent on S.
    assert abs(fT - tT) / tT < 0.01, (fT, tT)
    assert abs(fS - tS) / tS < 0.05, (fS, tS)
    assert r["r_squared"] > 0.999
    assert r["rmse_head"]["m"] < 1e-6
    print(f"\n[clean] true T={tT:.4e} fit T={fT:.4e}; true S={tS:.4e} fit S={fS:.4e}")


def test_noisy_data_with_missing_points():
    ds = standard_noisy()
    payload = _payload(ds)
    r = client.post("/api/fit", json=payload).json()
    assert r["converged"]
    tT, tS = ds["true"]["T"], ds["true"]["S"]
    fT, fS = r["transmissivity_m2_s"], r["storativity"]
    # Noise 0.01 m on ~0.5-2 m drawdowns: 10% T, 20% S tolerance.
    assert abs(fT - tT) / tT < 0.10, (fT, tT)
    assert abs(fS - tS) / tS < 0.20, (fS, tS)

    # Missing readings must be retained as gaps, not dropped or imputed.
    assert r["n_missing"] == 2
    missing_rows = [o for o in r["observations_si"] if o["missing"]]
    assert len(missing_rows) == 2
    for row in missing_rows:
        assert row["drawdown_m"] is None
        assert row["residual_m"] is None
        assert row["drawdown_model_m"] is not None  # model still defined at that t
    assert r["n_points"] == len(ds["observations"]) - 2
    assert any(c["code"] == "MISSING_VALUES" for c in r["input_checks"])
    print(f"\n[noisy] fit T={fT:.4e} S={fS:.4e}; n_missing={r['n_missing']}")


def test_distance_unit_error_is_flagged():
    """Distance-unit mistake cascades into an implausible storativity.

    Classic field error chain: the real distance is 300 ft (~91.4 m), the
    value is declared in metres, and a decimal-point slip enters 1500 m.
    The Theis curve shape cannot expose a pure scale error (R^2 stays ~1 and
    T is recovered correctly), but S is proportional to r^2: the recovered
    S collapses from 2e-4 to ~7.4e-7, crossing the confined-aquifer
    plausibility floor. The app must flag this and name distance units as a
    likely cause.
    """
    ds = standard_clean()
    r_m_true = 300.0 * 0.3048
    r_declared = 1500.0
    t_min = np.array([1, 2, 3, 5, 8, 12, 20, 30, 45, 60, 90, 120, 180, 240, 360, 720, 1440])
    from app.synthetic import theis_s

    d_m = theis_s(
        t_min * 60.0, ds["true"]["T"], ds["true"]["S"], r_m_true, ds["true"]["Q_m3_h"] / 3600.0
    )
    obs = [{"t": float(t), "drawdown": float(s)} for t, s in zip(t_min, d_m)]
    payload = _payload(ds, distance=r_declared, distance_unit="m", observations=obs)
    r = client.post("/api/fit", json=payload).json()
    assert r["converged"]  # fit is numerically fine...
    # T is invariant to the r-scale error; S collapses by (91.44/1500)^2.
    assert abs(r["transmissivity_m2_s"] - ds["true"]["T"]) / ds["true"]["T"] < 0.01
    assert r["storativity"] < 1e-6
    assert r["storativity"] > 5e-7
    codes = {c["code"] for c in r["diagnostics"]}
    assert "S_TOO_LOW" in codes, (r["storativity"], codes)
    msg = next(c["message"] for c in r["diagnostics"] if c["code"] == "S_TOO_LOW")
    assert "单位" in msg
    print(f"\n[unit error] fitted S={r['storativity']:.3e} -> {codes}")


def test_saved_run_is_reproducible():
    ds = standard_noisy()
    payload = _payload(ds, save=True, project_name="复现性核对")
    r1 = client.post("/api/fit", json=payload).json()
    rid = r1["run_id"]
    assert rid is not None

    # GET returns the stored result.
    stored = client.get(f"/api/runs/{rid}").json()
    assert stored["transmissivity_m2_s"] == r1["transmissivity_m2_s"]
    assert stored["storativity"] == r1["storativity"]
    assert len(stored["observations_si"]) == len(ds["observations"])

    # Refit from the saved raw input gives the identical numbers.
    r2 = client.post(f"/api/runs/{rid}/refit").json()
    assert r2["converged"]
    assert r2["transmissivity_m2_s"] == r1["transmissivity_m2_s"]
    assert r2["storativity"] == r1["storativity"]

    # Saved raw values, including the NULLs, round-trip unchanged.
    rows = client.get("/api/runs").json()
    assert any(row["id"] == rid for row in rows)
    print(f"\n[reproduce] run {rid}: T={r1['transmissivity_m2_s']:.6e} S={r1['storativity']:.6e}")

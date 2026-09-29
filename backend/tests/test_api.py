"""End-to-end API checks: validation, save, list, reproduce."""
from __future__ import annotations

import numpy as np

from app.theis import theis_drawdown
from app.units import rate_to_si, time_to_seconds

T_TRUE, S_TRUE, R_TRUE, Q_M3H = 5.0e-3, 2.0e-4, 100.0, 120.0
T_MINUTES = np.logspace(np.log10(1), np.log10(2880), 40).tolist()


def _payload(drawdowns, **kw):
    p = dict(
        name="API 核对",
        distance=R_TRUE,
        distance_unit="m",
        pumping_rate=Q_M3H,
        pumping_rate_unit="m3/h",
        times=T_MINUTES,
        drawdowns=drawdowns,
        time_unit="min",
    )
    p.update(kw)
    return p


def _synthetic_drawdowns(missing=()):
    Q = rate_to_si(Q_M3H, "m3/h")
    t_s = np.array([time_to_seconds(t, "min") for t in T_MINUTES])
    s = np.round(theis_drawdown(t_s, Q, R_TRUE, T_TRUE, S_TRUE), 4).tolist()
    for i in missing:
        s[i] = None
    return s


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_fit_endpoint_recovers_known_parameters(client):
    r = client.post("/api/fit", json=_payload(_synthetic_drawdowns()))
    assert r.status_code == 200, r.text
    body = r.json()
    assert 0.98 < body["transmissivity_m2_s"] / T_TRUE < 1.02
    assert 0.95 < body["storativity"] / S_TRUE < 1.05
    # Fit-only must not persist.
    assert body["saved_id"] is None


def test_validation_length_mismatch(client):
    payload = _payload(_synthetic_drawdowns())
    payload["times"] = [1.0, 2.0, 3.0]
    r = client.post("/api/fit", json=payload)
    assert r.status_code == 400
    assert "长度" in r.json()["detail"]


def test_save_and_reproduce(client):
    draws = _synthetic_drawdowns(missing=(5, 19))
    r = client.post("/api/analyses", json=_payload(draws, name="保存核对"))
    assert r.status_code == 201, r.text
    saved = r.json()
    sid = saved["saved_id"]
    assert sid is not None
    T0, S0 = saved["transmissivity_m2_s"], saved["storativity"]

    # Stored input snapshot preserves the null gaps.
    stored_input = saved["input_json"]
    assert stored_input["drawdowns"][5] is None
    assert stored_input["drawdowns"][19] is None

    # List endpoint shows the new row.
    listing = client.get("/api/analyses").json()
    assert any(x["id"] == sid and x["name"] == "保存核对" for x in listing)

    # Retrieve the raw snapshot.
    detail = client.get(f"/api/analyses/{sid}").json()
    assert detail["input_json"]["distance"] == R_TRUE
    assert detail["result_json"]["transmissivity_m2_s"] == T0

    # One-shot reproduction: refit stored input -> identical parameters.
    again = client.post(f"/api/analyses/{sid}/refit").json()
    assert again["transmissivity_m2_s"] == T0
    assert again["storativity"] == S0
    # Reproduced points identical too (determinism).
    assert again["points"] == saved["points"]


def test_refit_unknown_id_404(client):
    assert client.post("/api/analyses/999999/refit").status_code == 404

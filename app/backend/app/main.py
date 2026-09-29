"""FastAPI application: fit Theis models, persist runs, reproduce saved runs.

The tool is an internal review aid for hydrogeologists. It performs no
permitting decisions and explicitly states the model's scope in its output.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db, init_db
from .models import Observation, Run
from .schemas import Bounds, FitRequest, FitResponse, RunSummary
from .service import run_analysis
from .synthetic import standard_clean, standard_noisy, synthetic_dataset

app = FastAPI(
    title="抽水试验降深复核（Theis 模型）",
    version="0.1.0",
    description="均质承压含水层、定流量、单一观测井的 Theis 拟合复核工具。仅供室内复核，不输出开采许可。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/demo/{kind}")
def demo_dataset(kind: str) -> dict:
    """Synthetic verification datasets shared with the test suite.

    kind = clean | noisy | unit_error. The unit_error payload intentionally
    contains the wrong distance selector so the plausibility diagnostic fires.
    """
    if kind == "clean":
        ds = standard_clean()
        return {
            "kind": kind,
            "distance": ds["true"]["r"],
            "distance_unit": "m",
            "rate": ds["true"]["Q_m3_h"],
            "rate_unit": "m3/h",
            "time_unit": "min",
            "head_unit": "m",
            "static_water_level": 12.5,
            "observations": ds["observations"],
            "truth": ds["true"],
            "note": "已知参数合成数据（无噪声）。",
        }
    if kind == "noisy":
        ds = standard_noisy()
        return {
            "kind": kind,
            "distance": ds["true"]["r"],
            "distance_unit": "m",
            "rate": ds["true"]["Q_m3_h"],
            "rate_unit": "m3/h",
            "time_unit": "min",
            "head_unit": "m",
            "static_water_level": 12.5,
            "observations": ds["observations"],
            "truth": ds["true"],
            "note": "同一参数 + 0.01 m 高斯噪声，并故意删除 2 个测点。",
        }
    if kind == "unit_error":
        import numpy as np

        from .synthetic import theis_s

        ds = standard_clean()
        r_true_m = 300.0 * 0.3048
        t_min = [1, 2, 3, 5, 8, 12, 20, 30, 45, 60, 90, 120, 180, 240, 360, 720, 1440]
        d = theis_s(
            np.array(t_min, dtype=float) * 60.0,
            ds["true"]["T"],
            ds["true"]["S"],
            r_true_m,
            ds["true"]["Q_m3_h"] / 3600.0,
        )
        return {
            "kind": kind,
            # Deliberate error: 300 ft field distance entered as 1500 "m".
            "distance": 1500.0,
            "distance_unit": "m",
            "rate": ds["true"]["Q_m3_h"],
            "rate_unit": "m3/h",
            "time_unit": "min",
            "head_unit": "m",
            "static_water_level": 12.5,
            "observations": [
                {"t": float(t), "drawdown": float(s)} for t, s in zip(t_min, d)
            ],
            "truth": {**ds["true"], "r_true_m": r_true_m},
            "note": "真实井距 300 ft（约 91.4 m），被错误录入为 1500 m。",
        }
    raise HTTPException(status_code=404, detail="unknown demo kind")


@app.post("/api/fit", response_model=FitResponse)
def fit(req: FitRequest, db: Session = Depends(get_db)) -> FitResponse:
    result = run_analysis(req)
    run_id = None
    if req.save:
        run = Run(
            project_name=req.project_name,
            distance=req.distance,
            distance_unit=req.distance_unit,
            rate=req.rate,
            rate_unit=req.rate_unit,
            time_unit=req.time_unit,
            head_unit=req.head_unit,
            static_water_level=req.static_water_level,
            level_datum=req.level_datum,
            datum_note=req.datum_note,
            bounds=req.bounds.model_dump(),
            result=result,
        )
        for idx, p in enumerate(req.observations):
            run.observations.append(
                Observation(seq=idx, t_raw=p.t, drawdown_raw=p.drawdown)
            )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
    return FitResponse(run_id=run_id, **result)


@app.get("/api/runs", response_model=list[RunSummary])
def list_runs(db: Session = Depends(get_db)) -> list[RunSummary]:
    rows = db.scalars(select(Run).order_by(Run.created_at.desc()).limit(100)).all()
    out: list[RunSummary] = []
    for r in rows:
        res = r.result or {}
        out.append(
            RunSummary(
                id=r.id,
                project_name=r.project_name,
                created_at=r.created_at.isoformat(),
                distance_m=r.distance
                if r.distance_unit == "m"
                else r.distance * 0.3048,
                rate_m3_s=r.rate,
                transmissivity_m2_s=res.get("transmissivity_m2_s"),
                storativity=res.get("storativity"),
                converged=bool(res.get("converged")),
            )
        )
    return out


def _run_to_request(run: Run) -> FitRequest:
    """Rebuild the exact FitRequest from a saved run for reproduction."""
    obs = [
        {"t": o.t_raw, "drawdown": o.drawdown_raw}
        for o in sorted(run.observations, key=lambda o: o.seq)
    ]
    return FitRequest(
        project_name=run.project_name,
        distance=run.distance,
        distance_unit=run.distance_unit,
        rate=run.rate,
        rate_unit=run.rate_unit,
        time_unit=run.time_unit,
        head_unit=run.head_unit,
        static_water_level=run.static_water_level,
        level_datum=run.level_datum,
        datum_note=run.datum_note,
        observations=obs,
        bounds=Bounds(**run.bounds),
        save=False,
    )


@app.get("/api/runs/{run_id}", response_model=FitResponse)
def get_run(run_id: int, db: Session = Depends(get_db)) -> FitResponse:
    """Return the stored fit for a saved run (deterministic reproduction)."""
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    res = dict(run.result or {})
    return FitResponse(run_id=run.id, **res)


@app.post("/api/runs/{run_id}/refit", response_model=FitResponse)
def refit_run(run_id: int, db: Session = Depends(get_db)) -> FitResponse:
    """Re-run the fit from the *saved raw input* to prove reproducibility."""
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    req = _run_to_request(run)
    result = run_analysis(req)
    # Store the recomputed result only if the algorithm version changed;
    # here we simply verify equality is possible without mutating the original.
    return FitResponse(run_id=run.id, **result)


_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=_DIST / "assets"),
        name="assets",
    )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(_DIST / "index.html")

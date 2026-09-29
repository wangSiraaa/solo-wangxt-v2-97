"""API routes: fit, save, list, retrieve, reproduce."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import Analysis, get_db
from ..demo import demo_payload
from ..schemas import (
    AnalysisDetail,
    AnalysisSummary,
    FitRequest,
    FitResponse,
)
from ..services import run_fit

router = APIRouter(prefix="/api", tags=["theis"])


@router.get("/demo/{kind}")
def demo(kind: str) -> dict:
    """Built-in synthetic verification datasets:
    exact / noisy / wrong_unit."""
    try:
        return demo_payload(kind)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown demo kind")


def _fit_or_400(req: FitRequest) -> dict:
    try:
        return run_fit(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/fit", response_model=FitResponse)
def fit_only(req: FitRequest) -> dict:
    """Fit without persisting anything."""
    return _fit_or_400(req)


@router.post("/analyses", response_model=FitResponse, status_code=201)
def save_analysis(req: FitRequest, db: Session = Depends(get_db)) -> dict:
    """Fit and persist input + result in a single row (one-shot save)."""
    payload = _fit_or_400(req)
    row = Analysis(
        name=payload["name"],
        input_json=payload["input_json"],
        result_json={k: v for k, v in payload.items() if k != "input_json"},
        transmissivity_m2_s=payload["transmissivity_m2_s"],
        storativity=payload["storativity"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    payload["saved_id"] = row.id
    return payload


@router.get("/analyses", response_model=list[AnalysisSummary])
def list_analyses(db: Session = Depends(get_db)):
    rows = db.query(Analysis).order_by(Analysis.created_at.desc()).all()
    return [
        AnalysisSummary(
            id=r.id,
            name=r.name,
            transmissivity_m2_s=r.transmissivity_m2_s,
            storativity=r.storativity,
            created_at=r.created_at.isoformat(timespec="seconds"),
        )
        for r in rows
    ]


@router.get("/analyses/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    row = db.get(Analysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return AnalysisDetail(
        id=row.id,
        name=row.name,
        input_json=row.input_json,
        result_json=row.result_json,
        created_at=row.created_at.isoformat(timespec="seconds"),
    )


@router.post("/analyses/{analysis_id}/refit", response_model=FitResponse)
def refit_analysis(analysis_id: int, db: Session = Depends(get_db)):
    """Reproduce a saved fit from its single stored input snapshot."""
    row = db.get(Analysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    req = FitRequest(**row.input_json)
    payload = _fit_or_400(req)
    payload["saved_id"] = row.id
    # Deterministic check: reproduced parameters must match the stored ones.
    stored = row.result_json
    tol_T = 1e-6 * max(1.0, abs(stored["transmissivity_m2_s"]))
    tol_S = 1e-6 * max(1.0, abs(stored["storativity"]))
    if abs(payload["transmissivity_m2_s"] - stored["transmissivity_m2_s"]) > tol_T:
        raise HTTPException(
            status_code=500,
            detail="重现拟合与已保存结果不一致（T），数据完整性异常。",
        )
    if abs(payload["storativity"] - stored["storativity"]) > tol_S:
        raise HTTPException(
            status_code=500,
            detail="重现拟合与已保存结果不一致（S），数据完整性异常。",
        )
    return payload

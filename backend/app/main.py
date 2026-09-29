"""FastAPI application entry point.

Run (dev):  uvicorn app.main:app --reload --app-dir backend
The API serves the built React bundle from ../frontend/dist when present,
so a production deployment is a single process plus PostgreSQL.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS
from .database import init_db
from .routers.analyses import router as analyses_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Theis 抽水试验降深拟合",
    version="0.1.0",
    description=(
        "均质承压含水层、恒定流量、单一观测井条件下的 Theis 模型拟合。"
        "仅供水文地质参数解释，不输出任何开采/取水许可。"
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyses_router)


@app.exception_handler(RequestValidationError)
async def _validation_as_400(request: Request, exc: RequestValidationError):
    """Surface pydantic input problems as 400 with Chinese detail text."""
    messages = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"] if x not in ("body",))
        msg = err["msg"]
        # Forward our own ValueError messages embedded by pydantic.
        ctx = err.get("ctx", {})
        if isinstance(ctx.get("error"), ValueError):
            msg = str(ctx["error"])
        messages.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(status_code=400, content={"detail": "；".join(messages)})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# --- Serve built frontend (optional; Vite dev server is used in dev) ----
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount(
        "/assets", StaticFiles(directory=_DIST / "assets"), name="assets"
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "not found"})
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")

"""Pytest fixtures: isolated SQLite database + FastAPI test client."""
from __future__ import annotations

import os
import sys

import pytest

# Point the app at an isolated in-memory-ish SQLite file BEFORE importing
# app modules.  Production deployments use PostgreSQL via DATABASE_URL;
# the ORM and JSON handling are identical across both dialects.
_TMP_DB = os.path.join(os.path.dirname(__file__), "_test_theis.db")
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    init_db()
    with TestClient(app) as c:
        yield c

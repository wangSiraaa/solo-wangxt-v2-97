"""Application configuration.

Database selection is deliberately dialect-agnostic at the ORM layer:
production uses PostgreSQL (DATABASE_URL=postgresql+psycopg2://...),
while tests and local demos can fall back to a SQLite file or
``sqlite://`` in-memory database without changing any model code.
"""
from __future__ import annotations

import os

# Default keeps the app runnable out of the box; set a real Postgres URL
# in deployment (see docker-compose.yml).
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "sqlite:///./theis_app.db"
)

# Allow the API to be contacted from the Vite dev server.
CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

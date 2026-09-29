#!/usr/bin/env bash
# Start the FastAPI backend (serves API and the built frontend at /).
set -euo pipefail
cd "$(dirname "$0")/../backend"
export LD_LIBRARY_PATH="/home/node/pg/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000

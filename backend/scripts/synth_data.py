"""Print the built-in synthetic verification datasets as JSON.

Usage (from backend/):  python scripts/synth_data.py
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from app.demo import demo_payload

if __name__ == "__main__":
    print(
        json.dumps(
            {k: demo_payload(k) for k in ("exact", "noisy", "wrong_unit")},
            ensure_ascii=False,
            indent=2,
        )
    )

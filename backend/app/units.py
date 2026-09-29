"""Unit conversion helpers.

All computations inside the application use SI units internally:

* distance r        -> metres (m)
* pumping rate Q    -> cubic metres per second (m^3/s)
* time t            -> seconds (s)
* drawdown s        -> metres (m)
* transmissivity T  -> m^2/s
* storativity S     -> dimensionless

Only the *distance* and *pumping rate* inputs are unit-bearing and
user-selectable in this version; drawdown is always entered in metres so
that the reference (baseline) water level is unambiguous.
"""
from __future__ import annotations

# Multiplicative factors that convert a displayed unit into SI (metres).
DISTANCE_TO_METRES: dict[str, float] = {
    "m": 1.0,
    "cm": 0.01,
    "ft": 0.3048,
}

# Multiplicative factors that convert a displayed rate unit into m^3/s.
RATE_TO_SI: dict[str, float] = {
    "m3/s": 1.0,
    "m3/min": 1.0 / 60.0,
    "m3/h": 1.0 / 3600.0,
    "L/s": 0.001,
    "gpm": 0.003785411784 / 60.0,  # US gallons per minute
}

TIME_TO_SECONDS: dict[str, float] = {
    "s": 1.0,
    "min": 60.0,
    "h": 3600.0,
    "d": 86400.0,
}


def distance_to_metres(value: float, unit: str) -> float:
    try:
        return value * DISTANCE_TO_METRES[unit]
    except KeyError as exc:  # pragma: no cover - guarded by pydantic
        raise ValueError(f"unsupported distance unit: {unit}") from exc


def rate_to_si(value: float, unit: str) -> float:
    try:
        return value * RATE_TO_SI[unit]
    except KeyError as exc:  # pragma: no cover
        raise ValueError(f"unsupported pumping rate unit: {unit}") from exc


def time_to_seconds(value: float, unit: str) -> float:
    try:
        return value * TIME_TO_SECONDS[unit]
    except KeyError as exc:  # pragma: no cover
        raise ValueError(f"unsupported time unit: {unit}") from exc

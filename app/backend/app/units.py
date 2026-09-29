"""Unit handling for pumping-test input.

The API receives explicit unit selectors with every numeric value so that a
wrong selector (e.g. distance entered in feet but labelled metres) is treated
as a data error the diagnostics can flag, rather than a silent conversion.
"""
from __future__ import annotations

from enum import Enum


class TimeUnit(str, Enum):
    SECOND = "s"
    MINUTE = "min"
    HOUR = "h"
    DAY = "d"


_TO_SECONDS = {
    TimeUnit.SECOND: 1.0,
    TimeUnit.MINUTE: 60.0,
    TimeUnit.HOUR: 3600.0,
    TimeUnit.DAY: 86400.0,
}


class LengthUnit(str, Enum):
    METRE = "m"
    FOOT = "ft"


_METRES_PER = {LengthUnit.METRE: 1.0, LengthUnit.FOOT: 0.3048}


class RateUnit(str, Enum):
    M3_S = "m3/s"
    M3_H = "m3/h"
    M3_D = "m3/d"
    L_S = "L/s"
    GPM_US = "gpm_us"


_RATE_TO_M3_S = {
    RateUnit.M3_S: 1.0,
    RateUnit.M3_H: 1.0 / 3600.0,
    RateUnit.M3_D: 1.0 / 86400.0,
    RateUnit.L_S: 1.0e-3,
    RateUnit.GPM_US: 0.003785411784 / 60.0,  # US gallon
}


class HeadUnit(str, Enum):
    METRE = "m"
    FOOT = "ft"


def time_to_seconds(value: float, unit: TimeUnit | str) -> float:
    return value * _TO_SECONDS[TimeUnit(unit)]


def length_to_metres(value: float, unit: LengthUnit | str) -> float:
    return value * _METRES_PER[LengthUnit(unit)]


def rate_to_m3_s(value: float, unit: RateUnit | str) -> float:
    return value * _RATE_TO_M3_S[RateUnit(unit)]


def head_to_metres(value: float, unit: HeadUnit | str) -> float:
    return value * _METRES_PER[HeadUnit(unit)]


def metres_to_head(value_m: float, unit: HeadUnit | str) -> float:
    return value_m / _METRES_PER[HeadUnit(unit)]


def seconds_to_time(value_s: float, unit: TimeUnit | str) -> float:
    return value_s / _TO_SECONDS[TimeUnit(unit)]

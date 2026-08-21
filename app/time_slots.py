from __future__ import annotations


RUSH_HOUR_SLOTS = frozenset({"commute_am", "commute_pm"})
DEFAULT_TIME_SLOT = "default"


def is_rush_hour_slot(value: object) -> bool:
    return value in RUSH_HOUR_SLOTS

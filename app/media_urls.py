from __future__ import annotations


def normalize_optional_url(value: object) -> object:
    """Normalize optional stored URLs without weakening schema validation."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    return normalized or None

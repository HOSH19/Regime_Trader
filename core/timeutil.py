"""Timezone-aware UTC helpers (avoid naive ``datetime.utcnow()``)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """Return ``datetime.now(timezone.utc)``."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Treat naive ``dt`` as UTC; convert aware values to UTC.

    Args:
        dt: Input timestamp or ``None``.

    Returns:
        UTC-normalized datetime, or ``None`` if ``dt`` is ``None``.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

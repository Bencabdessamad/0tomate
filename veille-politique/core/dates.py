"""Dates : tout est converti en Africa/Casablanca (heure légale marocaine,
y compris le passage à UTC+0 pendant le Ramadan, géré par la base tz)."""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dateutil import parser as dparser

TZ = ZoneInfo("Africa/Casablanca")


def now() -> datetime:
    return datetime.now(TZ)


def to_local(dt: datetime, naive_tz=TZ) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=naive_tz)
    return dt.astimezone(TZ)


def parse_any(value, naive_tz=TZ) -> datetime | None:
    """Parse ISO/RFC822/texte ; une date sans fuseau est supposée `naive_tz`."""
    if not value:
        return None
    if isinstance(value, datetime):
        return to_local(value, naive_tz)
    try:
        return to_local(dparser.parse(str(value)), naive_tz)
    except (ValueError, OverflowError, TypeError):
        return None


def from_struct_utc(st) -> datetime | None:
    """time.struct_time UTC (feedparser *_parsed)."""
    if not st:
        return None
    return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc).astimezone(TZ)


def window(heures: float | None, depuis: str | None) -> tuple[datetime, datetime]:
    end = now()
    if depuis:
        start = datetime.strptime(depuis, "%Y-%m-%d").replace(tzinfo=TZ)
    else:
        start = end - timedelta(hours=heures or 24)
    return start, end

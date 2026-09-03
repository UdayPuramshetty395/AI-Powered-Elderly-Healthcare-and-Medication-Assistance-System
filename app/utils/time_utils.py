"""
Time utilities — use local time (IST) for all DB timestamps.
This avoids UTC confusion in display since app runs locally.
"""
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def now_local() -> datetime:
    """Return current datetime in IST (India Standard Time)."""
    return datetime.now(IST).replace(tzinfo=None)


def format_local(dt: datetime, fmt: str = '%d %b %Y, %I:%M %p') -> str:
    """Format a datetime for display. Assumes stored as local time."""
    if dt is None:
        return '—'
    return dt.strftime(fmt)

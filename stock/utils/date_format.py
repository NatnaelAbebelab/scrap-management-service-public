from datetime import timedelta, datetime
from django.utils import timezone
import pytz

def _validate_ddmmyyyy(date_str: str) -> str:
    date_str = date_str.strip()
    if not date_str:
        raise ValueError("Date cannot be empty after normalization")

    parts = date_str.split('.')
    if len(parts) != 3:
        raise ValueError(f"Invalid date format: '{date_str}'. Use DD.MM.YYYY")

    try:
        day, month, year = map(int, parts)
        if not (1 <= day <= 31 and 1 <= month <= 12 and 1000 <= year <= 9999):
            raise ValueError
        from datetime import datetime
        datetime.strptime(date_str, "%d.%m.%Y")
    except (ValueError, OverflowError):
        raise ValueError(f"Invalid date: '{date_str}'. Must be valid DD.MM.YYYY")
    return date_str

def _default_date_range() -> tuple[str, str]:
    tz = pytz.timezone("Africa/Addis_Ababa")
    now = timezone.localtime(timezone.now(), tz)
    today = now.date()
    thirty_days_ago = today - timedelta(days=30)
    return (
        thirty_days_ago.strftime("%Y-%m-%d"),
        today.strftime("%Y-%m-%d")
    )

def parse_date(s: str):
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()
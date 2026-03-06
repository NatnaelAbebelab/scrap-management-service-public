import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def resolve_rate(rate_cache, material_type, rate_date):
    """
    Resolve the correct rate for a given material and date.

    Priority:
    1. Expired rate where created_at <= rate_date <= expired_date
    2. Active rate
    """
    try:
        material_type = material_type.lower()

        if material_type not in rate_cache:
            return None

        rates = rate_cache[material_type]

        expired_match = None
        active_match = None

        for r in rates:
            # Convert char dates safely
            created = parse_rate_date(r.created_at)
            expired = parse_rate_date(r.expired_date)

            if r.status == "expired" and created and expired:
                if created <= rate_date <= expired:
                    expired_match = r

            if r.status == "active":
                active_match = r

        return expired_match if expired_match else active_match
    except Exception as e:
        logger.error(f"Error resolving rate: {e}")
        return None

def parse_rate_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception as e:
        return None
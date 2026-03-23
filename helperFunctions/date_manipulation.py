from datetime import datetime, timedelta
def get_last_week():
    # Get today's date
    today = datetime.today()

    # Calculate the start of the last week (7 days ago from today)
    start_of_last_week = today - timedelta(days=today.weekday() + 7)
    end_of_last_week = start_of_last_week + timedelta(days=6)

    return start_of_last_week, end_of_last_week # Send it as JSON response

def normalize_date_string(date_str: str) -> str:
    """
    Accepts:
    - DD.MM.YYYY
    - YYYY-MM-DD
    Returns:
    - YYYY-MM-DD
    """
    if not date_str:
        return ""

    try:
        # Try DD.MM.YYYY
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError:
        # Try YYYY-MM-DD
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

    return date_obj.strftime("%Y-%m-%d")
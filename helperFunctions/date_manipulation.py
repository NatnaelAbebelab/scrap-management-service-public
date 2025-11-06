from datetime import datetime, timedelta
def get_last_week():
    # Get today's date
    today = datetime.today()

    # Calculate the start of the last week (7 days ago from today)
    start_of_last_week = today - timedelta(days=today.weekday() + 7)
    end_of_last_week = start_of_last_week + timedelta(days=6)

    return start_of_last_week, end_of_last_week # Send as JSON response
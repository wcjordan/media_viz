"""
Utils for handling weeks and dates for preparing the timeline chart.
"""

from datetime import datetime, timedelta
import os

# Maximum number of horizontal slots for the timeline
MAX_SLOTS = 20


def compute_week_index(entry_date: datetime, min_date: datetime) -> int:
    """
    Compute the week index for a given date relative to the minimum date.

    Args:
        entry_date: datetime representing an entry start of finish date
        min_date: Minimum date as a datetime object

    Returns:
        Week index (integer)
    """
    # If entry_date is a Sunday, adjust to the next Monday
    if entry_date.weekday() == 6:
        entry_date = entry_date + timedelta(days=1)
    delta = entry_date - min_date
    return delta.days // 7


def get_datetime(date_str: str) -> datetime:
    """
    Convert a %Y-%m-%d date string to a naive datetime object.

    Returns:
        Datetime object
    """
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=None)


def is_debug_mode() -> bool:
    """
    Check if the application is running in debug mode.

    Returns:
        True if in debug mode, False otherwise
    """
    return os.getenv("DEBUG", "false").lower() == "true"

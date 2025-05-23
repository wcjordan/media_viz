"""
Preprocessing stage to parse and load weekly records from a CSV file.
This module includes functions to parse date ranges and load records from a CSV file.
"""

import re
import logging
import calendar
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

DATE_COLUMN_NAME = ""
MONTHS_ABBR = [month.lower() for month in calendar.month_abbr[1:]]
MONTHS_FULL = [month.lower() for month in calendar.month_name[1:]]


def _parse_date_range(date_range: str, last_year: int = None) -> tuple:
    """
    Parse a date range string (e.g., "Feb 1-6" or "Dec 28-Jan 3") into start and end dates.
    Uses the passed in last_year if not present in the date_range.

    Args:
        date_range: String representing a date range
        last_year: The year to use if not specified in the date_range

    Returns:
        Tuple of (start_date, end_date, current_year) where:
            - start_date and end_date are in ISO format (YYYY-MM-DD)
            - current_year is the year used for parsing the date range
    """
    # Get the year from the date range if specificed in the format "month start_date-end_date (YYYY)"
    current_year = last_year
    year_match = re.search(r"(\d{4})", date_range)
    if year_match:
        year = int(year_match.group(1))
        date_range = date_range.replace(f"({str(year)})", "").strip()
        current_year = year

    if current_year is None:
        logger.warning("Year is required for parsing date range: %s", date_range)
        return None, None, None

    # Clean the date range string
    date_range = date_range.strip()

    # Handle various separators (-, –, —, to)
    date_range = re.sub(r"[\-–—]", "-", date_range)

    # Handle Sept by converting to Sep
    date_range = date_range.replace("Sept ", "Sep ")

    # Check if there's a range or just a single date
    if "-" in date_range:
        # Split the range
        start_str, end_str = date_range.split("-", 1)
        start_str = start_str.strip()
        end_str = end_str.strip()

        # Parse the start date
        try:
            start_date = _parse_date(start_str, current_year)
        except ValueError as e:
            logger.warning("Error parsing start date '%s': %s", start_str, e)
            return None, None, current_year

        # Parse the end date
        try:
            end_date = _parse_date(end_str, current_year, start_date.month)
        except ValueError as e:
            logger.warning("Error parsing end date '%s': %s", end_str, e)
            return None, None, current_year

        # Validate results
        invalid_result = False

        # Handle year wrap (December to January)
        if start_date.month == 12 and end_date.month == 1:
            logger.warning("Rows are not expected to cross years: '%s'", date_range)
            invalid_result = True

        # Handle case where end date is before start date
        if not invalid_result and end_date < start_date:
            logger.warning(
                "End date is unexpectedly before the start date '%s'", date_range
            )
            invalid_result = True

        if invalid_result:
            return None, None, current_year
    else:
        try:
            both_date = _parse_date(date_range, current_year)
        except ValueError as e:
            logger.warning("Error parsing date '%s': %s", date_range, e)
            return None, None, current_year
        start_date = both_date
        end_date = both_date

    # Format as ISO dates
    start_iso = start_date.strftime("%Y-%m-%d")
    end_iso = end_date.strftime("%Y-%m-%d")
    return start_iso, end_iso, current_year


def _parse_date(date_str: str, current_year: int, month_idx: int = None) -> datetime:
    """
    Parse a date string (e.g., "Jan 1") into a datetime object.
    Uses the passed in current_year.
    Args:
        date_str: String representing a date
        current_year: The year to use
        month_idx: The month index to use if not specified in the date_str.  Optional.
    Raises:
        ValueError: If the date string cannot be parsed
    Returns:
        A datetime object representing the parsed date
    """
    # Check if month is in the  date_str
    if _contains_month_abbr(date_str.lower()):
        # If there's an abbreviated month name, try to parse with the current year
        result_date = datetime.strptime(f"{date_str} {current_year}", "%b %d %Y")
    elif _contains_month_name(date_str.lower()):
        # If there's a full month name, try to parse with the current year
        result_date = datetime.strptime(f"{date_str} {current_year}", "%B %d %Y")
    elif month_idx:
        # If no month, assume it's just a day and use the month from start_str
        month = MONTHS_ABBR[month_idx - 1]
        result_date = datetime.strptime(
            f"{month} {date_str} {current_year}", "%b %d %Y"
        )
    else:
        raise ValueError("Month not found in date string")

    return result_date


def _contains_month_abbr(text: str) -> bool:
    """
    Check if the given text contains a valid month abbreviation.

    Args:
        text: The text to check.

    Returns:
        True if the text contains a valid month abbreviation, False otherwise.
    """
    lower_text = text.lower()
    # Use an space char after month to avoid false positives from full month names like September
    return any(f"{month} " in lower_text for month in MONTHS_ABBR)


def _contains_month_name(text: str) -> bool:
    """
    Check if the given text contains a valid full month name.

    Args:
        text: The text to check.

    Returns:
        True if the text contains a valid month name, False otherwise.
    """
    lower_text = text.lower()
    return any(month in lower_text for month in MONTHS_FULL)


def parse_row(row: Dict, current_year: int) -> List[Dict]:
    """
    Load and parse the specified row from the raw data.

    Args:
        row: A dictionary representing a single row from the CSV file.
        current_year: The year to use for parsing dates if not specified in the row.

    Returns:
        A tuple containing:
            - A dictionary with the parsed start and end dates, and raw notes.
            - The year for the row.
    """
    date_range = row.get(DATE_COLUMN_NAME, "").strip()
    notes = row.get("Notes", "").strip()

    # Parse the date range
    start_date, end_date, current_year = _parse_date_range(date_range, current_year)
    if start_date and end_date:
        return {
            "start_date": start_date,
            "end_date": end_date,
            "raw_notes": notes,
        }, current_year
    logger.warning("Skipping row with unparseable date range: %s", date_range)
    return None, current_year


if __name__ == "__main__":
    # Example usage
    record = parse_row(
        {"": "Jan 1-7 (2023)", "Notes": "Started The Hobbit"},
        None,
    )
    print(f"Loaded record: {record}")

"""
Preprocessing module to parse and load weekly records from a CSV file.
This module includes functions to parse date ranges and load records from a CSV file.
"""

import csv
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="preprocess.log",
    filemode="w",
)
logger = logging.getLogger(__name__)

DATE_COLUMN_NAME = ""
MONTHS = [
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]


def parse_date_range(date_range: str, last_year: int = None) -> tuple:
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

    # Check if there's a range or just a single date
    if "-" in date_range:
        # Split the range
        start_str, end_str = date_range.split("-", 1)
        start_str = start_str.strip()
        end_str = end_str.strip()

        # Parse the start date
        try:
            # Check if month is in the start string
            if any(month in start_str.lower() for month in MONTHS):
                # If there's a month, try to parse with the current year
                start_date = datetime.strptime(
                    f"{start_str} {current_year}", "%b %d %Y"
                )
            else:
                raise ValueError("Month not found in start date string")
        except (ValueError, AttributeError) as e:
            logger.warning("Error parsing start date '%s': %s", start_str, e)
            return None, None, current_year

        # Parse the end date
        try:
            # Check if month is in the end string
            if any(month in end_str.lower() for month in MONTHS):
                # If there's a month, try to parse with the current year
                end_date = datetime.strptime(f"{end_str} {current_year}", "%b %d %Y")
            else:
                # If no month, assume it's just a day and use the month from start_str
                month = (
                    re.search(
                        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
                        start_str.lower(),
                    )
                    .group(1)
                    .capitalize()
                )
                end_date = datetime.strptime(
                    f"{month} {end_str} {current_year}", "%b %d %Y"
                )

            # Handle year wrap (December to January)
            if start_date.month == 12 and end_date.month == 1:
                raise ValueError("Rows are not expected to cross years")

            # Handle case where end date is before start date (needs year increment)
            if end_date < start_date and end_date.month != 1:
                raise ValueError("End date is unexpectedly before the start date")

        except ValueError as e:
            logger.warning("Error parsing end date '%s': %s", end_str, e)
            return None, None, current_year
    else:
        logger.warning("No range found in date '%s'", date_range)
        return None, None, current_year

    # Format as ISO dates
    start_iso = start_date.strftime("%Y-%m-%d")
    end_iso = end_date.strftime("%Y-%m-%d")

    return start_iso, end_iso, current_year


def load_weekly_records(path: str) -> List[Dict]:
    """
    Load and parse the media_enjoyed.csv file.

    Args:
        path: Path to the CSV file

    Returns:
        List of dictionaries with start_date, end_date, and raw_notes
    """
    records = []
    current_year = None

    try:
        with open(path, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                date_range = row.get(DATE_COLUMN_NAME, "").strip()
                notes = row.get("Notes", "").strip()

                # Parse the date range
                start_date, end_date, current_year = parse_date_range(
                    date_range, current_year
                )
                if start_date and end_date:
                    records.append(
                        {
                            "start_date": start_date,
                            "end_date": end_date,
                            "raw_notes": notes,
                        }
                    )
                else:
                    logger.warning(
                        "Skipping row with unparseable date range: %s", date_range
                    )

    except FileNotFoundError as e:
        logger.error("File not found: %s", e)
        raise
    except PermissionError as e:
        logger.error("Permission denied: %s", e)
        raise
    except csv.Error as e:
        logger.error("CSV parsing error: %s", e)
        raise

    logger.info("Loaded %d weekly records from %s", len(records), path)
    return records


def extract_entries(record: Dict) -> List[Dict]:
    """
    Extract media entries from a weekly record's raw notes.

    Args:
        record: Dictionary containing start_date, end_date, and raw_notes

    Returns:
        List of dictionaries with raw_text, action, and week_date
    """
    entries = []

    # Get the raw notes and dates from the record
    raw_notes = record.get("raw_notes", "")
    start_date = record.get("start_date")
    end_date = record.get("end_date")

    if not raw_notes or not start_date or not end_date:
        logger.warning("Skipping record with missing data: %s", record)
        return entries

    # Split the raw notes on '&' or newlines
    raw_items = []
    for item in re.split(r"&|\n", raw_notes):
        item = item.strip()
        if item:
            raw_items.append(item)

    # Define patterns for different actions
    action_patterns = [
        (r"(?i)started(?:\s+reading|\s+playing|\s+watching)?\s+(.*)", "started"),
        (r"(?i)finished(?:\s+reading|\s+playing|\s+watching)?\s+(.*)", "finished"),
        (r"(?i)watched\s+(.*)", "watched"),
        (r"(?i)playing\s+(.*)", "playing"),
        (r"(?i)reading\s+(.*)", "reading"),
        (r"(?i)completed\s+(.*)", "completed"),
        (r"(?i)began\s+(.*)", "started"),
        (r"(?i)continuing\s+(.*)", "continuing"),
    ]

    # Process each item
    for raw_text in raw_items:
        action = None
        title = None

        # Try to match each action pattern
        for pattern, act in action_patterns:
            match = re.search(pattern, raw_text)
            if match:
                action = act
                title = match.group(1).strip()
                break

        # If no specific action was found, treat as a general mention
        if not action:
            action = "mentioned"
            title = raw_text

        # Create an entry
        entry = {
            "raw_text": raw_text,
            "action": action,
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
        }

        entries.append(entry)

    logger.info(
        "Extracted %d entries from record with dates %s to %s",
        len(entries),
        start_date,
        end_date,
    )
    return entries


if __name__ == "__main__":
    # Example usage
    weekly_records = load_weekly_records("raw_data/media_enjoyed.csv")
    print(f"Loaded {len(weekly_records)} records")

    # Extract entries from the records
    all_entries = []
    for record in weekly_records:
        entries = extract_entries(record)
        all_entries.extend(entries)

    print(f"Extracted {len(all_entries)} media entries")

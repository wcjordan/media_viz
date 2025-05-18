import csv
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='preprocess.log',
    filemode='w'
)
logger = logging.getLogger(__name__)

MONTHS = [
    'jan', 'feb', 'mar', 'apr', 'may', 'jun',
    'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
]


def parse_date_range(date_range: str, last_year: int = None) -> tuple:
    """
    Parse a date range string (e.g., "Feb 1-6" or "Dec 28-Jan 3") into start and end dates.
    Uses the passed in last_year if not present in the date_range.

    Args:
        date_range: String representing a date range
        last_year: The year to use if not specified in the date_range

    Returns:
        Tuple of (start_date, end_date) in ISO format (YYYY-MM-DD)
    """
    # Get the year from the date range if specificed in the format "month start_date-end_date (YYYY)"
    current_year = last_year
    year_match = re.search(r'(\d{4})', date_range)
    if year_match:
        year = int(year_match.group(1))
        date_range = date_range.replace(f'({str(year)})', '').strip()
        current_year = year

    if current_year is None:
        logger.warning(f"Year is required for parsing date range: {date_range}")
        return None, None, None

    # Clean the date range string
    date_range = date_range.strip()

    # Handle various separators (-, –, —, to)
    date_range = re.sub(r'[\-–—]|to', '-', date_range)

    # Check if there's a range or just a single date
    if '-' in date_range:
        # Split the range
        start_str, end_str = date_range.split('-', 1)
        start_str = start_str.strip()
        end_str = end_str.strip()

        # Parse the start date
        try:
            # Check if month is in the start string
            if any(month in start_str.lower() for month in MONTHS):
                # If there's a month, try to parse with the current year
                start_date = datetime.strptime(f"{start_str} {current_year}", "%b %d %Y")
            else:
                raise ValueError("Month not found in start date string")
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing start date '{start_str}': {e}")
            return None, None, current_year

        # Parse the end date
        try:
            # Check if month is in the start string
            if any(month in end_str.lower() for month in MONTHS):
                # If there's a month, try to parse with the current year
                end_date = datetime.strptime(f"{end_str} {current_year}", "%b %d %Y")
            else:
                # If no month, assume it's just a day and use the month from start_str
                month = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
                                   start_str.lower()).group(1).capitalize()
                end_date = datetime.strptime(f"{month} {end_str} {current_year}", "%b %d %Y")

            # Handle year wrap (December to January)
            if start_date.month == 12 and end_date.month == 1:
                raise ValueError("Rows are not expected to cross years")

            # Handle case where end date is before start date (needs year increment)
            if end_date < start_date and end_date.month != 1:
                raise ValueError("End date is unexpectedly before the start date")

        except ValueError as e:
            logger.warning(f"Error parsing end date '{end_str}': {e}")
            return None, None, current_year
    else:
        logger.warning(f"No range found in date '{date_range}'")
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
        with open(path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)

            for row in reader:
                date_range = row.get('', '').strip()
                notes = row.get('Notes', '').strip()

                # Parse the date range
                start_date, end_date, current_year = parse_date_range(date_range, current_year)
                if start_date and end_date:
                    records.append({
                        'start_date': start_date,
                        'end_date': end_date,
                        'raw_notes': notes
                    })
                else:
                    logger.warning(f"Skipping row with unparseable date range: {date_range}")

    except Exception as e:
        logger.error(f"Error loading CSV file: {e}")
        raise

    logger.info(f"Loaded {len(records)} weekly records from {path}")
    return records


if __name__ == "__main__":
    # Example usage
    records = load_weekly_records("media_enjoyed.csv")
    print(f"Loaded {len(records)} records")

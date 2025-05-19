"""
Preprocessing module to parse and load weekly records from a CSV file.
This module includes functions to parse date ranges and load records from a CSV file.
"""

import csv
import logging
from typing import List, Dict

from .media_extractor import extract_entries
from .week_extractor import parse_row


logger = logging.getLogger(__name__)


def load_weekly_records(path: str) -> List[Dict]:
    """
    Load weekly records from a CSV file.

    Args:
        path: The file path to the CSV file.

    Returns:
        A list of dictionaries representing the weekly records.
    """
    records = []
    current_year = None
    try:
        with open(path, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                record, current_year = parse_row(row, current_year)
                if record:
                    records.append(record)

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


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.WARN,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename="preprocess.log",
        filemode="w",
    )

    # Example usage
    weekly_records = load_weekly_records("preprocessing/raw_data/media_enjoyed.csv")
    print(f"Loaded {len(weekly_records)} records")

    all_entries = []
    for curr_record in weekly_records:
        all_entries.extend(extract_entries(curr_record))
    print(f"Extracted {len(all_entries)} entries")

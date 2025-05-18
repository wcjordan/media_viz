"""
Module to extract media entries from the Notes column of a weekly record.
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def extract_entries(record: Dict) -> List[Dict]:
    """
    Extract media entries from a weekly record's raw notes.

    Args:
        record: Dictionary containing start_date, end_date, and raw_notes

    Returns:
        List of dictionaries with title, action, and date
    """
    entries = []

    # Get the raw notes and dates from the record
    raw_notes = record.get("raw_notes", "")
    start_date = record.get("start_date")
    end_date = record.get("end_date")

    if not raw_notes or not start_date or not end_date:
        logger.warning("Skipping record with missing data: %s", record)
        return entries

    # Split the raw notes on newlines to process each line separately
    for line in raw_notes.splitlines():
        line = line.strip()
        entries.extend(_extract_entries_from_line(line, start_date))

    logger.info(
        "Extracted %d entries from record with dates %s to %s",
        len(entries),
        start_date,
        end_date,
    )
    return entries


def _extract_entries_from_line(line: str, start_date: str) -> List[Dict]:
    """
    Extract media entries from a weekly record's raw notes.
    This helper method handles the extraction from a single line of the notes.

    Args:
        line: String containing a single line from the Notes
        start_date: The start date of the week

    Returns:
        List of dictionaries with title, action, and date
    """
    entries = []

    # Split the line to extract the action from the items
    tokens = line.split()
    if len(tokens) < 2:
        logger.warning("Skipping line with insufficient tokens: %s", line)
        return entries

    action = tokens[0].lower()
    if action not in ("finished", "played", "read", "started", "watched"):
        raise ValueError(f"Invalid action '{action}' in line: {line}")

    # Split the entities on '&' or newlines
    entities = " ".join(tokens[1:])
    for title in entities.split("&"):
        title = title.strip()
        if title:
            if action in ("finished", "started"):
                entry = {
                    "action": action,
                    "title": title,
                    "date": start_date,
                }
                entries.append(entry)
            else:
                for sub_action in ("finished", "started"):
                    entry = {
                        "action": sub_action,
                        "title": title,
                        "date": start_date,
                    }
                    entries.append(entry)
    return entries


if __name__ == "__main__":
    # Example usage
    curr_entries = extract_entries(
        {
            "start_date": "2023-01-01",
            "end_date": "2023-01-07",
            "raw_notes": "Started The Hobbit",
        }
    )

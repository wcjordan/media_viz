"""
Preprocessing module to parse and load weekly records from a CSV file.
This module includes functions to parse date ranges and load records from a CSV file.
"""

import csv
import json
import logging
from typing import List, Dict

from .media_extractor import RANGE_VERBS, extract_entries
from .week_extractor import parse_row
from .media_tagger import apply_tagging, get_media_db_api_calls


logger = logging.getLogger(__name__)


def _load_weekly_records(path: str) -> List[Dict]:
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


def _group_entries(individual_entries):
    """
    Group individual media entries by title.

    Args:
        individual_entries: List of individual media entry dictionaries.

    Returns:
        Dictionary mapping titles to their grouped entry data.
    """
    grouped_entries = {}
    for entry in individual_entries:
        title = entry.get("title", "")
        if not title:
            logger.warning("Entry missing title, skipping: %s", entry)
            continue

        if title not in grouped_entries:
            grouped_entries[title] = {
                "title": title,
                "started_dates": [],
                "finished_dates": [],
            }

        # Add dates to the appropriate list
        action = entry.get("action", "")
        if action not in RANGE_VERBS:
            logger.warning("Unknown action '%s' for entry: %s", action, entry)
            continue

        date = entry.get("date", "")
        if action == "started" and date not in grouped_entries[title]["started_dates"]:
            grouped_entries[title]["started_dates"].append(date)
        elif (
            action == "finished"
            and date not in grouped_entries[title]["finished_dates"]
        ):
            grouped_entries[title]["finished_dates"].append(date)

    return list(grouped_entries.values())


def process_and_save(
    input_csv: str, output_json: str, hints_path: str = None, limit: int = None
) -> Dict:
    """
    Process the input CSV file and save the results to a JSON file.

    Args:
        input_csv: Path to the input CSV file.
        output_json: Path to the output JSON file.
        hints_path: Path to the hints YAML file. Optional.
        limit: Maximum number of entries to process. Optional.

    Returns:
        Dictionary with statistics about the processing.
    """
    # Load weekly records
    weekly_records = _load_weekly_records(input_csv)
    logger.info("Loaded %d weekly records from %s", len(weekly_records), input_csv)

    # Extract media entries
    individual_entries = []
    for curr_record in weekly_records:
        individual_entries.extend(extract_entries(curr_record))
    logger.info("Extracted %d media entries", len(individual_entries))

    # Group entries to avoid multiple tagging calls for the same title
    grouped_entries = _group_entries(individual_entries)

    # Apply tagging
    if limit is not None:
        grouped_entries = grouped_entries[:limit]
        logger.warning("Limited to %d entries", limit)
    tagged_entries = apply_tagging(grouped_entries, hints_path)
    logger.info("Tagged %d media entries", len(tagged_entries))

    # Calculate statistics
    stats = calculate_statistics(tagged_entries)

    # Save to JSON
    try:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(tagged_entries, f, indent=2)
        logger.info("Saved %d entries to %s", len(tagged_entries), output_json)
    except IOError as e:
        logger.error("Error saving to JSON file: %s", e)
        raise

    return stats


def calculate_statistics(entries: List[Dict]) -> Dict:
    """
    Calculate statistics about the processed entries.

    Args:
        entries: List of processed media entries.

    Returns:
        Dictionary with statistics.
    """
    stats = {
        "total_entries": len(entries),
        "by_type": {},
        "low_confidence": 0,
    }

    for entry in entries:
        tagged_entry = entry.get("tagged", {})
        # Count by media type
        media_type = tagged_entry.get("type", "Unknown")
        stats["by_type"][media_type] = stats["by_type"].get(media_type, 0) + 1

        # Count low confidence entries
        if tagged_entry.get("confidence", 0) < 0.5:
            stats["low_confidence"] += 1

    return stats


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.WARN,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename="preprocessing/processed_data/preprocess.log",
        filemode="w",
    )

    # Process and save
    final_stats = process_and_save(
        "preprocessing/raw_data/media_enjoyed.csv",
        "preprocessing/processed_data/media_entries.json",
        limit=20,
    )

    # Print statistics
    print(f"Processed {final_stats['total_entries']} media entries:")
    print(f"  By type: {final_stats['by_type']}")
    print(f"  Low confidence: {final_stats['low_confidence']}")
    print("Count of API calls to the media databases.")
    for db_api, count in get_media_db_api_calls().items():
        print(f"  {db_api}: {count} API calls")

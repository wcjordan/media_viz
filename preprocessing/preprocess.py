"""
Preprocessing module to parse and load weekly records from a CSV file.
This module includes functions to parse date ranges and load records from a CSV file.
"""

import csv
import json
import logging
from typing import List, Dict

from .media_extractor import extract_entries
from .week_extractor import parse_row
from .media_tagger import apply_tagging


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


def process_and_save(input_csv: str, output_json: str, hints_path: str = None) -> Dict:
    """
    Process the input CSV file and save the results to a JSON file.

    Args:
        input_csv: Path to the input CSV file.
        output_json: Path to the output JSON file.
        hints_path: Path to the hints YAML file. Optional.

    Returns:
        Dictionary with statistics about the processing.
    """
    # Load weekly records
    weekly_records = load_weekly_records(input_csv)
    logger.info("Loaded %d weekly records from %s", len(weekly_records), input_csv)

    # Extract media entries
    all_entries = []
    for curr_record in weekly_records:
        all_entries.extend(extract_entries(curr_record))
    logger.info("Extracted %d media entries", len(all_entries))

    # Apply tagging
    tagged_entries = apply_tagging(all_entries, hints_path)
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
        "start_only": 0,
        "finish_only": 0,
        "completed": 0,
        "low_confidence": 0,
        "with_warnings": 0,
        "hint_applied": 0,
    }

    for entry in entries:
        # Count by media type
        media_type = entry.get("type", "Unknown")
        stats["by_type"][media_type] = stats["by_type"].get(media_type, 0) + 1

        # Count entries by status
        if entry.get("action") == "started" and "finish_date" not in entry:
            stats["start_only"] += 1
        elif entry.get("action") == "finished" and "start_date" not in entry:
            stats["finish_only"] += 1
        elif "start_date" in entry and "finish_date" in entry:
            stats["completed"] += 1

        # Count low confidence entries
        if entry.get("confidence", 0) < 0.5:
            stats["low_confidence"] += 1

        # Count entries with warnings
        if entry.get("warnings", []):
            stats["with_warnings"] += 1

        # Count entries with hints applied
        if entry.get("confidence", 0) == 1.0:
            stats["hint_applied"] += 1

    return stats


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.WARN,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename="preprocess.log",
        filemode="w",
    )

    # Process and save
    final_stats = process_and_save(
        "preprocessing/raw_data/media_enjoyed.csv", "preprocessing/media_entries.json"
    )

    # Print statistics
    print(f"Processed {final_stats['total_entries']} media entries:")
    print(f"  By type: {final_stats['by_type']}")
    print(f"  Start only: {final_stats['start_only']}")
    print(f"  Finish only: {final_stats['finish_only']}")
    print(f"  Completed: {final_stats['completed']}")
    print(f"  Low confidence: {final_stats['low_confidence']}")
    print(f"  With warnings: {final_stats['with_warnings']}")
    print(f"  Hint applied: {final_stats['hint_applied']}")

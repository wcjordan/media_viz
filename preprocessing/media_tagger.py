"""
Preprocessing stage to tag media entries with metadata from external APIs.
This module includes functions to load hints from YAML and query external APIs.
"""

import operator
import os
import logging
from typing import Dict, List, Tuple, Optional
import yaml

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_HINTS_PATH = os.path.join(os.path.dirname(__file__), "hints.yaml")


def _load_hints(hints_path: str = DEFAULT_HINTS_PATH) -> Dict:
    """
    Load hints from a YAML file for manual overrides.

    Args:
        hints_path: Path to the hints YAML file.

    Returns:
        Dictionary containing hints for media entries.
    """
    if not os.path.exists(hints_path):
        logger.warning(
            "Hints file not found at %s. No manual overrides will be applied.",
            hints_path,
        )
        return {}

    try:
        with open(hints_path, "r", encoding="utf-8") as file:
            hints = yaml.safe_load(file)
            if not hints:
                return {}
            logger.info("Loaded %d hints from %s", len(hints), hints_path)
            return hints
    except (yaml.YAMLError, IOError) as e:
        logger.error("Error loading hints file: %s", e)
        return {}


def _query_tmdb(title: str) -> Tuple[Optional[str], Optional[Dict], float]:
    """
    Query The Movie Database (TMDB) API for movie and TV show metadata.

    Args:
        title: The title of the media to query.

    Returns:
        List of dictionaries with metadata for each entry:
            - canonical_title is the official title from TMDB
            - type is the type of media (Movie, TV Show, etc.)
            - tags is a dictionary containing tags for genre, mood, etc.
            - confidence is a float between 0 and 1 indicating match confidence
            - source is the source of the metadata (e.g., "tmdb")
    """
    # This is a stub implementation
    # In a real implementation, this would make API calls to TMDB
    logger.info("Querying TMDB for title: %s", title)

    # Simulate API call
    api_key = os.environ.get("TMDB_API_KEY")
    if not api_key:
        logger.warning("TMDB_API_KEY not found in environment variables")
        return None, None, 0.0

    # Mock response - would be replaced with actual API call
    return [
        {
            "canonical_title": title,
            "type": "Movie",
            "tags": {"genre": ["Drama"]},
            "confidence": 0.8,
            "source": "tmdb",
        }
    ]


def _query_igdb(title: str) -> Tuple[Optional[str], Optional[Dict], float]:
    """
    Query the Internet Game Database (IGDB) API for video game metadata.

    Args:
        title: The title of the game to query.

    Returns:
        List of dictionaries with metadata for each entry:
            - canonical_title is the official title from IGDB
            - type is the type of media (Movie, TV Show, etc.)
            - tags is a dictionary containing tags for genre, mood, etc.
            - confidence is a float between 0 and 1 indicating match confidence
            - source is the source of the metadata (e.g., "igdb")
    """
    # This is a stub implementation
    # In a real implementation, this would make API calls to IGDB
    logger.info("Querying IGDB for title: %s", title)

    # Simulate API call
    api_key = os.environ.get("IGDB_API_KEY")
    if not api_key:
        logger.warning("IGDB_API_KEY not found in environment variables")
        return None, None, 0.0

    # Mock response - would be replaced with actual API call
    return [
        {
            "canonical_title": title,
            "type": "Game",
            "tags": {"platform": ["PC"], "genre": ["RPG"]},
            "confidence": 0.7,
            "source": "igdb",
        }
    ]


def _query_openlibrary(title: str) -> Tuple[Optional[str], Optional[Dict], float]:
    """
    Query the Open Library API for book metadata.

    Args:
        title: The title of the book to query.

    Returns:
        List of dictionaries with metadata for each entry:
            - canonical_title is the official title from Open Library
            - type is the type of media (Movie, TV Show, etc.)
            - tags is a dictionary containing tags for genre, mood, etc.
            - confidence is a float between 0 and 1 indicating match confidence
            - source is the source of the metadata (e.g., "openlibrary")
    """
    # This is a stub implementation
    # In a real implementation, this would make API calls to Open Library
    logger.info("Querying Open Library for title: %s", title)

    # Simulate API call
    api_key = os.environ.get("OPENLIBRARY_API_KEY")
    if not api_key:
        logger.warning("OPENLIBRARY_API_KEY not found in environment variables")
        return None, None, 0.0

    # Mock response - would be replaced with actual API call
    return [
        {
            "canonical_title": title,
            "type": "Book",
            "tags": {"genre": ["Fiction"]},
            "confidence": 0.6,
            "source": "openlibrary",
        }
    ]


def _combine_votes(
    entry: Dict, api_hits: List[Dict], hint: Optional[Dict] = None
) -> Dict:
    """
    Combine votes from hints and API hits.
    Args:
        entry: The original media entry.
        api_hits: List of dictionaries with metadata from API calls.
        hint: Optional dictionary with metadata from hints.
    Returns:
        Dictionary copied from the past in entry and modified with the highest confidence API data and hints.
        Includes fields:
        - canonical_title: The official title from the API
        - type: The type of media (Movie, TV Show, etc.)
        - tags: A dictionary containing tags for genre, mood, etc.
        - confidence: A float between 0 and 1 indicating match confidence
        - source: The source of the metadata (e.g., "tmdb", "igdb", "openlibrary")
    """
    tagged_entry = entry.copy()

    # Apply the hint if available
    if hint:
        tagged_entry.update(hint)

    # If no API hits were found, fallback as best possible
    if not api_hits:
        if "canonical_title" not in tagged_entry:
            logger.warning("No API hits found for entry: %s", entry)
            tagged_entry["canonical_title"] = tagged_entry.get("title")

        if "type" not in tagged_entry:
            tagged_entry["type"] = "Other / Unknown"

        tagged_entry["tags"] = {}
        tagged_entry["confidence"] = 0.1
        tagged_entry["source"] = "fallback"
        return tagged_entry

    best_api_hit = api_hits[0]
    if len(api_hits) > 1:
        confidence_list = sorted([hit["confidence"] for hit in api_hits], reverse=True)
        if confidence_list[0] - confidence_list[1] < 0.1:
            logger.warning(
                "Multiple API hits with close confidence for %s. %s",
                entry,
                ", ".join(str(hit) for hit in api_hits),
            )

        best_api_hit = max(api_hits, key=operator.itemgetter("confidence"))

    # Combine the best API hit with the entry
    if "canonical_title" not in tagged_entry:
        tagged_entry["canonical_title"] = best_api_hit.get("canonical_title")
    if "type" not in tagged_entry:
        tagged_entry["type"] = best_api_hit.get("type")
    tagged_entry["tags"] = {**best_api_hit.get("tags", {}), **entry.get("tags", {})}
    tagged_entry["confidence"] = best_api_hit.get("confidence")
    tagged_entry["source"] = best_api_hit.get("source")
    return tagged_entry


def apply_tagging(
    entries: List[Dict], hints_path: str = DEFAULT_HINTS_PATH
) -> List[Dict]:
    """
    Apply tagging to media entries using hints and API calls.

    Args:
        entries: List of dictionaries representing media entries.
        hints_path: Path to the hints YAML file.

    Returns:
        List of dictionaries with added metadata: canonical_title, type, tags, confidence.
    """
    hints = _load_hints(hints_path)
    tagged_entries = []

    for entry in entries:
        title = entry.get("title", "")
        if not title:
            logger.warning("Entry missing title, skipping tagging: %s", entry)
            tagged_entries.append(entry)
            continue

        # Apply hints if available
        hint = None
        for hint_key, hint_data in hints.items():
            if hint_key.lower() in title.lower():
                logger.info("Applying hint for '%s' to entry '%s'", hint_key, entry)
                title = hint_data.get("canonical_title", title)
                hint = {
                    "canonical_title": title,
                    "type": hint_data["type"],
                    "tags": hint_data.get("tags", {}),
                }
                break

        api_hits = []
        api_hits.extend(_query_tmdb(title))
        api_hits.extend(_query_igdb(title))
        api_hits.extend(_query_openlibrary(title))

        # Combine votes from hints and API hits
        tagged_entry = _combine_votes(entry, api_hits, hint)
        if tagged_entry["confidence"] < 0.5:
            logger.warning("Low confidence match for entry: %s", tagged_entry)
        tagged_entries.append(tagged_entry)

    logger.info("Tagged %d entries with metadata", len(tagged_entries))
    return tagged_entries


if __name__ == "__main__":
    # Example usage
    sample_entries = [
        {"title": "The Hobbit", "action": "started", "date": "2023-01-01"},
        {"title": "Elden Ring", "action": "finished", "date": "2023-02-15"},
    ]

    tagged = apply_tagging(sample_entries)
    for curr_entry in tagged:
        print(f"Tagged entry: {curr_entry}")

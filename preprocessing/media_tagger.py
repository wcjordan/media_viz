"""
Preprocessing stage to tag media entries with metadata from external APIs.
This module includes functions to load hints from YAML and query external APIs.
"""

import os
import logging
from typing import Dict, List, Tuple, Optional
import yaml

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_HINTS_PATH = os.path.join(os.path.dirname(__file__), "hints.yaml")


def load_hints(hints_path: str = DEFAULT_HINTS_PATH) -> Dict:
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


def query_tmdb(title: str) -> Tuple[Optional[str], Optional[Dict], float]:
    """
    Query The Movie Database (TMDB) API for movie and TV show metadata.

    Args:
        title: The title of the media to query.

    Returns:
        Tuple of (canonical_title, metadata, confidence) where:
            - canonical_title is the official title from TMDB
            - metadata is a dictionary containing type, genre, etc.
            - confidence is a float between 0 and 1 indicating match confidence
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
    return title, {"type": "Movie", "tags": {"genre": ["Drama"]}}, 0.8


def query_igdb(title: str) -> Tuple[Optional[str], Optional[Dict], float]:
    """
    Query the Internet Game Database (IGDB) API for video game metadata.

    Args:
        title: The title of the game to query.

    Returns:
        Tuple of (canonical_title, metadata, confidence) where:
            - canonical_title is the official title from IGDB
            - metadata is a dictionary containing platform, genre, etc.
            - confidence is a float between 0 and 1 indicating match confidence
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
    return title, {"type": "Game", "tags": {"platform": ["PC"], "genre": ["RPG"]}}, 0.7


def query_openlibrary(title: str) -> Tuple[Optional[str], Optional[Dict], float]:
    """
    Query the Open Library API for book metadata.

    Args:
        title: The title of the book to query.

    Returns:
        Tuple of (canonical_title, metadata, confidence) where:
            - canonical_title is the official title from Open Library
            - metadata is a dictionary containing author, genre, etc.
            - confidence is a float between 0 and 1 indicating match confidence
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
    return title, {"type": "Book", "tags": {"genre": ["Fiction"]}}, 0.6


def guess_media_type(title: str) -> str:
    """
    Make a best guess at the media type based on the title.
    This is a fallback when API calls fail or aren't available.

    Args:
        title: The title of the media.

    Returns:
        A string representing the guessed media type: "Movie", "TV", "Game", or "Book".
    """
    # This is a very simple heuristic and would be improved in a real implementation
    lower_title = title.lower()

    # Check for common video game indicators
    if any(term in lower_title for term in ["game", "played", "gaming"]):
        return "Game"

    # Check for common TV show indicators
    if any(
        term in lower_title for term in ["season", "episode", "tv", "show", "series"]
    ):
        return "TV"

    # Check for common book indicators
    if any(term in lower_title for term in ["book", "novel", "read"]):
        return "Book"

    # Default to Movie if no other indicators
    return "Movie"


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
    hints = load_hints(hints_path)
    tagged_entries = []

    for entry in entries:
        title = entry.get("title", "")
        if not title:
            logger.warning("Entry missing title, skipping tagging: %s", entry)
            tagged_entries.append(entry)
            continue

        # Start with a copy of the original entry
        tagged_entry = entry.copy()

        # Apply hints if available
        hint_applied = False
        for hint_key, hint_data in hints.items():
            if hint_key.lower() in title.lower():
                logger.info("Applying hint for '%s' to entry '%s'", hint_key, title)
                tagged_entry["canonical_title"] = hint_data.get(
                    "canonical_title", title
                )
                tagged_entry["type"] = hint_data.get("type")
                tagged_entry["tags"] = hint_data.get("tags", {})
                tagged_entry["confidence"] = 1.0  # Hints have perfect confidence
                hint_applied = True
                break

        if hint_applied:
            tagged_entries.append(tagged_entry)
            continue

        # If no hint, try API calls based on guessed media type
        media_type = guess_media_type(title)
        canonical_title = None
        metadata = None
        confidence = 0.0

        if media_type in ("Movie", "TV"):
            canonical_title, metadata, confidence = query_tmdb(title)
        elif media_type == "Game":
            canonical_title, metadata, confidence = query_igdb(title)
        elif media_type == "Book":
            canonical_title, metadata, confidence = query_openlibrary(title)

        if canonical_title and metadata:
            tagged_entry["canonical_title"] = canonical_title
            tagged_entry["type"] = metadata.get("type", media_type)
            tagged_entry["tags"] = metadata.get("tags", {})
            tagged_entry["confidence"] = confidence
        else:
            # Fallback if API calls fail
            tagged_entry["canonical_title"] = title
            tagged_entry["type"] = media_type
            tagged_entry["tags"] = {}
            tagged_entry["confidence"] = 0.1  # Low confidence for guesses
            tagged_entry["warnings"] = tagged_entry.get("warnings", []) + [
                "Failed to fetch metadata from APIs"
            ]

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

"""
Preprocessing stage to tag media entries with metadata from external APIs.
This module includes functions to apply tagging with metadata from APIs and hints.
"""

import operator
import logging
import re
from typing import Dict, List, Optional

from preprocessing.media_apis import query_tmdb, query_igdb, query_openlibrary
from preprocessing.utils import load_hints

logger = logging.getLogger(__name__)


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
        - poster_path is the URL to the media's poster image
        - type: The type of media (Movie, TV Show, etc.)
        - tags: A dictionary containing tags for genre, mood, etc.
        - confidence: A float between 0 and 1 indicating match confidence
        - source: The source of the metadata (e.g., "tmdb", "igdb", "openlibrary")
    """
    tagged_entry = entry.copy()

    # Apply the hint if available
    if hint:
        tagged_entry.update(hint)
        api_hits = [hit for hit in api_hits if hit["type"] == hint["type"]]

    # If no API hits were found, fallback as best possible
    if not api_hits:
        if "canonical_title" not in tagged_entry:
            logger.warning("No API hits found for entry: %s", entry)
            tagged_entry["canonical_title"] = tagged_entry.get("title")

        if "type" not in tagged_entry:
            tagged_entry["type"] = "Other / Unknown"

        if "tags" not in tagged_entry:
            tagged_entry["tags"] = {}

        tagged_entry["confidence"] = 0.1
        tagged_entry["source"] = "fallback"
        return tagged_entry

    # Sort API hits by confidence so we can check how close the to matches are
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
    tagged_entry["tags"] = {
        **best_api_hit.get("tags", {}),
        **tagged_entry.get("tags", {}),
    }
    tagged_entry["confidence"] = best_api_hit.get("confidence")
    tagged_entry["poster_path"] = best_api_hit.get("poster_path")
    tagged_entry["source"] = best_api_hit.get("source")
    return tagged_entry


def _tag_entry(entry: Dict, hints: Dict) -> Dict:
    """
    Process a single media entry to extract relevant information.

    Args:
        entry: A dictionary representing a media entry.
        hints: A dictionary containing hints for tagging.

    Returns:
        A dictionary with the entry tagged with additional metadata: canonical_title, type, tags, confidence.
        Returns None if the entry is not valid.
    """
    title = entry.get("title", "")
    if not title:
        logger.warning("Entry missing title, skipping tagging: %s", entry)
        return None

    # Remove and re-add any season data.
    season_match = re.search(r"(.*)(s\d{1,2})\s*(e\d{1,2})?\s*", title, re.IGNORECASE)
    if season_match:
        title = season_match.group(1).strip()
        entry["season"] = season_match.group(2).lower()
        entry["type"] = "TV Show"
        logger.info("Extracted season from title: %s", entry)

    # Apply hints if available
    hint = None
    for hint_key, hint_data in hints.items():
        if hint_key == title:
            logger.info("Applying hint for '%s' to entry '%s'", hint_key, entry)
            hint = hint_data
            break

    api_hits = []
    types_to_query = ["Movie", "TV Show", "Game", "Book"]
    # If hint specifies the type, only query the appropriate database
    if "type" in entry:
        types_to_query = [entry["type"]]
    elif hint and "type" in hint:
        types_to_query = [hint["type"]]
    if "Movie" in types_to_query:
        api_hits.extend(query_tmdb("movie", title))
    if "TV Show" in types_to_query:
        api_hits.extend(query_tmdb("tv", title))
    if "Game" in types_to_query:
        api_hits.extend(query_igdb(title))
    if "Book" in types_to_query:
        api_hits.extend(query_openlibrary(title))

    # Combine votes from hints and API hits
    tagged_entry = _combine_votes(entry, api_hits, hint)
    if tagged_entry["confidence"] < 0.5:
        logger.warning("Low confidence match for entry: %s", tagged_entry)

    if entry.get("season"):
        # If we have a season, add it to the canonical title
        tagged_entry["canonical_title"] = (
            f"{tagged_entry['canonical_title']} {entry['season']}"
        )
        logger.info(
            "Added season to canonical title: %s", tagged_entry["canonical_title"]
        )
    return tagged_entry


def apply_tagging(entries: List[Dict], hints_path: Optional[str] = None) -> List[Dict]:
    """
    Apply tagging to media entries using hints and API calls.

    Args:
        entries: List of dictionaries representing media entries.
        hints_path: Path to the hints YAML file. Optional.

    Returns:
        List of dictionaries with added metadata: canonical_title, type, tags, confidence.
    """
    hints = load_hints(hints_path)
    tagged_entries = [_tag_entry(entry, hints) for entry in entries]
    tagged_entries = [entry for entry in tagged_entries if entry is not None]

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

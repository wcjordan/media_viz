"""
Preprocessing stage to tag media entries with metadata from external APIs.
This module includes functions to apply tagging with metadata from APIs and hints.
"""

import copy
import logging
import re
from typing import Dict, List, Optional

from preprocessing.media_apis import query_tmdb, query_igdb, query_openlibrary
from preprocessing.utils import load_hints

logger = logging.getLogger(__name__)

# Cache for API query results to avoid redundant calls
QUERY_CACHE = {}
MEDIA_DB_API_CALL_COUNTS = {}


def get_media_db_api_calls() -> Dict:
    """
    Get the number of API calls made to media databases.
    Returns:
        The number of API calls made by type.
    """
    return MEDIA_DB_API_CALL_COUNTS


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
        tagged_entry["confidence"] = 0.5
        tagged_entry["source"] = "hint"
        api_hits = [hit for hit in api_hits if hit["type"] == hint["type"]]

    # If no API hits were found, fallback as best possible
    if not api_hits:
        if "canonical_title" not in tagged_entry:
            logger.warning("No API hits found for entry: %s", entry)
            tagged_entry["canonical_title"] = tagged_entry.get("title")
            tagged_entry["confidence"] = 0.1
            tagged_entry["source"] = "fallback"

        if "type" not in tagged_entry:
            tagged_entry["type"] = "Other / Unknown"
            tagged_entry["confidence"] = 0.1
            tagged_entry["source"] = "fallback"

        if "tags" not in tagged_entry:
            tagged_entry["tags"] = {}

        return tagged_entry

    # Sort API hits by confidence so we can check how close the to matches are
    if len(api_hits) > 1:
        api_hits.sort(key=lambda x: x["confidence"], reverse=True)
        if api_hits[0]["confidence"] - api_hits[1]["confidence"] < 0.1:
            logger.warning(
                "Multiple API hits with close confidence for %s.\n\t%s",
                entry,
                ",\n\t".join(str(hit) for hit in api_hits),
            )

    best_api_hit = api_hits[0]

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


def _query_with_cache(media_type: str, title: str) -> List[Dict]:
    """
    Query the appropriate API with caching to avoid redundant calls.

    Args:
        media_type: The type of media to query ("movie", "tv", "game", "book")
        title: The title to search for

    Returns:
        List of API hits
    """
    cache_key = (title.lower(), media_type)
    if cache_key in QUERY_CACHE:
        logger.info("Using cached result for %s: %s", media_type, title)
        return QUERY_CACHE[cache_key]

    MEDIA_DB_API_CALL_COUNTS[media_type] = (
        MEDIA_DB_API_CALL_COUNTS.get(media_type, 0) + 1
    )

    # Query the appropriate API
    results = []
    if media_type == "movie":
        results = query_tmdb("movie", title)
    elif media_type == "tv":
        results = query_tmdb("tv", title)
    elif media_type == "game":
        results = query_igdb(title)
    elif media_type == "book":
        results = query_openlibrary(title)

    # Cache the results
    QUERY_CACHE[cache_key] = results
    return results


def _tag_entry(title: str, hints: Dict) -> Dict:
    """
    Process a single media entry to extract relevant information.

    Args:
        title: The title of the media entry.
        hints: A dictionary containing hints for tagging.

    Returns:
        A dictionary with the entry tagged with additional metadata: canonical_title, type, tags, confidence.
        Returns None if the entry is not valid.
    """
    # Remove and re-add any season data.
    entry = {"title": title}
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
            title = hint_data.get("canonical_title", title)
            hint = hint_data
            break

    api_hits = []
    types_to_query = ["Movie", "TV Show", "Game", "Book"]
    # If hint specifies the type, only query the appropriate database
    if "type" in entry:
        types_to_query = [entry["type"]]
    elif hint and "type" in hint:
        types_to_query = [hint["type"]]

    # Query APIs with caching
    if "Movie" in types_to_query:
        api_hits.extend(_query_with_cache("movie", title))
    if "TV Show" in types_to_query:
        api_hits.extend(_query_with_cache("tv", title))
    if "Game" in types_to_query:
        api_hits.extend(_query_with_cache("game", title))
    if "Book" in types_to_query:
        api_hits.extend(_query_with_cache("book", title))

    # Combine votes from hints and API hits
    tagged_entry = _combine_votes(entry, api_hits, hint)
    if tagged_entry["confidence"] < 0.5 and not hint:
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


def _combine_similar_entries(tagged_entries: List[Dict]) -> List[Dict]:
    """
    Combine similar entries based on canonical title and type.
    Args:
        tagged_entries: List of dictionaries with tagged entries.
    Returns:
        List of dictionaries where duplicate entries have been combined.
    """
    canonical_groups = {}
    for entry in tagged_entries:
        tagged_entry = entry.get("tagged", {})
        canonical_key = (
            tagged_entry.get("canonical_title", ""),
            tagged_entry.get("type", ""),
        )
        if canonical_key not in canonical_groups:
            canonical_groups[canonical_key] = []
        canonical_groups[canonical_key].append(entry)

    final_entries = []
    for key, entries in canonical_groups.items():
        if len(entries) == 1:
            final_entries.append(
                {
                    "canonical_title": key[0],
                    "tagged": copy.deepcopy(entries[0].get("tagged")),
                    "original_titles": [entries[0].get("title")],
                    "started_dates": entries[0].get("started_dates"),
                    "finished_dates": entries[0].get("finished_dates"),
                }
            )
        else:
            # Multiple entries with the same canonical title and type
            combined_entry = {
                "canonical_title": key[0],
                "tagged": copy.deepcopy(entries[0].get("tagged")),
                "original_titles": [],
                "started_dates": [],
                "finished_dates": [],
            }

            combined_entry["original_titles"] = [e.get("title", "") for e in entries]

            # Combine started and finished dates
            started_dates = set()
            finished_dates = set()
            for e in entries:
                started_dates.update(e.get("started_dates", []))
                finished_dates.update(e.get("finished_dates", []))

            combined_entry["started_dates"] = sorted(list(started_dates))
            combined_entry["finished_dates"] = sorted(list(finished_dates))

            # Check for inconsistencies in tags or poster_path
            for next_entry in entries[1:]:
                if next_entry.get("tags") != combined_entry.get("tags"):
                    logger.warning(
                        "Inconsistent tags for entries with canonical_title '%s' and type '%s'. Discarding tags: %s",
                        key[0],
                        key[1],
                        next_entry.get("tags"),
                    )
                if next_entry.get("poster_path") != combined_entry.get("poster_path"):
                    logger.warning(
                        (
                            "Inconsistent poster_path for entries with canonical_title '%s' and type '%s'. Discarding "
                            "poster_path: %s"
                        ),
                        key[0],
                        key[1],
                        next_entry.get("poster_path"),
                    )
                if next_entry.get("confidence") != combined_entry.get("confidence"):
                    logger.warning(
                        (
                            "Inconsistent confidence for entries with canonical_title '%s' and type '%s'. Discarding "
                            "confidence: %s"
                        ),
                        key[0],
                        key[1],
                        next_entry.get("confidence"),
                    )
                if next_entry.get("source") != combined_entry.get("source"):
                    logger.warning(
                        (
                            "Inconsistent source for entries with canonical_title '%s' and type '%s'. Discarding "
                            "source: %s"
                        ),
                        key[0],
                        key[1],
                        next_entry.get("source"),
                    )

            final_entries.append(combined_entry)

    logger.info(
        "Reduced down to %d entries with metadata (from %d original entries)",
        len(final_entries),
        len(tagged_entries),
    )
    return final_entries


def apply_tagging(entries: List[Dict], hints_path: Optional[str] = None) -> List[Dict]:
    """
    Apply tagging to media entries using hints and API calls.

    Args:
        entries: List of dictionaries representing media entries.
        hints_path: Path to the hints YAML file. Optional.

    Returns:
        List of dictionaries with added metadata in the 'tagged' field
        Added metadata includes canonical_title, type, tags, confidence.
    """
    hints = load_hints(hints_path)
    for entry in entries:
        tagged_entry = _tag_entry(entry["title"], hints)
        entry["tagged"] = tagged_entry

    logger.info("Tagged %d entries with metadata", len(entries))
    return _combine_similar_entries(entries)


if __name__ == "__main__":
    # Example usage
    sample_entries = [
        {"title": "The Hobbit", "action": "started", "date": "2023-01-01"},
        {"title": "Elden Ring", "action": "finished", "date": "2023-02-15"},
    ]

    tagged = apply_tagging(sample_entries)
    for curr_entry in tagged:
        print(f"Tagged entry: {curr_entry}")

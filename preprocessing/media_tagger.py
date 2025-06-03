"""
Preprocessing stage to tag media entries with metadata from external APIs.
This module includes functions to apply tagging with metadata from APIs and hints.
"""

import copy
import logging
import re
from typing import Dict, List, Optional, Tuple

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
        close_api_hits = [
            hit
            for hit in api_hits
            if hit["confidence"] >= api_hits[0]["confidence"] - 0.1
        ]
        if len(close_api_hits) > 1:
            logger.warning(
                "Multiple API hits with close confidence for %s.\n\t%s",
                entry,
                ",\n\t".join(str(hit) for hit in close_api_hits),
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


def _query_with_cache(
    media_type: str, title: str, release_year: str = None
) -> List[Dict]:
    """
    Query the appropriate API with caching to avoid redundant calls.

    Args:
        media_type: The type of media to query ("movie", "tv", "game", "book")
        title: The title to search for
        release_year: Optional year of release to narrow search results

    Returns:
        List of API hits
    """
    cache_key = (title.lower(), media_type, release_year)
    if cache_key in QUERY_CACHE:
        logger.info("Using cached result for %s: %s", media_type, title)
        return QUERY_CACHE[cache_key]

    MEDIA_DB_API_CALL_COUNTS[media_type] = (
        MEDIA_DB_API_CALL_COUNTS.get(media_type, 0) + 1
    )

    # Query the appropriate API
    results = []
    if media_type == "movie":
        results = query_tmdb("movie", title, release_year)
    elif media_type == "tv":
        results = query_tmdb("tv", title, release_year)
    elif media_type == "game":
        results = query_igdb(title, release_year)
    elif media_type == "book":
        results = query_openlibrary(title, release_year)

    # Cache the results
    QUERY_CACHE[cache_key] = results
    return results


def _tag_with_hint(entry: Dict, hint: Dict) -> None:
    """
    Tag an entry with metadata from hints and API calls.
    Args:
        entry: The media entry to tag.
        hint: Optional dictionary with metadata from hints.
    """
    # Apply hint if available
    title = entry["title"]
    release_year_query_term = None
    if hint:
        logger.info("Applying hint for '%s' to entry '%s'", title, entry)
        if hint.get("type") == "Ignored":
            return None
        title = hint.get("canonical_title", title)

        # Extract release_year from hint if available
        if "release_year" in hint:
            release_year_query_term = hint["release_year"]

    api_hits = []
    types_to_query = ["Movie", "TV Show", "Game", "Book"]
    # If entry already has a type, only query that type (used for specifying TV Show if there's a season in the title)
    if "type" in entry:
        types_to_query = [entry["type"]]
    # If hint specifies the type, only query the appropriate database
    elif hint and "type" in hint:
        types_to_query = [hint["type"]]

    # Query APIs with caching
    if "Movie" in types_to_query:
        api_hits.extend(_query_with_cache("movie", title, release_year_query_term))
    if "TV Show" in types_to_query:
        api_hits.extend(_query_with_cache("tv", title, release_year_query_term))
    if "Game" in types_to_query:
        api_hits.extend(_query_with_cache("game", title, release_year_query_term))
    if "Book" in types_to_query:
        api_hits.extend(_query_with_cache("book", title, release_year_query_term))

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

    entry["tagged"] = tagged_entry


def _pair_dates_with_hints(hints: List[Dict], entry: Dict) -> List[Tuple[Dict, Dict]]:
    """
    Pair dates from the entry with hints based on title.

    Args:
        hints: List of hint dictionaries to match against.
        entry: The media entry to process.

    Returns:
        A list of tuples of (matching_hint, entry_with_matching_dates)
        matching_hint: The hint that matches the entry's dates.
        entry_with_matching_dates: The entry with dates limited to those that match the hint.
    """
    unmatched_dates = entry.get("started_dates", []) + entry.get("finished_dates", [])

    matched_pairs = []
    for hint in hints:
        new_entry = copy.deepcopy(entry)
        new_entry["started_dates"] = [
            date
            for date in new_entry.get("started_dates", [])
            if date in hint.get("dates", [])
        ]
        new_entry["finished_dates"] = [
            date
            for date in new_entry.get("finished_dates", [])
            if date in hint.get("dates", [])
        ]
        if not new_entry["started_dates"] and not new_entry["finished_dates"]:
            logger.warning(
                "No matching dates found for entry '%s' with hint '%s'.",
                entry.get("title", "No Title"),
                ", ".join(hint.get("dates", [])),
            )
            continue

        unmatched_dates = [
            date for date in unmatched_dates if date not in hint.get("dates", [])
        ]
        matched_pairs.append((hint, new_entry))

    if unmatched_dates:
        logger.warning("Unmatched dates after pairing: %s", ", ".join(unmatched_dates))

    return matched_pairs


def _tag_entry(entry: Dict, hints: Dict) -> List[Dict]:
    """
    Process a single media entry to extract relevant information.

    Args:
        entry: entry dict with title and dates for hint matching.
        hints: A dictionary containing hints for tagging.

    Returns:
        A list of dictionaries with the entry tagged with additional metadata:
        canonical_title, poster_path, source, type, tags, confidence.
        The list will only contain multiple entries if hints suggest splitting the entry because only a subset of
        dates match.
    """
    title = entry["title"]

    season_match = re.search(r"(.*)(s\d{1,2})\s*(e\d{1,2})?\s*", title, re.IGNORECASE)
    if season_match:
        title = season_match.group(1).strip()
        entry["season"] = season_match.group(2).lower()
        entry["type"] = "TV Show"
        logger.info("Extracted season from title: %s", entry)

    hint = hints.get(title, None)
    hint_entry_pairs = [(hint, entry)]
    if isinstance(hint, list):
        logger.warning("Multiple hints found for '%s'.", title)
        hint_entry_pairs = _pair_dates_with_hints(hint, entry)

    for hint, entry in hint_entry_pairs:
        _tag_with_hint(entry, hint)
    return [entry for _, entry in hint_entry_pairs]


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
        tagged_entry = entry.get("tagged")
        if tagged_entry is None:
            continue

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
            combined_tagged = combined_entry.get("tagged", {})
            for next_entry in entries[1:]:
                next_tagged_entry = next_entry.get("tagged", {})
                if next_tagged_entry.get("tags") != combined_tagged.get("tags"):
                    logger.warning(
                        "Inconsistent tags for entries with canonical_title '%s' and type '%s'. Discarding tags: %s",
                        key[0],
                        key[1],
                        next_tagged_entry.get("tags"),
                    )
                if next_tagged_entry.get("poster_path") != combined_tagged.get(
                    "poster_path"
                ):
                    logger.warning(
                        (
                            "Inconsistent poster_path for entries with canonical_title '%s' and type '%s'. Discarding "
                            "poster_path: %s"
                        ),
                        key[0],
                        key[1],
                        next_tagged_entry.get("poster_path"),
                    )
                if next_tagged_entry.get("confidence") != combined_tagged.get(
                    "confidence"
                ):
                    logger.warning(
                        (
                            "Inconsistent confidence for entries with canonical_title '%s' and type '%s'. Discarding "
                            "confidence: %s"
                        ),
                        key[0],
                        key[1],
                        next_tagged_entry.get("confidence"),
                    )
                if next_tagged_entry.get("source") != combined_tagged.get("source"):
                    logger.warning(
                        (
                            "Inconsistent source for entries with canonical_title '%s' and type '%s'. Discarding "
                            "source: %s"
                        ),
                        key[0],
                        key[1],
                        next_tagged_entry.get("source"),
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

    processed_entries = []
    for entry in entries:
        tagged_entries = [
            entry for entry in _tag_entry(entry, hints) if entry is not None
        ]
        processed_entries.extend(tagged_entries)

    logger.info("Tagged %d entries with metadata", len(processed_entries))
    return _combine_similar_entries(processed_entries)


if __name__ == "__main__":
    # Example usage
    sample_entries = [
        {"title": "The Hobbit", "action": "started", "date": "2023-01-01"},
        {"title": "Elden Ring", "action": "finished", "date": "2023-02-15"},
    ]

    tagged = apply_tagging(sample_entries)
    for curr_entry in tagged:
        print(f"Tagged entry: {curr_entry}")

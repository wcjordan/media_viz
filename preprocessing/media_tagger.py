"""
Preprocessing stage to tag media entries with metadata from external APIs.
This module includes functions to load hints from YAML and query external APIs.
"""

import operator
import os
import logging
from typing import Dict, List, Optional
import requests

import nltk
import yaml

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_HINTS_PATH = os.path.join(os.path.dirname(__file__), "hints.yaml")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
GENRE_MAP_BY_MODE = {}


def _load_hints(hints_path: Optional[str] = DEFAULT_HINTS_PATH) -> Dict:
    """
    Load hints from a YAML file for manual overrides.

    Args:
        hints_path: Path to the hints YAML file.

    Returns:
        Dictionary containing hints for media entries.
    """
    if hints_path is None:
        hints_path = DEFAULT_HINTS_PATH
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


def _get_genre_map(mode: str) -> Dict[int, str]:
    if mode in GENRE_MAP_BY_MODE:
        return GENRE_MAP_BY_MODE[mode]

    api_key = os.environ.get("TMDB_API_KEY")
    genre_response = requests.get(
        f"{TMDB_BASE_URL}/genre/{mode}/list",
        params={"api_key": api_key, "language": "en-US"},
        timeout=10,
    )
    genre_response.raise_for_status()
    genre_data = genre_response.json()
    genre_map = {g["id"]: g["name"] for g in genre_data.get("genres", [])}
    GENRE_MAP_BY_MODE[mode] = genre_map
    return genre_map


def _query_tmdb(mode: str, title: str) -> List[Dict]:
    """
    Query The Movie Database (TMDB) API for TV shows or Movie metadata.

    Args:
        mode: The mode of media to query (e.g., "movie" or "tv").
        title: The title of the media to query.

    Returns:
        List of dictionaries with metadata for each entry:
            - canonical_title is the official title from TMDB
            - poster_path is the URL to the media's poster image
            - type is the type of media (Movie, TV Show, etc.)
            - tags is a dictionary containing tags for genre, mood, etc.
            - confidence is a float between 0 and 1 indicating match confidence
            - source is the source of the metadata (e.g., "tmdb")
    """
    logger.info("Querying TMDB for %s w/ title: %s", mode, title)

    api_key = os.environ.get("TMDB_API_KEY")
    if not api_key:
        logger.warning("TMDB_API_KEY not found in environment variables")
        return []

    results = []

    # Search for TV shows or Movies
    try:
        tmdb_response = requests.get(
            f"{TMDB_BASE_URL}/search/{mode}",
            params={
                "api_key": api_key,
                "query": title,
                "language": "en-US",
                "page": 1,
                "include_adult": "false",
            },
            timeout=10,
        )
        tmdb_response.raise_for_status()
        tmdb_data = tmdb_response.json()
        genre_map = _get_genre_map(mode)

        # Process TMDB results
        for entry in tmdb_data.get("results", [])[
            :5
        ]:  # Get top 5 TV show or Movie matches
            # Calculate confidence based on popularity and title similarity
            canonical_title = (
                entry.get("name", "") if mode == "tv" else entry.get("title", "")
            )

            title_similarity = 1.0 - (
                nltk.edit_distance(title.lower(), canonical_title.lower())
                / max(len(title), len(canonical_title))
            )
            popularity = entry.get("popularity", 0) / 100  # Normalize popularity
            confidence = (
                0.7 * title_similarity
                + 0.2 * popularity
                + 0.1 * min(1.0, entry.get("vote_average", 0) / 10)
            )

            # Get genre information
            genres = []
            if "genre_ids" in entry:
                genres = [
                    genre_map.get(gid)
                    for gid in entry.get("genre_ids", [])
                    if gid in genre_map
                ]

            # Create result entry
            date_key = "first_air_date" if mode == "tv" else "release_date"
            results.append(
                {
                    "canonical_title": canonical_title,
                    "poster_path": f"https://image.tmdb.org/t/p/w600_and_h900_bestv2/{entry.get("poster_path", "")}",
                    "type": "TV" if mode == "tv" else "Movie",
                    "tags": {
                        "genre": genres,
                        "release_year": (
                            entry.get(date_key, "")[:4] if entry.get(date_key) else ""
                        ),
                    },
                    "confidence": confidence,
                    "source": "tmdb",
                }
            )

        # Sort results by confidence
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:5]  # Return top 5 results overall

    except requests.RequestException as e:
        logger.error("Error querying TMDB API for %s: %s", mode, e)
        return []


def _query_igdb(title: str) -> List[Dict]:
    """
    Query the Internet Game Database (IGDB) API for video game metadata.

    Args:
        title: The title of the game to query.

    Returns:
        List of dictionaries with metadata for each entry:
            - canonical_title is the official title from IGDB
            - poster_path is the URL to the media's poster image
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
        return []

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


def _query_openlibrary(title: str) -> List[Dict]:
    """
    Query the Open Library API for book metadata.

    Args:
        title: The title of the book to query.

    Returns:
        List of dictionaries with metadata for each entry:
            - canonical_title is the official title from Open Library
            - poster_path is the URL to the media's poster image
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
        return []

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


def apply_tagging(entries: List[Dict], hints_path: Optional[str] = None) -> List[Dict]:
    """
    Apply tagging to media entries using hints and API calls.

    Args:
        entries: List of dictionaries representing media entries.
        hints_path: Path to the hints YAML file. Optional.

    Returns:
        List of dictionaries with added metadata: canonical_title, type, tags, confidence.
    """
    hints = _load_hints(hints_path)
    tagged_entries = []

    for entry in entries:
        title = entry.get("title", "")
        if not title:
            logger.warning("Entry missing title, skipping tagging: %s", entry)
            continue

        # Apply hints if available
        hint = None
        for hint_key, hint_data in hints.items():
            if hint_key == title:
                logger.info("Applying hint for '%s' to entry '%s'", hint_key, entry)
                hint = hint_data
                break

        api_hits = []
        api_hits.extend(_query_tmdb("movie", title))
        api_hits.extend(_query_tmdb("tv", title))
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

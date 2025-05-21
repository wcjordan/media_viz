"""
Preprocessing stage to tag media entries with metadata from external APIs.
This module includes functions to load hints from YAML and query external APIs.
"""

import operator
import os
import logging
import requests
from typing import Dict, List, Optional
import yaml

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_HINTS_PATH = os.path.join(os.path.dirname(__file__), "hints.yaml")


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


def _query_tmdb(title: str) -> List[Dict]:
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
    logger.info("Querying TMDB for title: %s", title)

    api_key = os.environ.get("TMDB_API_KEY")
    if not api_key:
        logger.warning("TMDB_API_KEY not found in environment variables")
        return []

    base_url = "https://api.themoviedb.org/3"
    results = []

    # Search for movies
    try:
        movie_response = requests.get(
            f"{base_url}/search/movie",
            params={
                "api_key": api_key,
                "query": title,
                "language": "en-US",
                "page": 1,
                "include_adult": "false",
            },
            timeout=10,
        )
        movie_response.raise_for_status()
        movie_data = movie_response.json()

        # Process movie results
        for movie in movie_data.get("results", [])[:3]:  # Get top 3 movie matches
            # Calculate confidence based on popularity and title similarity
            title_similarity = 1.0 - min(1.0, abs(len(title) - len(movie.get("title", ""))) / max(len(title), 1))
            popularity = min(1.0, movie.get("popularity", 0) / 100)  # Normalize popularity
            confidence = 0.5 * title_similarity + 0.3 * popularity + 0.2 * min(1.0, movie.get("vote_average", 0) / 10)

            # Get genre information
            genres = []
            if "genre_ids" in movie:
                genre_response = requests.get(
                    f"{base_url}/genre/movie/list",
                    params={"api_key": api_key, "language": "en-US"},
                    timeout=10,
                )
                genre_response.raise_for_status()
                genre_data = genre_response.json()
                genre_map = {g["id"]: g["name"] for g in genre_data.get("genres", [])}
                genres = [genre_map.get(gid) for gid in movie.get("genre_ids", []) if gid in genre_map]

            # Create result entry
            results.append({
                "canonical_title": movie.get("title", title),
                "type": "Movie",
                "tags": {
                    "genre": genres,
                    "release_year": movie.get("release_date", "")[:4] if movie.get("release_date") else "",
                    "overview": movie.get("overview", "")[:100] + "..." if len(movie.get("overview", "")) > 100 else movie.get("overview", ""),
                },
                "confidence": confidence,
                "source": "tmdb",
            })

        # Search for TV shows
        tv_response = requests.get(
            f"{base_url}/search/tv",
            params={
                "api_key": api_key,
                "query": title,
                "language": "en-US",
                "page": 1,
                "include_adult": "false",
            },
            timeout=10,
        )
        tv_response.raise_for_status()
        tv_data = tv_response.json()

        # Process TV show results
        for show in tv_data.get("results", [])[:2]:  # Get top 2 TV show matches
            # Calculate confidence based on popularity and title similarity
            title_similarity = 1.0 - min(1.0, abs(len(title) - len(show.get("name", ""))) / max(len(title), 1))
            popularity = min(1.0, show.get("popularity", 0) / 100)  # Normalize popularity
            confidence = 0.5 * title_similarity + 0.3 * popularity + 0.2 * min(1.0, show.get("vote_average", 0) / 10)

            # Get genre information
            genres = []
            if "genre_ids" in show:
                genre_response = requests.get(
                    f"{base_url}/genre/tv/list",
                    params={"api_key": api_key, "language": "en-US"},
                    timeout=10,
                )
                genre_response.raise_for_status()
                genre_data = genre_response.json()
                genre_map = {g["id"]: g["name"] for g in genre_data.get("genres", [])}
                genres = [genre_map.get(gid) for gid in show.get("genre_ids", []) if gid in genre_map]

            # Create result entry
            results.append({
                "canonical_title": show.get("name", title),
                "type": "TV",
                "tags": {
                    "genre": genres,
                    "first_air_date": show.get("first_air_date", "")[:4] if show.get("first_air_date") else "",
                    "overview": show.get("overview", "")[:100] + "..." if len(show.get("overview", "")) > 100 else show.get("overview", ""),
                },
                "confidence": confidence,
                "source": "tmdb",
            })

        # Sort results by confidence
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:5]  # Return top 5 results overall

    except requests.RequestException as e:
        logger.error("Error querying TMDB API: %s", e)
        return []


def _query_igdb(title: str) -> List[Dict]:
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

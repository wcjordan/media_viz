"""
API client functions for querying external media databases.
"""

import os
import logging
import requests
import nltk

logger = logging.getLogger(__name__)

# Default paths
TMDB_BASE_URL = "https://api.themoviedb.org/3"
GENRE_MAP_BY_MODE = {}


def _get_genre_map(mode: str) -> dict:
    """
    Get or cache the genre map for a specific TMDB mode (movie or tv).
    
    Args:
        mode: The mode to get genres for ("movie" or "tv")
        
    Returns:
        Dictionary mapping genre IDs to genre names
    """
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


def query_tmdb(mode: str, title: str) -> list:
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
                    "poster_path": f"https://image.tmdb.org/t/p/w600_and_h900_bestv2/{entry.get('poster_path', '')}",
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


def query_igdb(title: str) -> list:
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


def query_openlibrary(title: str) -> list:
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

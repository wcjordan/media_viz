"""
API client functions for querying external media databases.
"""

import os
import logging
import time
import requests
import nltk

logger = logging.getLogger(__name__)

# Default paths
TMDB_BASE_URL = "https://api.themoviedb.org/3"
GENRE_MAP_BY_MODE = {}
IGDB_TOKEN = None


def _calculate_title_similarity(title1: str, title2: str) -> float:
    """
    Calculate similarity between two titles using edit distance.

    Args:
        title1: First title string
        title2: Second title string

    Returns:
        Float between 0.0 and 1.0 representing similarity (1.0 = identical)
    """
    return 1.0 - (
        nltk.edit_distance(title1.lower(), title2.lower())
        / max(len(title1), len(title2), 1)
    )


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

            title_similarity = _calculate_title_similarity(title, canonical_title)
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

        return results

    except requests.RequestException as e:
        logger.error("Error querying TMDB API for %s: %s", mode, e)
        return []


def _get_igdb_token() -> str:
    """
    Get an access token for IGDB API using Twitch credentials.

    Returns:
        Access token string
    """
    global IGDB_TOKEN  # pylint: disable=global-statement
    if IGDB_TOKEN:
        return IGDB_TOKEN

    # IGDB requires a Client ID and Client Secret from Twitch
    client_id = os.environ.get("IGDB_CLIENT_ID")
    client_secret = os.environ.get("IGDB_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.warning(
            "IGDB_CLIENT_ID or IGDB_CLIENT_SECRET not found in environment variables"
        )
        return None

    try:
        auth_response = requests.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        auth_response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Error querying IGDB API: %s", e)
        return None

    token = auth_response.json().get("access_token", "")
    if IGDB_TOKEN:
        IGDB_TOKEN = token
    return token


def _format_igdb_entry(search_title: str, game: dict) -> dict:
    """
    Format a single IGDB game entry into a standardized dictionary.
    Args:
        search_title: The search title.  Used to calculate confidence.
        game: A dictionary containing game metadata from IGDB.
    Returns:
        A dictionary with the following keys
            - canonical_title: The official title from IGDB
            - poster_path: The URL to the media's poster image
            - type: The type of media (Game)
            - tags: A dictionary containing tags for genre, platform, etc.
            - confidence: A float between 0 and 1 indicating match confidence
            - source: The source of the metadata (e.g., "igdb")
    """
    # Calculate confidence based on name similarity and ratings
    game_title = game.get("name", "")
    title_similarity = _calculate_title_similarity(search_title, game_title)

    # Normalize ratings (they're on a scale of 0-100)
    user_rating = game.get("rating", 0) / 100 if game.get("rating") else 0
    critic_rating = (
        game.get("aggregated_rating", 0) / 100 if game.get("aggregated_rating") else 0
    )

    # Calculate overall confidence
    confidence = 0.7 * title_similarity + 0.15 * user_rating + 0.15 * critic_rating

    # Extract genres
    genres = []
    if "genres" in game and game["genres"]:
        genres = [genre.get("name") for genre in game["genres"] if genre.get("name")]

    # Extract platforms
    platforms = []
    if "platforms" in game and game["platforms"]:
        platforms = [
            platform.get("name")
            for platform in game["platforms"]
            if platform.get("name")
        ]

    # Get cover image URL
    cover_url = ""
    if "cover" in game and game["cover"] and "url" in game["cover"]:
        # IGDB returns URLs like "//images.igdb.com/..."
        # Convert to https://images.igdb.com/...
        cover_url = game["cover"]["url"]
        if cover_url.startswith("//"):
            cover_url = f"https:{cover_url}"
        # Get the larger image by replacing thumb with 720p
        cover_url = cover_url.replace("thumb", "720p")

    # Get release year
    release_year = ""
    if "first_release_date" in game and game["first_release_date"]:
        # IGDB uses Unix timestamps
        release_year = time.strftime("%Y", time.gmtime(game["first_release_date"]))

    return {
        "canonical_title": game_title,
        "poster_path": cover_url,
        "type": "Game",
        "tags": {
            "genre": genres,
            "platform": platforms,
            "release_year": release_year,
        },
        "confidence": confidence,
        "source": "igdb",
    }


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
    logger.info("Querying IGDB for title: %s", title)

    access_token = _get_igdb_token()
    if not access_token:
        logger.warning("Failed to obtain IGDB access token")
        return []

    client_id = os.environ.get("IGDB_CLIENT_ID")
    headers = {"Client-ID": client_id, "Authorization": f"Bearer {access_token}"}
    try:
        # Step 2: Query IGDB API for games

        # Use the Apicalypse query format that IGDB requires
        # Search for games with name similar to the title
        # Include relevant fields for metadata
        query = f"""
            search "{title}";
            fields name, cover.url, first_release_date, genres.name, platforms.name, rating, aggregated_rating;
            where version_parent = null;
            limit 5;
        """

        response = requests.post(
            "https://api.igdb.com/v4/games", headers=headers, data=query, timeout=10
        )
        response.raise_for_status()
        games = response.json()

        # Step 3: Process results
        return [_format_igdb_entry(title, game) for game in games]

    except requests.RequestException as e:
        logger.error("Error querying IGDB API: %s", e)
        return []


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

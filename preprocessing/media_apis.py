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


def _format_tmdb_entry(
    search_title: str, entry: dict, mode: str, genre_map: dict
) -> dict:
    """
    Format a single TMDB game entry into a standardized dictionary.
    Args:
        search_title: The search title.  Used to calculate confidence.
        entry: A dictionary containing game metadata from TMDB.
        mode: The mode of media (e.g., "movie" or "tv").
        genre_map: A dictionary mapping genre IDs to genre names.
    Returns:
        A dictionary with the following keys
            - canonical_title: The official title from TMDB
            - poster_path: The URL to the media's poster image
            - type: The type of media (TV Show, Movie, etc.)
            - tags: A dictionary containing tags for genre, platform, etc.
            - confidence: A float between 0 and 1 indicating match confidence
            - source: The source of the metadata (e.g., "tmdb")
    """
    # Calculate confidence based on popularity and title similarity
    canonical_title = entry.get("name", "") if mode == "tv" else entry.get("title", "")

    title_similarity = _calculate_title_similarity(search_title, canonical_title)
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
            genre_map.get(gid) for gid in entry.get("genre_ids", []) if gid in genre_map
        ]

    # Create result entry
    date_key = "first_air_date" if mode == "tv" else "release_date"
    release_year = entry.get(date_key, "")[:4] if entry.get(date_key) else ""
    if not release_year:
        return None

    return {
        "canonical_title": canonical_title,
        "poster_path": f"https://image.tmdb.org/t/p/w600_and_h900_bestv2/{entry.get('poster_path', '')}",
        "type": "TV Show" if mode == "tv" else "Movie",
        "tags": {
            "genre": genres,
            "release_year": release_year,
        },
        "confidence": confidence,
        "source": "tmdb",
    }


def query_tmdb(mode: str, title: str, release_year: str = None) -> list:
    """
    Query The Movie Database (TMDB) API for TV shows or Movie metadata.

    Args:
        mode: The mode of media to query (e.g., "movie" or "tv").
        title: The title of the media to query.
        release_year: Optional year of release to narrow search results.

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

    # Search for TV shows or Movies
    try:
        # Prepare parameters for the API call
        params = {
            "api_key": api_key,
            "query": title,
            "language": "en-US",
            "page": 1,
            "include_adult": "false",
        }

        # Add year parameter if provided
        if release_year:
            params["year"] = release_year

        tmdb_response = requests.get(
            f"{TMDB_BASE_URL}/search/{mode}",
            params=params,
            timeout=10,
        )
        tmdb_response.raise_for_status()
        tmdb_data = tmdb_response.json()
        genre_map = _get_genre_map(mode)

        # Get top 5 TV show or Movie matches
        raw_entries = tmdb_data.get("results", [])[:5]
        entries = [
            _format_tmdb_entry(title, entry, mode, genre_map) for entry in raw_entries
        ]
        entries = [entry for entry in entries if entry is not None]
        return entries

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
    if token:
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
    confidence = 0.8 * title_similarity + 0.1 * user_rating + 0.1 * critic_rating

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
    if not release_year:
        return None

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


def query_igdb(title: str, release_year: str = None) -> list:
    """
    Query the Internet Game Database (IGDB) API for video game metadata.

    Args:
        title: The title of the game to query.
        release_year: Optional year of release to narrow search results.

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
        # Query IGDB API for games

        # Use the Apicalypse query format that IGDB requires
        # Search for games with name similar to the title
        # Include relevant fields for metadata
        query = f"""
            search "{title}";
            fields name, cover.url, first_release_date, genres.name, platforms.name, rating, aggregated_rating;
            where version_parent = null;
        """

        # Add year filter if provided
        if release_year:
            # Convert year to Unix timestamps (start and end of year)
            try:
                year = int(release_year)
                start_timestamp = int(
                    time.mktime(time.strptime(f"{year}-01-01", "%Y-%m-%d"))
                )
                end_timestamp = int(
                    time.mktime(time.strptime(f"{year}-12-31", "%Y-%m-%d"))
                )
                query_segments.append(
                    f"first_release_date >= {start_timestamp} & first_release_date <= {end_timestamp}"
                )
            except ValueError:
                logger.warning("Invalid release_year format: %s", release_year)

        query_segments.append("limit 5")
        query = "; ".join(query_segments) + ";"

        response = requests.post(
            "https://api.igdb.com/v4/games", headers=headers, data=query, timeout=10
        )
        response.raise_for_status()
        games = response.json()

        tagged_games = [_format_igdb_entry(title, game) for game in games]
        return [game for game in tagged_games if game is not None]

    except requests.RequestException as e:
        logger.error("Error querying IGDB API: %s", e)
        return []


def _format_openlibrary_entry(search_title: str, book: dict) -> dict:
    """
    Format a single Open Library book entry into a standardized dictionary.
    Args:
        search_title: The search title.  Used to calculate confidence.
        book: A dictionary containing book metadata from Open Library.
    Returns:
        A dictionary with the following keys
            - canonical_title: The official title from Open Library
            - poster_path: The URL to the book's cover image
            - type: The type of media (Book)
            - tags: A dictionary containing tags for genre, author, etc.
            - confidence: A float between 0 and 1 indicating match confidence
            - source: The source of the metadata (e.g., "openlibrary")
    """
    # Calculate confidence based on title similarity
    # Note books confidence is handicapped to 0.8 to avoid drowning out games and movies
    book_title = book.get("title", "")
    confidence = 0.8 * _calculate_title_similarity(search_title, book_title)

    # Get cover image URL if available
    cover_id = book.get("cover_i")
    cover_url = ""
    if cover_id:
        cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

    # Get authors
    authors = book.get("author_name", [])

    # Get subjects/genres
    subjects = book.get("subject", []) if book.get("subject") else []

    # Get first publication year
    publish_year = (
        str(book.get("first_publish_year", ""))
        if book.get("first_publish_year")
        else ""
    )
    if not publish_year:
        return None

    # Create result entry
    return {
        "canonical_title": book_title,
        "poster_path": cover_url,
        "type": "Book",
        "tags": {
            "genre": subjects,
            "author": authors,
            "release_year": publish_year,
        },
        "confidence": confidence,
        "source": "openlibrary",
    }


def query_openlibrary(title: str, release_year: str = None) -> list:
    """
    Query the Open Library API for book metadata.

    Args:
        title: The title of the book to query.
        release_year: Optional year of release to narrow search results.

    Returns:
        List of dictionaries with metadata for each entry:
            - canonical_title is the official title from Open Library
            - poster_path is the URL to the media's poster image
            - type is the type of media (Movie, TV Show, etc.)
            - tags is a dictionary containing tags for genre, mood, etc.
            - confidence is a float between 0 and 1 indicating match confidence
            - source is the source of the metadata (e.g., "openlibrary")
    """
    logger.info("Querying Open Library for title: %s", title)

    try:
        # Prepare parameters for the API call
        params = {
            "title": title,
            "limit": 5,
            "fields": "key,title,author_name,first_publish_year,subject,cover_i",
        }

        # Add first_publish_year parameter if provided
        if release_year:
            params["first_publish_year"] = release_year

        # Search for books by title
        search_url = "https://openlibrary.org/search.json"
        response = requests.get(
            search_url,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        search_data = response.json()

        # Process search results
        tagged_books = [
            _format_openlibrary_entry(title, book)
            for book in search_data.get("docs", [])
        ]
        return [book for book in tagged_books if book is not None]

    except requests.RequestException as e:
        logger.error("Error querying Open Library API: %s", e)
        return []

"""Unit tests for the media API client functions."""

import logging
import os
from unittest.mock import patch
import pytest
import requests

from preprocessing import media_apis
from preprocessing.media_apis import (
    query_tmdb,
    query_igdb,
    query_openlibrary,
    _get_genre_map,
    _get_igdb_token,
    _format_igdb_entry,
    _calculate_title_similarity,
    GENRE_MAP_BY_MODE,
)


GENRE_MAPPING = [
    {"id": 28, "name": "Action"},
    {"id": 18, "name": "Drama"},
    {"id": 878, "name": "Science Fiction"},
    {"id": 9648, "name": "Mystery"},
    {"id": 10765, "name": "Sci-Fi & Fantasy"},
]


@pytest.fixture(name="mock_api_responses")
def fixture_mock_api_responses():
    """Mock API responses for different media types."""
    return {
        "book": [
            {
                "title": "The Hobbit",
                "author_name": ["J.R.R. Tolkien"],
                "first_publish_year": 1937,
                "subject": ["Fantasy", "Fiction", "Adventure"],
                "cover_i": 12345,
            },
            {
                "title": "The Hobbit: An Unexpected Journey",
                "author_name": ["J.R.R. Tolkien", "Peter Jackson"],
                "first_publish_year": 2012,
                "subject": ["Fantasy", "Film Adaptation"],
                "cover_i": 67890,
            },
        ],
        "game": [
            {
                "name": "The Witcher 3: Wild Hunt",
                "first_release_date": 1431993600,  # May 19, 2015
                "rating": 93.4,
                "aggregated_rating": 91.2,
                "cover": {
                    "url": "//images.igdb.com/igdb/image/upload/t_thumb/co1wyy.jpg",
                },
                "genres": [
                    {"name": "Role-playing (RPG)"},
                    {"name": "Adventure"},
                ],
                "platforms": [
                    {"name": "PC"},
                    {"name": "PlayStation 4"},
                ],
            },
            {
                "name": "The Witcher 3: Wild Hunt - Hearts of Stone",
                "first_release_date": 1444694400,  # October 13, 2015
                "rating": 87.5,
                "cover": {
                    "url": "//images.igdb.com/igdb/image/upload/t_thumb/co1wyz.jpg",
                },
                "genres": [
                    {"name": "Role-playing (RPG)"},
                    {"name": "Adventure"},
                ],
                "platforms": [
                    {"name": "PC"},
                    {"name": "PlayStation 4"},
                    {"name": "Xbox One"},
                ],
            },
        ],
        "movie": [
            {
                "title": "The Matrix",
                "release_date": "1999-03-31",
                "popularity": 50.0,
                "vote_average": 8.7,
                "poster_path": "/path/to/poster.jpg",
                "genre_ids": [28, 878],  # Action, Sci-Fi
            },
            {
                "title": "The Matrix Reloaded",
                "release_date": "2003-05-15",
                "popularity": 40.0,
                "vote_average": 7.2,
                "poster_path": "/path/to/poster2.jpg",
                "genre_ids": [28, 878],
            },
        ],
        "tv": [
            {
                "name": "Stranger Things",
                "first_air_date": "2016-07-15",
                "popularity": 80.0,
                "vote_average": 8.5,
                "poster_path": "/path/to/poster10.jpg",
                "genre_ids": [18, 9648, 10765],  # Drama, Mystery, Sci-Fi & Fantasy
            },
        ],
    }


@pytest.fixture(autouse=True, name="mock_http_requests")
def fixture_mock_http_requests():
    """
    Prevent real HTTP requests during tests by mocking requests.get and requests.post.
    This fixture runs automatically for all tests.
    """
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # Set default behavior to raise an exception if called without specific mocking
        mock_get.side_effect = RuntimeError("Unmocked HTTP GET request attempted")
        mock_post.side_effect = RuntimeError("Unmocked HTTP POST request attempted")
        yield mock_get, mock_post


@pytest.fixture(autouse=True)
def reset_api_state():
    """Reset API state (IGDB token & genre map cache) before each test to ensure consistent state."""
    media_apis.IGDB_TOKEN = None
    GENRE_MAP_BY_MODE.clear()


@pytest.fixture(autouse=True)
def mock_env_variables():
    """Set up environment variables for API keys."""
    with patch.dict(
        os.environ,
        {
            "IGDB_CLIENT_ID": "fake_client_id",
            "IGDB_CLIENT_SECRET": "fake_client_secret",
            "TMDB_API_KEY": "fake_key",
        },
    ):
        yield


@pytest.fixture(name="_mock_get_genre_map")
def fixture_mock_get_genre_map():
    """Mock the _get_genre_map function to return a predefined genre map."""
    with patch("preprocessing.media_apis._get_genre_map") as mock_get_genre_map:
        mock_get_genre_map.return_value = {
            genre["id"]: genre["name"] for genre in GENRE_MAPPING
        }
        yield mock_get_genre_map


@pytest.fixture(name="_mock_get_igdb_token")
def fixture_mock_get_igdb_token():
    """Mock the IGDB authentication response."""
    with patch("preprocessing.media_apis._get_igdb_token") as mock_get_igdb_token:
        mock_get_igdb_token.return_value = "mock_token"
        yield


@pytest.fixture(name="mock_igdb_auth_response")
def fixture_mock_igdb_auth_response(mock_http_requests):
    """
    Mock the IGDB authentication response.
    """

    def _mock_igdb_auth_response():
        _, mock_post = mock_http_requests
        mock_post.return_value.json.return_value = {
            "access_token": "mock_access_token",
            "expires_in": 14400,
            "token_type": "bearer",
        }
        mock_post.side_effect = None
        return mock_post

    return _mock_igdb_auth_response


@pytest.fixture(name="mock_tmdb_response")
def fixture_mock_tmdb_response(mock_http_requests):
    """Mock the response for TMDB API."""

    def _mock_tmdb_response(results):
        mock_get, _ = mock_http_requests
        mock_get.return_value.json.return_value = {"results": results}
        mock_get.side_effect = None

    return _mock_tmdb_response


@pytest.fixture(name="mock_igdb_response")
def fixture_mock_igdb_response(mock_api_responses, mock_http_requests):
    """Mock the response for IGDB API."""

    def _mock_igdb_response(results=None):
        if results is None:
            results = mock_api_responses["game"]
        _, mock_post = mock_http_requests
        mock_post.return_value.json.return_value = results
        mock_post.side_effect = None
        return mock_post

    return _mock_igdb_response


@pytest.fixture(name="mock_openlibrary_response")
def fixture_mock_openlibrary_response(mock_api_responses, mock_http_requests):
    """Mock responses for OpenLibrary API."""

    def _mock_openlibrary_response(results=None):
        if results is None:
            results = mock_api_responses["book"]
        mock_get, _ = mock_http_requests
        mock_get.return_value.json.return_value = {
            "docs": results,
        }
        mock_get.side_effect = None
        return mock_get

    return _mock_openlibrary_response


def test_get_genre_map(mock_http_requests):
    """Test getting and caching the genre map."""
    mock_get, _ = mock_http_requests
    mock_get.return_value.json.return_value = {
        "genres": GENRE_MAPPING,
    }
    mock_get.side_effect = None

    expected_genre_map = {genre["id"]: genre["name"] for genre in GENRE_MAPPING}

    # First call should make the API request
    genre_map = _get_genre_map("movie")
    assert mock_get.call_count == 1
    assert genre_map == expected_genre_map

    # Second call should use the cached value
    genre_map = _get_genre_map("movie")
    assert mock_get.call_count == 1
    assert genre_map == expected_genre_map

    # Different mode should make a new request
    genre_map = _get_genre_map("tv")
    assert mock_get.call_count == 2
    assert genre_map == expected_genre_map


def test_query_tmdb_movie_success(
    mock_api_responses, mock_tmdb_response, _mock_get_genre_map
):
    """Test successful TMDB movie query."""
    mock_tmdb_response(mock_api_responses["movie"])

    # Call the function
    results = query_tmdb("movie", "The Matrix")

    # Verify results
    assert len(results) == 2
    assert results[0]["canonical_title"] == "The Matrix"
    assert results[0]["type"] == "Movie"
    assert results[0]["tags"]["genre"] == ["Action", "Science Fiction"]
    assert results[0]["tags"]["release_year"] == "1999"
    assert results[0]["confidence"] > 0.7  # High confidence for exact match
    assert results[0]["source"] == "tmdb"
    assert "poster_path" in results[0]


def test_query_tmdb_with_release_year(
    mock_api_responses, mock_tmdb_response, mock_http_requests, _mock_get_genre_map
):
    """Test TMDB query with release_year parameter."""
    mock_get, _ = mock_http_requests
    mock_tmdb_response(mock_api_responses["movie"])

    # Call the function with release_year
    query_tmdb("movie", "The Matrix", "1999")

    # Verify that the year parameter was included in the API call
    assert mock_get.call_count == 1
    assert "year" in mock_get.call_args.kwargs["params"]
    assert mock_get.call_args.kwargs["params"]["year"] == "1999"


def test_query_tmdb_tv_success(
    mock_api_responses, mock_tmdb_response, _mock_get_genre_map
):
    """Test successful TMDB TV query."""
    mock_tmdb_response(mock_api_responses["tv"])

    # Call the function
    results = query_tmdb("tv", "Stranger Things")

    # Verify results
    assert len(results) == 1
    assert results[0]["canonical_title"] == "Stranger Things"
    assert results[0]["type"] == "TV Show"
    assert "Drama" in results[0]["tags"]["genre"]
    assert results[0]["tags"]["release_year"] == "2016"
    assert results[0]["confidence"] > 0.7  # High confidence for exact match
    assert results[0]["source"] == "tmdb"


def test_query_tmdb_no_api_key(caplog, _mock_get_genre_map):
    """Test TMDB query with no API key."""
    # Clear the TMDB_API_KEY environment variable set by the autouse fixture
    os.environ.clear()
    with caplog.at_level(logging.WARNING):
        results = query_tmdb("movie", "The Matrix")

        assert len(results) == 0
        assert "TMDB_API_KEY not found in environment variables" in caplog.text


def test_query_tmdb_empty_results(mock_tmdb_response, _mock_get_genre_map):
    """Test TMDB query with empty results."""
    # Set up mock for empty results
    mock_tmdb_response([])

    results = query_tmdb("movie", "NonexistentMovie12345")

    assert len(results) == 0


def test_query_tmdb_api_error(mock_http_requests, caplog, _mock_get_genre_map):
    """Test TMDB query with API error."""
    mock_get, _ = mock_http_requests
    mock_get.side_effect = requests.RequestException("API Error")

    with caplog.at_level(logging.ERROR):
        results = query_tmdb("movie", "The Matrix")

        assert len(results) == 0
        assert "Error querying TMDB API for movie: API Error" in caplog.text


def test_query_tmdb_confidence_calculation(
    mock_api_responses, mock_tmdb_response, _mock_get_genre_map
):
    """Test confidence calculation in TMDB query."""
    different_title = "Matrices and Their Many Uses in Mathematics"
    mock_tmdb_response(
        mock_api_responses["movie"]
        + [
            {
                "title": different_title,
                "release_date": "2020-01-15",
                "popularity": 7.2,
                "vote_average": 6.2,
            }
        ]
    )

    query_results = query_tmdb("movie", "Matrix")
    exact_results = [
        result for result in query_results if result["canonical_title"] == "The Matrix"
    ][0]
    similar_results = [
        result
        for result in query_results
        if result["canonical_title"] == "The Matrix Reloaded"
    ][0]
    different_results = [
        result
        for result in query_results
        if result["canonical_title"] == different_title
    ][0]

    # Verify confidence scores
    assert exact_results["confidence"] > similar_results["confidence"]
    assert similar_results["confidence"] > different_results["confidence"]


def test_query_tmdb_limits_results(
    mock_api_responses, mock_tmdb_response, _mock_get_genre_map
):
    """Test that TMDB query limits results to top 5."""
    # Create mock response with more than 5 results
    mock_tmdb_response(mock_api_responses["movie"] * 10)

    # Call the function
    results = query_tmdb("movie", "Movie")

    # Verify results are limited to 5
    assert len(results) == 5


def test_query_tmdb_handles_missing_fields(
    mock_api_responses, mock_tmdb_response, _mock_get_genre_map
):
    """Test that TMDB query handles missing fields gracefully."""
    # Create mock response with missing release_date
    unreleased_movies = [movie.copy() for movie in mock_api_responses["movie"]]
    for movie in unreleased_movies:
        movie["release_date"] = None
    mock_tmdb_response(unreleased_movies)
    results = query_tmdb("movie", "Movie")

    # Verify that results missing a release_date are omitted
    assert len(results) == 0

    # Create mock response with missing release_date
    unreleased_tv = [show.copy() for show in mock_api_responses["tv"]]
    for show in unreleased_tv:
        show["first_air_date"] = None
    mock_tmdb_response(unreleased_tv)
    results = query_tmdb("tv", "Show")

    # Verify that results missing a first_air_date are omitted
    assert len(results) == 0


def test_get_igdb_token_success(mock_igdb_auth_response):
    """Test successful IGDB token retrieval."""
    mock_post = mock_igdb_auth_response()

    token = _get_igdb_token()

    assert token == "mock_access_token"
    mock_post.assert_called_once()
    assert "'client_id': 'fake_client_id'" in str(mock_post.call_args)
    assert "'client_secret': 'fake_client_secret'" in str(mock_post.call_args)


def test_get_igdb_token_missing_credentials(caplog):
    """Test IGDB token retrieval with missing credentials."""
    # Clear the IGDB_CLIENT_ID and IGDB_CLIENT_SECRET environment variable set by the autouse fixture
    os.environ.clear()

    with caplog.at_level(logging.WARNING):
        token = _get_igdb_token()

        assert token is None
        assert "IGDB_CLIENT_ID or IGDB_CLIENT_SECRET not found" in caplog.text


def test_get_igdb_token_api_error(caplog, mock_http_requests):
    """Test IGDB token retrieval with API error."""
    _, mock_post = mock_http_requests
    mock_post.side_effect = requests.RequestException("API Error")

    with caplog.at_level(logging.ERROR):
        token = _get_igdb_token()

        assert token is None
        assert mock_post.called


def test_format_igdb_entry(mock_api_responses):
    """Test formatting an IGDB game entry."""
    result = _format_igdb_entry(
        "The Witcher 3: Wild Hunt", mock_api_responses["game"][0]
    )

    assert result["canonical_title"] == "The Witcher 3: Wild Hunt"
    assert result["type"] == "Game"
    assert result["tags"]["genre"] == ["Role-playing (RPG)", "Adventure"]
    assert result["tags"]["platform"] == ["PC", "PlayStation 4"]
    assert result["tags"]["release_year"] == "2015"
    assert result["confidence"] > 0.9  # Should be high for exact match
    assert result["source"] == "igdb"
    assert "https:" in result["poster_path"]
    assert "720p" in result["poster_path"]  # Should upgrade image quality


def test_format_igdb_entry_unreleased(mock_api_responses):
    """Test formatting an IGDB game entry with missing fields."""
    test_game = mock_api_responses["game"][0].copy()
    test_game["first_release_date"] = None  # Simulate missing first_release_date

    result = _format_igdb_entry("Unreleased Game", test_game)

    # Results without a first_release_date should not be included
    assert result is None


def test_format_igdb_entry_partial_fields(mock_api_responses):
    """Test formatting an IGDB game entry with partial fields."""
    test_game = {
        "name": mock_api_responses["game"][0].get("name"),
        "first_release_date": mock_api_responses["game"][0].get("first_release_date"),
    }

    result = _format_igdb_entry("Partial Game", test_game)

    assert result["canonical_title"] == "The Witcher 3: Wild Hunt"
    assert result["type"] == "Game"
    assert result["tags"]["genre"] == []
    assert result["tags"]["platform"] == []
    assert result["tags"]["release_year"] == "2015"
    assert result["poster_path"] == ""


def test_query_igdb_success(_mock_get_igdb_token, mock_igdb_response):
    """Test successful IGDB query."""
    mock_post = mock_igdb_response()
    results = query_igdb("The Witcher 3")

    assert len(results) == 2
    assert results[0]["canonical_title"] == "The Witcher 3: Wild Hunt"
    assert results[0]["type"] == "Game"
    assert "Role-playing (RPG)" in results[0]["tags"]["genre"]
    assert "PC" in results[0]["tags"]["platform"]
    assert results[0]["tags"]["release_year"] == "2015"
    assert results[0]["confidence"] > 0.6
    assert results[0]["source"] == "igdb"
    assert "https:" in results[0]["poster_path"]

    # Verify API call
    mock_post.assert_called_once()
    assert "Bearer mock_token" in str(mock_post.call_args)
    assert "The Witcher 3" in str(mock_post.call_args)


def test_query_igdb_with_release_year(_mock_get_igdb_token, mock_igdb_response):
    """Test IGDB query with release_year parameter."""
    mock_post = mock_igdb_response()

    # Call the function with release_year
    query_igdb("The Witcher 3", "2015")

    # Verify that the release_year was included in the query
    assert mock_post.call_count == 1
    assert "first_release_date >=" in str(mock_post.call_args)
    assert "first_release_date <=" in str(mock_post.call_args)


def test_query_igdb_no_token():
    """Test IGDB query with no token."""
    with patch("preprocessing.media_apis._get_igdb_token", return_value=None):
        results = query_igdb("The Witcher 3")
        assert len(results) == 0


def test_query_igdb_api_error(caplog, _mock_get_igdb_token, mock_http_requests):
    """Test IGDB query with API error."""
    _, mock_post = mock_http_requests
    mock_post.side_effect = requests.RequestException("API Error")

    with caplog.at_level(logging.ERROR):
        results = query_igdb("The Witcher 3")

        assert len(results) == 0
        assert "Error querying IGDB API: API Error" in caplog.text


def test_query_igdb_empty_results(_mock_get_igdb_token, mock_igdb_response):
    """Test IGDB query with empty results."""
    mock_igdb_response([])
    results = query_igdb("NonexistentGame12345")
    assert len(results) == 0


def test_query_openlibrary_success(mock_openlibrary_response):
    """Test successful OpenLibrary query."""
    mock_get = mock_openlibrary_response()

    results = query_openlibrary("The Hobbit")

    # Verify results
    assert len(results) == 2
    assert results[0]["canonical_title"] == "The Hobbit"
    assert results[0]["type"] == "Book"
    assert "Fantasy" in results[0]["tags"]["genre"]
    assert "J.R.R. Tolkien" in results[0]["tags"]["author"]
    assert results[0]["tags"]["release_year"] == "1937"
    assert results[0]["confidence"] > 0.7  # High confidence for exact match
    assert results[0]["source"] == "openlibrary"
    assert "covers.openlibrary.org" in results[0]["poster_path"]

    # Verify API call
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["params"]["title"] == "The Hobbit"


def test_query_openlibrary_with_release_year(mock_openlibrary_response):
    """Test OpenLibrary query with release_year parameter."""
    mock_get = mock_openlibrary_response()

    # Call the function with release_year
    query_openlibrary("The Hobbit", "1937")

    # Verify that the first_publish_year parameter was included in the API call
    assert mock_get.call_count == 1
    assert mock_get.call_args.kwargs["params"]["first_publish_year"] == "1937"


def test_query_openlibrary_empty_results(mock_openlibrary_response):
    """Test OpenLibrary query with empty results."""
    mock_openlibrary_response([])

    results = query_openlibrary("NonexistentBook12345")

    assert len(results) == 0


def test_query_openlibrary_api_error(caplog, mock_http_requests):
    """Test OpenLibrary query with API error."""
    mock_get, _ = mock_http_requests
    mock_get.side_effect = requests.RequestException("API Error")

    with caplog.at_level(logging.ERROR):
        results = query_openlibrary("The Hobbit")

        assert len(results) == 0
        assert "Error querying Open Library API: API Error" in caplog.text


def test_query_openlibrary_missing_fields(
    mock_api_responses, mock_openlibrary_response
):
    """Test OpenLibrary query with missing fields in response."""
    unreleased_books = [book.copy() for book in mock_api_responses["book"]]
    for book in unreleased_books:
        book["first_publish_year"] = None
    mock_openlibrary_response(unreleased_books)

    results = query_openlibrary("Book")

    # Verify results handle missing a first_publish_year are omitted
    assert len(results) == 0


def test_query_openlibrary_malformed_response(mock_http_requests):
    """Test OpenLibrary query with malformed response."""
    mock_get, _ = mock_http_requests
    mock_get.return_value.json.return_value = {"malformed": "response"}
    mock_get.side_effect = None

    results = query_openlibrary("The Hobbit")

    assert len(results) == 0


def test_query_openlibrary_confidence_calculation(
    mock_api_responses, mock_openlibrary_response
):
    """Test confidence calculation in OpenLibrary query."""
    different_title = "The Fellowship of the Ring"
    mock_openlibrary_response(
        mock_api_responses["book"]
        + [{"title": different_title, "first_publish_year": 1954}]
    )

    # Test with different search titles to test confidence calculation
    query_results = query_openlibrary("The Hobbit")

    exact_results = [
        result for result in query_results if result["canonical_title"] == "The Hobbit"
    ][0]
    similar_results = [
        result
        for result in query_results
        if result["canonical_title"] == "The Hobbit: An Unexpected Journey"
    ][0]
    different_results = [
        result
        for result in query_results
        if result["canonical_title"] == different_title
    ][0]

    # Verify confidence scores
    assert exact_results["confidence"] > similar_results["confidence"]
    assert similar_results["confidence"] > different_results["confidence"]


def test_calculate_title_similarity():
    """Test the title similarity calculation function."""
    test_cases = [
        # (title1, title2, expected_range)
        ("The Witcher 3", "The Witcher 3", (1.0, 1.0)),  # Identical
        ("The Witcher 3", "The Witcher III", (0.7, 1.0)),  # Similar
        ("The Witcher 3", "Cyberpunk 2077", (0.0, 0.5)),  # Different
        ("", "", (1.0, 1.0)),  # Empty
        ("Title", "", (0.0, 0.2)),  # One empty
    ]

    for title1, title2, (min_val, max_val) in test_cases:
        similarity = _calculate_title_similarity(title1, title2)
        assert min_val <= similarity <= max_val, f"Failed for {title1} vs {title2}"

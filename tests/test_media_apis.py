"""Unit tests for the media API client functions."""

import logging
import os
from unittest.mock import patch, MagicMock
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


@pytest.fixture(autouse=True)
def reset_igdb_token():
    """Reset IGDB token before each test to ensure consistent state."""
    media_apis.IGDB_TOKEN = None
    yield


@pytest.fixture(name="mock_tmdb_movie_response")
def fixture_mock_tmdb_movie_response():
    """Mock response for TMDB movie search."""
    return {
        "results": [
            {
                "id": 123,
                "title": "The Matrix",
                "release_date": "1999-03-31",
                "popularity": 50.0,
                "vote_average": 8.7,
                "poster_path": "/path/to/poster.jpg",
                "genre_ids": [28, 878],  # Action, Sci-Fi
                "overview": "A computer hacker learns about the true nature of reality",
            },
            {
                "id": 456,
                "title": "The Matrix Reloaded",
                "release_date": "2003-05-15",
                "popularity": 40.0,
                "vote_average": 7.2,
                "poster_path": "/path/to/poster2.jpg",
                "genre_ids": [28, 878],
                "overview": "Neo and the rebels fight against the machines",
            },
        ]
    }


@pytest.fixture(name="mock_tmdb_tv_response")
def fixture_mock_tmdb_tv_response():
    """Mock response for TMDB TV search."""
    return {
        "results": [
            {
                "id": 789,
                "name": "Stranger Things",
                "first_air_date": "2016-07-15",
                "popularity": 80.0,
                "vote_average": 8.5,
                "poster_path": "/path/to/poster3.jpg",
                "genre_ids": [18, 9648, 10765],  # Drama, Mystery, Sci-Fi & Fantasy
                "overview": "When a young boy disappears, his mother and friends must confront terrifying forces",
            }
        ]
    }


@pytest.fixture(name="mock_genre_response")
def fixture_mock_genre_response():
    """Mock response for TMDB genre list."""
    return {
        "genres": [
            {"id": 28, "name": "Action"},
            {"id": 18, "name": "Drama"},
            {"id": 878, "name": "Science Fiction"},
            {"id": 9648, "name": "Mystery"},
            {"id": 10765, "name": "Sci-Fi & Fantasy"},
        ]
    }


def test_get_genre_map(mock_genre_response):
    """Test getting and caching the genre map."""
    # Clear the cache
    GENRE_MAP_BY_MODE.clear()

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_genre_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        expected_genre_map = {
            28: "Action",
            18: "Drama",
            878: "Science Fiction",
            9648: "Mystery",
            10765: "Sci-Fi & Fantasy",
        }

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


def test_query_tmdb_movie_success(mock_tmdb_movie_response, mock_genre_response):
    """Test successful TMDB movie query."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), patch(
        "requests.get"
    ) as mock_get:
        # Set up mock responses
        def mock_response_side_effect(*args, **_):
            mock_resp = MagicMock()
            if "search/movie" in args[0]:
                mock_resp.json.return_value = mock_tmdb_movie_response
            elif "genre/movie/list" in args[0]:
                mock_resp.json.return_value = mock_genre_response
            mock_resp.raise_for_status.return_value = None
            return mock_resp

        mock_get.side_effect = mock_response_side_effect

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


def test_query_tmdb_tv_success(mock_tmdb_tv_response, mock_genre_response):
    """Test successful TMDB TV query."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), patch(
        "requests.get"
    ) as mock_get:
        # Set up mock responses
        def mock_response_side_effect(*args, **_):
            mock_resp = MagicMock()
            if "search/tv" in args[0]:
                mock_resp.json.return_value = mock_tmdb_tv_response
            elif "genre/tv/list" in args[0]:
                mock_resp.json.return_value = mock_genre_response
            mock_resp.raise_for_status.return_value = None
            return mock_resp

        mock_get.side_effect = mock_response_side_effect

        # Call the function
        results = query_tmdb("tv", "Stranger Things")

        # Verify results
        assert len(results) == 1
        assert results[0]["canonical_title"] == "Stranger Things"
        assert results[0]["type"] == "TV"
        assert "Drama" in results[0]["tags"]["genre"]
        assert results[0]["tags"]["release_year"] == "2016"
        assert results[0]["confidence"] > 0.7  # High confidence for exact match
        assert results[0]["source"] == "tmdb"


def test_query_tmdb_no_api_key(caplog):
    """Test TMDB query with no API key."""
    with patch.dict(os.environ, {}, clear=True), caplog.at_level(logging.WARNING):
        results = query_tmdb("movie", "The Matrix")

        assert len(results) == 0
        assert "TMDB_API_KEY not found in environment variables" in caplog.text


def test_query_tmdb_empty_results():
    """Test TMDB query with empty results."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), patch(
        "requests.get"
    ) as mock_get:
        # Set up mock responses
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the function
        results = query_tmdb("movie", "NonexistentMovie12345")

        # Verify results
        assert len(results) == 0


def test_query_tmdb_api_error(caplog):
    """Test TMDB query with API error."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), patch(
        "requests.get"
    ) as mock_get, caplog.at_level(logging.ERROR):
        # Set up mock to raise an exception
        mock_get.side_effect = requests.RequestException("API Error")

        # Call the function
        results = query_tmdb("movie", "The Matrix")

        # Verify results
        assert len(results) == 0
        assert "Error querying TMDB API for movie: API Error" in caplog.text


def test_query_tmdb_confidence_calculation():
    """Test confidence calculation in TMDB query."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), patch(
        "requests.get"
    ) as mock_get, patch("preprocessing.media_apis._get_genre_map", return_value={}):
        # Create mock responses with varying similarity
        exact_match = {
            "results": [
                {
                    "title": "Inception",
                    "popularity": 50.0,
                    "vote_average": 8.0,
                    "release_date": "2010-07-16",
                    "genre_ids": [],
                }
            ]
        }

        similar_match = {
            "results": [
                {
                    "title": "Inceptions",  # Slightly different
                    "popularity": 50.0,
                    "vote_average": 8.0,
                    "release_date": "2010-07-16",
                    "genre_ids": [],
                }
            ]
        }

        different_match = {
            "results": [
                {
                    "title": "Completely Different Title",
                    "popularity": 50.0,
                    "vote_average": 8.0,
                    "release_date": "2010-07-16",
                    "genre_ids": [],
                }
            ]
        }

        # Test exact match
        mock_response = MagicMock()
        mock_response.json.return_value = exact_match
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        exact_results = query_tmdb("movie", "Inception")

        # Test similar match
        mock_response.json.return_value = similar_match
        similar_results = query_tmdb("movie", "Inception")

        # Test different match
        mock_response.json.return_value = different_match
        different_results = query_tmdb("movie", "Inception")

        # Verify confidence scores
        assert exact_results[0]["confidence"] > similar_results[0]["confidence"]
        assert similar_results[0]["confidence"] > different_results[0]["confidence"]


def test_query_tmdb_limits_results():
    """Test that TMDB query limits results to top 5."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), patch(
        "requests.get"
    ) as mock_get, patch("preprocessing.media_apis._get_genre_map", return_value={}):
        # Create mock response with more than 5 results
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": f"Movie {i}",
                    "popularity": 50.0,
                    "vote_average": 7.0,
                    "release_date": "2020-01-01",
                    "genre_ids": [],
                }
                for i in range(10)  # 10 results
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the function
        results = query_tmdb("movie", "Movie")

        # Verify results are limited to 5
        assert len(results) == 5


def test_query_tmdb_handles_missing_fields():
    """Test that TMDB query handles missing fields gracefully."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), patch(
        "requests.get"
    ) as mock_get, patch("preprocessing.media_apis._get_genre_map", return_value={}):
        # Create mock response with missing fields
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Movie With Missing Fields",
                    # Missing: popularity, vote_average, release_date, poster_path
                    "genre_ids": [],
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the function
        results = query_tmdb("movie", "Movie")

        # Verify results handle missing fields
        assert len(results) == 1
        assert results[0]["canonical_title"] == "Movie With Missing Fields"
        assert results[0]["tags"]["release_year"] == ""  # Empty string for missing date
        assert "poster_path" in results[0]  # Should still have the field
        assert results[0]["confidence"] > 0  # Should still calculate confidence


@pytest.fixture(name="mock_igdb_auth_response")
def fixture_mock_igdb_auth_response():
    """Mock response for IGDB authentication."""
    return {
        "access_token": "mock_access_token",
        "expires_in": 14400,
        "token_type": "bearer",
    }


@pytest.fixture(name="mock_igdb_games_response")
def fixture_mock_igdb_games_response():
    """Mock response for IGDB games search."""
    return [
        {
            "id": 1942,
            "name": "The Witcher 3: Wild Hunt",
            "first_release_date": 1431993600,  # May 19, 2015
            "rating": 93.4,
            "aggregated_rating": 91.2,
            "cover": {
                "id": 89386,
                "url": "//images.igdb.com/igdb/image/upload/t_thumb/co1wyy.jpg",
            },
            "genres": [
                {"id": 12, "name": "Role-playing (RPG)"},
                {"id": 31, "name": "Adventure"},
            ],
            "platforms": [
                {"id": 6, "name": "PC"},
                {"id": 48, "name": "PlayStation 4"},
                {"id": 49, "name": "Xbox One"},
                {"id": 130, "name": "Nintendo Switch"},
            ],
        },
        {
            "id": 1943,
            "name": "The Witcher 3: Wild Hunt - Hearts of Stone",
            "first_release_date": 1444694400,  # October 13, 2015
            "rating": 87.5,
            "cover": {
                "id": 89387,
                "url": "//images.igdb.com/igdb/image/upload/t_thumb/co1wyz.jpg",
            },
            "genres": [
                {"id": 12, "name": "Role-playing (RPG)"},
                {"id": 31, "name": "Adventure"},
            ],
            "platforms": [
                {"id": 6, "name": "PC"},
                {"id": 48, "name": "PlayStation 4"},
                {"id": 49, "name": "Xbox One"},
            ],
        },
    ]


def test_calculate_title_similarity():
    """Test the title similarity calculation function."""
    # Identical titles
    assert _calculate_title_similarity("The Witcher 3", "The Witcher 3") == 1.0

    # Similar titles
    similarity = _calculate_title_similarity("The Witcher 3", "The Witcher III")
    assert 0.7 < similarity < 1.0

    # Different titles
    similarity = _calculate_title_similarity("The Witcher 3", "Cyberpunk 2077")
    assert similarity < 0.5

    # Empty titles
    assert _calculate_title_similarity("", "") == 1.0
    assert _calculate_title_similarity("Title", "") < 1.0


def test_get_igdb_token_success(mock_igdb_auth_response):
    """Test successful IGDB token retrieval."""
    with patch.dict(
        os.environ,
        {
            "IGDB_CLIENT_ID": "fake_client_id",
            "IGDB_CLIENT_SECRET": "fake_client_secret",
        },
    ), patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_igdb_auth_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        token = _get_igdb_token()

        assert token == "mock_access_token"
        mock_post.assert_called_once()
        assert "'client_id': 'fake_client_id'" in str(mock_post.call_args)
        assert "'client_secret': 'fake_client_secret'" in str(mock_post.call_args)


def test_get_igdb_token_missing_credentials(caplog):
    """Test IGDB token retrieval with missing credentials."""
    with patch.dict(os.environ, {}, clear=True), caplog.at_level(logging.WARNING):
        token = _get_igdb_token()

        assert token is None
        assert "IGDB_CLIENT_ID or IGDB_CLIENT_SECRET not found" in caplog.text


def test_get_igdb_token_api_error(caplog):
    """Test IGDB token retrieval with API error."""
    with patch.dict(
        os.environ,
        {
            "IGDB_CLIENT_ID": "fake_client_id",
            "IGDB_CLIENT_SECRET": "fake_client_secret",
        },
    ), patch("requests.post") as mock_post, caplog.at_level(logging.ERROR):
        mock_post.side_effect = requests.RequestException("API Error")

        token = _get_igdb_token()

        assert token is None
        assert mock_post.called


def test_format_igdb_entry():
    """Test formatting an IGDB game entry."""
    game = {
        "name": "The Witcher 3",
        "first_release_date": 1431993600,  # May 19, 2015
        "rating": 93.4,
        "aggregated_rating": 91.2,
        "cover": {"url": "//images.igdb.com/igdb/image/upload/t_thumb/co1wyy.jpg"},
        "genres": [{"name": "Role-playing (RPG)"}, {"name": "Adventure"}],
        "platforms": [{"name": "PC"}, {"name": "PlayStation 4"}],
    }

    result = _format_igdb_entry("The Witcher 3", game)

    assert result["canonical_title"] == "The Witcher 3"
    assert result["type"] == "Game"
    assert result["tags"]["genre"] == ["Role-playing (RPG)", "Adventure"]
    assert result["tags"]["platform"] == ["PC", "PlayStation 4"]
    assert result["tags"]["release_year"] == "2015"
    assert result["confidence"] > 0.9  # Should be high for exact match
    assert result["source"] == "igdb"
    assert "https:" in result["poster_path"]
    assert "720p" in result["poster_path"]  # Should upgrade image quality


def test_format_igdb_entry_missing_fields():
    """Test formatting an IGDB game entry with missing fields."""
    game = {
        "name": "Minimal Game",
        # Missing most fields
    }

    result = _format_igdb_entry("Minimal Game", game)

    assert result["canonical_title"] == "Minimal Game"
    assert result["type"] == "Game"
    assert result["tags"]["genre"] == []
    assert result["tags"]["platform"] == []
    assert result["tags"]["release_year"] == ""
    assert result["confidence"] > 0  # Should still calculate confidence
    assert result["source"] == "igdb"
    assert result["poster_path"] == ""


def test_format_igdb_entry_partial_fields():
    """Test formatting an IGDB game entry with partial fields."""
    game = {
        "name": "Partial Game",
        "first_release_date": 1577836800,  # January 1, 2020
        "genres": [],  # Empty list
        "platforms": [{"name": "PC"}],
        "cover": {"url": "thumb/image.jpg"},  # Malformed URL
    }

    result = _format_igdb_entry("Partial Game", game)

    assert result["canonical_title"] == "Partial Game"
    assert result["type"] == "Game"
    assert result["tags"]["genre"] == []
    assert result["tags"]["platform"] == ["PC"]
    assert result["tags"]["release_year"] == "2020"
    assert (
        result["poster_path"] == "720p/image.jpg"
    )  # If not starting with //, it should not add https:


def test_query_igdb_success(mock_igdb_games_response):
    """Test successful IGDB query."""
    with patch.dict(
        os.environ,
        {
            "IGDB_CLIENT_ID": "fake_client_id",
            "IGDB_CLIENT_SECRET": "fake_client_secret",
        },
    ), patch(
        "preprocessing.media_apis._get_igdb_token", return_value="mock_token"
    ), patch(
        "requests.post"
    ) as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_igdb_games_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

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


def test_query_igdb_no_token():
    """Test IGDB query with no token."""
    with patch("preprocessing.media_apis._get_igdb_token", return_value=""):
        results = query_igdb("The Witcher 3")

        assert len(results) == 0


def test_query_igdb_api_error(caplog):
    """Test IGDB query with API error."""
    with patch(
        "preprocessing.media_apis._get_igdb_token", return_value="mock_token"
    ), patch("requests.post") as mock_post, caplog.at_level(logging.ERROR):
        mock_post.side_effect = requests.RequestException("API Error")

        results = query_igdb("The Witcher 3")

        assert len(results) == 0
        assert "Error querying IGDB API: API Error" in caplog.text


def test_query_igdb_empty_results():
    """Test IGDB query with empty results."""
    with patch(
        "preprocessing.media_apis._get_igdb_token", return_value="mock_token"
    ), patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = []  # Empty results
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        results = query_igdb("NonexistentGame12345")

        assert len(results) == 0


@pytest.fixture(name="mock_openlibrary_response")
def fixture_mock_openlibrary_response():
    """Mock response for OpenLibrary search."""
    return {
        "numFound": 2,
        "start": 0,
        "docs": [
            {
                "key": "/works/OL45883W",
                "title": "The Hobbit",
                "author_name": ["J.R.R. Tolkien"],
                "first_publish_year": 1937,
                "subject": ["Fantasy", "Fiction", "Adventure"],
                "cover_i": 12345,
            },
            {
                "key": "/works/OL12345W",
                "title": "The Hobbit: An Unexpected Journey",
                "author_name": ["J.R.R. Tolkien", "Peter Jackson"],
                "first_publish_year": 2012,
                "subject": ["Fantasy", "Film Adaptation"],
                "cover_i": 67890,
            },
        ],
    }


def test_query_openlibrary_success(mock_openlibrary_response):
    """Test successful OpenLibrary query."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_openlibrary_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        results = query_openlibrary("The Hobbit")

        # Verify results
        assert len(results) == 2
        assert results[0]["canonical_title"] == "The Hobbit"
        assert results[0]["type"] == "Book"
        assert "Fantasy" in results[0]["tags"]["genre"]
        assert "J.R.R. Tolkien" in results[0]["tags"]["author"]
        assert results[0]["tags"]["release_year"] == "1937"
        assert results[0]["confidence"] > 0.8  # High confidence for exact match
        assert results[0]["source"] == "openlibrary"
        assert "covers.openlibrary.org" in results[0]["poster_path"]

        # Verify API call
        mock_get.assert_called_once()
        assert "'title': 'The Hobbit'" in str(mock_get.call_args)


def test_query_openlibrary_empty_results():
    """Test OpenLibrary query with empty results."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"numFound": 0, "start": 0, "docs": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        results = query_openlibrary("NonexistentBook12345")

        assert len(results) == 0


def test_query_openlibrary_api_error(caplog):
    """Test OpenLibrary query with API error."""
    with patch("requests.get") as mock_get, caplog.at_level(logging.ERROR):
        mock_get.side_effect = requests.RequestException("API Error")

        results = query_openlibrary("The Hobbit")

        assert len(results) == 0
        assert "Error querying Open Library API: API Error" in caplog.text


def test_query_openlibrary_missing_fields():
    """Test OpenLibrary query with missing fields in response."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "numFound": 1,
            "start": 0,
            "docs": [
                {
                    "key": "/works/OL12345W",
                    "title": "Book With Missing Fields",
                    # Missing: author_name, first_publish_year, subject, cover_i
                }
            ],
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        results = query_openlibrary("Book")

        # Verify results handle missing fields
        assert len(results) == 1
        assert results[0]["canonical_title"] == "Book With Missing Fields"
        assert results[0]["type"] == "Book"
        assert results[0]["tags"]["genre"] == []
        assert results[0]["tags"]["author"] == []
        assert results[0]["tags"]["release_year"] == ""
        assert results[0]["poster_path"] == ""
        assert results[0]["confidence"] > 0  # Should still calculate confidence


def test_query_openlibrary_malformed_response(caplog):
    """Test OpenLibrary query with malformed response."""
    with patch("requests.get") as mock_get, caplog.at_level(logging.ERROR):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "malformed": "response"
        }  # Missing 'docs' key
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        results = query_openlibrary("The Hobbit")

        assert len(results) == 0


def test_query_openlibrary_confidence_calculation():
    """Test confidence calculation in OpenLibrary query."""
    with patch("requests.get") as mock_get:
        # Create mock responses with varying similarity
        response = {
            "numFound": 1,
            "docs": [{"title": "Lord of the Rings"}],
        }

        # Test exact match
        mock_response = MagicMock()
        mock_response.json.return_value = response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        exact_results = query_openlibrary("Lord of the Rings")

        # Test similar match
        similar_results = query_openlibrary("The Lord of the Rings")

        # Test different match
        different_results = query_openlibrary("Completely Different Title")

        # Verify confidence scores
        assert exact_results[0]["confidence"] > similar_results[0]["confidence"]
        assert similar_results[0]["confidence"] > different_results[0]["confidence"]

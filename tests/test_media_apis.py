"""Unit tests for the media API client functions."""

import logging
import os
import datetime
import time
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
def mock_http_requests():
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
    """Reset API state before each test to ensure consistent state."""
    # Reset IGDB token
    media_apis.IGDB_TOKEN = None
    # Reset genre map cache
    GENRE_MAP_BY_MODE.clear()
    yield


@pytest.fixture
def mock_api_response():
    """Create a mock API response."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    return mock_response


@pytest.fixture
def mock_tmdb_responses():
    """Mock responses for TMDB API."""
    return {
        "movie": {
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
        },
        "tv": {
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
        },
        "genres": {
            "genres": [
                {"id": 28, "name": "Action"},
                {"id": 18, "name": "Drama"},
                {"id": 878, "name": "Science Fiction"},
                {"id": 9648, "name": "Mystery"},
                {"id": 10765, "name": "Sci-Fi & Fantasy"},
            ]
        }
    }


def test_get_genre_map(mock_tmdb_responses, mock_api_response, mock_http_requests):
    """Test getting and caching the genre map."""
    mock_get, _ = mock_http_requests
    mock_api_response.json.return_value = mock_tmdb_responses["genres"]
    mock_get.return_value = mock_api_response
    mock_get.side_effect = None  # Override the default side_effect

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


@pytest.fixture
def setup_tmdb_mocks(mock_tmdb_responses, mock_api_response, mock_http_requests):
    """Setup mocks for TMDB API tests."""
    def _setup_mocks(mode):
        mock_get, _ = mock_http_requests
        
        # Set up environment variables
        with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}):
            # Set up mock responses
            def mock_response_side_effect(*args, **_):
                mock_resp = mock_api_response
                if f"search/{mode}" in args[0]:
                    mock_resp.json.return_value = mock_tmdb_responses[mode]
                elif f"genre/{mode}/list" in args[0]:
                    mock_resp.json.return_value = mock_tmdb_responses["genres"]
                return mock_resp

            mock_get.side_effect = mock_response_side_effect
            return mock_get
    return _setup_mocks


def test_query_tmdb_movie_success(setup_tmdb_mocks):
    """Test successful TMDB movie query."""
    mock_get = setup_tmdb_mocks("movie")
    
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


def test_query_tmdb_tv_success(setup_tmdb_mocks):
    """Test successful TMDB TV query."""
    mock_get = setup_tmdb_mocks("tv")
    
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


@pytest.fixture
def setup_tmdb_error_tests(mock_http_requests):
    """Setup for TMDB error test cases."""
    def _setup(error_type, mock_response=None):
        mock_get, _ = mock_http_requests
        
        with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}):
            if error_type == "no_api_key":
                # Clear environment
                os.environ.clear()
            elif error_type == "empty_results":
                # Set up mock for empty results
                mock_response = MagicMock()
                mock_response.json.return_value = {"results": []}
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response
                mock_get.side_effect = None
            elif error_type == "api_error":
                # Set up mock to raise an exception
                mock_get.side_effect = requests.RequestException("API Error")
            else:
                # Custom mock response
                mock_get.return_value = mock_response
                mock_get.side_effect = None
                
            return mock_get
    return _setup


def test_query_tmdb_no_api_key(setup_tmdb_error_tests, caplog):
    """Test TMDB query with no API key."""
    setup_tmdb_error_tests("no_api_key")
    
    with caplog.at_level(logging.WARNING):
        results = query_tmdb("movie", "The Matrix")
        
        assert len(results) == 0
        assert "TMDB_API_KEY not found in environment variables" in caplog.text


def test_query_tmdb_empty_results(setup_tmdb_error_tests):
    """Test TMDB query with empty results."""
    setup_tmdb_error_tests("empty_results")
    
    results = query_tmdb("movie", "NonexistentMovie12345")
    
    assert len(results) == 0


def test_query_tmdb_api_error(setup_tmdb_error_tests, caplog):
    """Test TMDB query with API error."""
    setup_tmdb_error_tests("api_error")
    
    with caplog.at_level(logging.ERROR):
        results = query_tmdb("movie", "The Matrix")
        
        assert len(results) == 0
        assert "Error querying TMDB API for movie: API Error" in caplog.text


@pytest.fixture
def tmdb_confidence_test_data():
    """Test data for TMDB confidence calculation tests."""
    return {
        "exact_match": {
            "results": [
                {
                    "title": "Inception",
                    "popularity": 50.0,
                    "vote_average": 8.0,
                    "release_date": "2010-07-16",
                    "genre_ids": [],
                }
            ]
        },
        "similar_match": {
            "results": [
                {
                    "title": "Inceptions",  # Slightly different
                    "popularity": 50.0,
                    "vote_average": 8.0,
                    "release_date": "2010-07-16",
                    "genre_ids": [],
                }
            ]
        },
        "different_match": {
            "results": [
                {
                    "title": "Completely Different Title",
                    "popularity": 50.0,
                    "vote_average": 8.0,
                    "release_date": "2010-07-16",
                    "genre_ids": [],
                }
            ]
        },
        "many_results": {
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
        },
        "missing_fields": {
            "results": [
                {
                    "title": "Movie With Missing Fields",
                    # Missing: popularity, vote_average, release_date, poster_path
                    "genre_ids": [],
                }
            ]
        }
    }


def test_query_tmdb_confidence_calculation(tmdb_confidence_test_data, mock_api_response, mock_http_requests):
    """Test confidence calculation in TMDB query."""
    mock_get, _ = mock_http_requests
    mock_get.side_effect = None
    mock_get.return_value = mock_api_response
    
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), patch("preprocessing.media_apis._get_genre_map", return_value={}):
        # Test exact match
        mock_api_response.json.return_value = tmdb_confidence_test_data["exact_match"]
        exact_results = query_tmdb("movie", "Inception")

        # Test similar match
        mock_api_response.json.return_value = tmdb_confidence_test_data["similar_match"]
        similar_results = query_tmdb("movie", "Inception")

        # Test different match
        mock_api_response.json.return_value = tmdb_confidence_test_data["different_match"]
        different_results = query_tmdb("movie", "Inception")

        # Verify confidence scores
        assert exact_results[0]["confidence"] > similar_results[0]["confidence"]
        assert similar_results[0]["confidence"] > different_results[0]["confidence"]


def test_query_tmdb_limits_results(tmdb_confidence_test_data, mock_api_response, mock_http_requests):
    """Test that TMDB query limits results to top 5."""
    mock_get, _ = mock_http_requests
    mock_get.side_effect = None
    mock_get.return_value = mock_api_response
    
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), patch("preprocessing.media_apis._get_genre_map", return_value={}):
        # Create mock response with more than 5 results
        mock_api_response.json.return_value = tmdb_confidence_test_data["many_results"]

        # Call the function
        results = query_tmdb("movie", "Movie")

        # Verify results are limited to 5
        assert len(results) == 5


def test_query_tmdb_handles_missing_fields(tmdb_confidence_test_data, mock_api_response, mock_http_requests):
    """Test that TMDB query handles missing fields gracefully."""
    mock_get, _ = mock_http_requests
    mock_get.side_effect = None
    mock_get.return_value = mock_api_response
    
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), patch("preprocessing.media_apis._get_genre_map", return_value={}):
        # Create mock response with missing fields
        mock_api_response.json.return_value = tmdb_confidence_test_data["missing_fields"]

        # Call the function
        results = query_tmdb("movie", "Movie")

        # Verify that results missing a release date are omitted
        assert len(results) == 0


@pytest.fixture
def mock_igdb_responses():
    """Mock responses for IGDB API."""
    return {
        "auth": {
            "access_token": "mock_access_token",
            "expires_in": 14400,
            "token_type": "bearer",
        },
        "games": [
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
        ],
        "empty": []
    }


@pytest.fixture
def setup_igdb_mocks(mock_igdb_responses, mock_api_response, mock_http_requests):
    """Setup mocks for IGDB API tests."""
    def _setup_mocks(response_type="games", error_type=None):
        _, mock_post = mock_http_requests
        
        with patch.dict(
            os.environ,
            {
                "IGDB_CLIENT_ID": "fake_client_id",
                "IGDB_CLIENT_SECRET": "fake_client_secret",
            }
        ):
            if error_type == "missing_credentials":
                os.environ.clear()
                return None
                
            if error_type == "api_error":
                mock_post.side_effect = requests.RequestException("API Error")
                return mock_post
            
            mock_api_response.json.return_value = mock_igdb_responses[response_type]
            mock_post.return_value = mock_api_response
            mock_post.side_effect = None
            return mock_post
    return _setup_mocks


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


def test_get_igdb_token_success(setup_igdb_mocks):
    """Test successful IGDB token retrieval."""
    mock_post = setup_igdb_mocks("auth")
    
    token = _get_igdb_token()
    
    assert token == "mock_access_token"
    mock_post.assert_called_once()
    assert "'client_id': 'fake_client_id'" in str(mock_post.call_args)
    assert "'client_secret': 'fake_client_secret'" in str(mock_post.call_args)


def test_get_igdb_token_missing_credentials(setup_igdb_mocks, caplog):
    """Test IGDB token retrieval with missing credentials."""
    setup_igdb_mocks(error_type="missing_credentials")
    
    with caplog.at_level(logging.WARNING):
        token = _get_igdb_token()
        
        assert token is None
        assert "IGDB_CLIENT_ID or IGDB_CLIENT_SECRET not found" in caplog.text


def test_get_igdb_token_api_error(setup_igdb_mocks, caplog):
    """Test IGDB token retrieval with API error."""
    mock_post = setup_igdb_mocks(error_type="api_error")
    
    with caplog.at_level(logging.ERROR):
        token = _get_igdb_token()
        
        assert token is None
        assert mock_post.called


@pytest.fixture
def igdb_test_games():
    """Test game data for IGDB formatting tests."""
    return {
        "complete": {
            "name": "The Witcher 3",
            "first_release_date": 1431993600,  # May 19, 2015
            "rating": 93.4,
            "aggregated_rating": 91.2,
            "cover": {"url": "//images.igdb.com/igdb/image/upload/t_thumb/co1wyy.jpg"},
            "genres": [{"name": "Role-playing (RPG)"}, {"name": "Adventure"}],
            "platforms": [{"name": "PC"}, {"name": "PlayStation 4"}],
        },
        "minimal": {
            "name": "Minimal Game",
            # Missing most fields
        },
        "partial": {
            "name": "Partial Game",
            "first_release_date": 1577836800,  # January 1, 2020
            "genres": [],  # Empty list
            "platforms": [{"name": "PC"}],
            "cover": {"url": "thumb/image.jpg"},  # Malformed URL
        }
    }


def test_format_igdb_entry(igdb_test_games):
    """Test formatting an IGDB game entry."""
    result = _format_igdb_entry("The Witcher 3", igdb_test_games["complete"])

    assert result["canonical_title"] == "The Witcher 3"
    assert result["type"] == "Game"
    assert result["tags"]["genre"] == ["Role-playing (RPG)", "Adventure"]
    assert result["tags"]["platform"] == ["PC", "PlayStation 4"]
    assert result["tags"]["release_year"] == "2015"
    assert result["confidence"] > 0.9  # Should be high for exact match
    assert result["source"] == "igdb"
    assert "https:" in result["poster_path"]
    assert "720p" in result["poster_path"]  # Should upgrade image quality


def test_format_igdb_entry_missing_fields(igdb_test_games):
    """Test formatting an IGDB game entry with missing fields."""
    result = _format_igdb_entry("Minimal Game", igdb_test_games["minimal"])

    # Results without a first_release_date should not be included
    assert result is None


def test_format_igdb_entry_partial_fields(igdb_test_games):
    """Test formatting an IGDB game entry with partial fields."""
    result = _format_igdb_entry("Partial Game", igdb_test_games["partial"])

    assert result["canonical_title"] == "Partial Game"
    assert result["type"] == "Game"
    assert result["tags"]["genre"] == []
    assert result["tags"]["platform"] == ["PC"]
    assert result["tags"]["release_year"] == "2020"
    assert result["poster_path"] == "720p/image.jpg"  # Should replace thumb with 720p


def test_query_igdb_success(setup_igdb_mocks):
    """Test successful IGDB query."""
    mock_post = setup_igdb_mocks("games")
    
    with patch("preprocessing.media_apis._get_igdb_token", return_value="mock_token"):
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
    with patch("preprocessing.media_apis._get_igdb_token", return_value=None):
        results = query_igdb("The Witcher 3")
        assert len(results) == 0


def test_query_igdb_api_error(setup_igdb_mocks, caplog):
    """Test IGDB query with API error."""
    mock_post = setup_igdb_mocks(error_type="api_error")
    
    with patch("preprocessing.media_apis._get_igdb_token", return_value="mock_token"), caplog.at_level(logging.ERROR):
        results = query_igdb("The Witcher 3")
        
        assert len(results) == 0
        assert "Error querying IGDB API: API Error" in caplog.text


def test_query_igdb_empty_results(setup_igdb_mocks):
    """Test IGDB query with empty results."""
    mock_post = setup_igdb_mocks("empty")
    
    with patch("preprocessing.media_apis._get_igdb_token", return_value="mock_token"):
        results = query_igdb("NonexistentGame12345")
        
        assert len(results) == 0


@pytest.fixture
def mock_openlibrary_responses():
    """Mock responses for OpenLibrary API."""
    return {
        "success": {
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
        },
        "empty": {
            "numFound": 0, 
            "start": 0, 
            "docs": []
        },
        "missing_fields": {
            "numFound": 1,
            "start": 0,
            "docs": [
                {
                    "key": "/works/OL12345W",
                    "title": "Book With Missing Fields",
                    # Missing: author_name, first_publish_year, subject, cover_i
                }
            ],
        },
        "malformed": {
            "malformed": "response"  # Missing 'docs' key
        },
        "confidence_test": {
            "numFound": 1,
            "docs": [
                {
                    "title": "Lord of the Rings",
                    "first_publish_year": 1954,
                }
            ],
        }
    }


@pytest.fixture
def setup_openlibrary_mocks(mock_openlibrary_responses, mock_api_response, mock_http_requests):
    """Setup mocks for OpenLibrary API tests."""
    def _setup_mocks(response_type="success", error_type=None):
        mock_get, _ = mock_http_requests
        
        if error_type == "api_error":
            mock_get.side_effect = requests.RequestException("API Error")
            return mock_get
            
        mock_api_response.json.return_value = mock_openlibrary_responses[response_type]
        mock_get.return_value = mock_api_response
        mock_get.side_effect = None
        return mock_get
    return _setup_mocks


def test_query_openlibrary_success(setup_openlibrary_mocks):
    """Test successful OpenLibrary query."""
    mock_get = setup_openlibrary_mocks("success")
    
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


def test_query_openlibrary_empty_results(setup_openlibrary_mocks):
    """Test OpenLibrary query with empty results."""
    setup_openlibrary_mocks("empty")
    
    results = query_openlibrary("NonexistentBook12345")
    
    assert len(results) == 0


def test_query_openlibrary_api_error(setup_openlibrary_mocks, caplog):
    """Test OpenLibrary query with API error."""
    setup_openlibrary_mocks(error_type="api_error")
    
    with caplog.at_level(logging.ERROR):
        results = query_openlibrary("The Hobbit")
        
        assert len(results) == 0
        assert "Error querying Open Library API: API Error" in caplog.text


def test_query_openlibrary_missing_fields(setup_openlibrary_mocks):
    """Test OpenLibrary query with missing fields in response."""
    setup_openlibrary_mocks("missing_fields")
    
    results = query_openlibrary("Book")
    
    # Verify results handle missing a first_publish_year are omitted
    assert len(results) == 0


def test_query_openlibrary_malformed_response(setup_openlibrary_mocks):
    """Test OpenLibrary query with malformed response."""
    setup_openlibrary_mocks("malformed")
    
    results = query_openlibrary("The Hobbit")
    
    assert len(results) == 0


def test_query_openlibrary_confidence_calculation(setup_openlibrary_mocks):
    """Test confidence calculation in OpenLibrary query."""
    mock_get = setup_openlibrary_mocks("confidence_test")
    
    # Test with different search titles to test confidence calculation
    exact_results = query_openlibrary("Lord of the Rings")
    similar_results = query_openlibrary("The Lord of the Rings")
    different_results = query_openlibrary("Completely Different Title")
    
    # Verify confidence scores
    assert exact_results[0]["confidence"] > similar_results[0]["confidence"]
    assert similar_results[0]["confidence"] > different_results[0]["confidence"]

"""Unit tests for the media API client functions."""

import logging
import os
from unittest.mock import patch, MagicMock
import pytest
import requests

from preprocessing.media_apis import (
    query_tmdb,
    query_igdb,
    query_openlibrary,
    _get_genre_map,
    GENRE_MAP_BY_MODE,
)


@pytest.fixture
def mock_tmdb_movie_response():
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


@pytest.fixture
def mock_tmdb_tv_response():
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


@pytest.fixture
def mock_genre_response():
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
        
        # First call should make the API request
        genre_map = _get_genre_map("movie")
        assert mock_get.call_count == 1
        assert genre_map == {28: "Action", 18: "Drama", 878: "Science Fiction", 
                            9648: "Mystery", 10765: "Sci-Fi & Fantasy"}
        
        # Second call should use the cached value
        genre_map = _get_genre_map("movie")
        assert mock_get.call_count == 1
        
        # Different mode should make a new request
        genre_map = _get_genre_map("tv")
        assert mock_get.call_count == 2


def test_query_tmdb_movie_success(mock_tmdb_movie_response, mock_genre_response):
    """Test successful TMDB movie query."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), \
         patch("requests.get") as mock_get:
        # Set up mock responses
        def mock_response_side_effect(*args, **kwargs):
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
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), \
         patch("requests.get") as mock_get:
        # Set up mock responses
        def mock_response_side_effect(*args, **kwargs):
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
    with patch.dict(os.environ, {}, clear=True), \
         caplog.at_level(logging.WARNING):
        results = query_tmdb("movie", "The Matrix")
        
        assert len(results) == 0
        assert "TMDB_API_KEY not found in environment variables" in caplog.text


def test_query_tmdb_empty_results():
    """Test TMDB query with empty results."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), \
         patch("requests.get") as mock_get:
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
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), \
         patch("requests.get") as mock_get, \
         caplog.at_level(logging.ERROR):
        # Set up mock to raise an exception
        mock_get.side_effect = requests.RequestException("API Error")
        
        # Call the function
        results = query_tmdb("movie", "The Matrix")
        
        # Verify results
        assert len(results) == 0
        assert "Error querying TMDB API for movie: API Error" in caplog.text


def test_query_tmdb_confidence_calculation():
    """Test confidence calculation in TMDB query."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), \
         patch("requests.get") as mock_get, \
         patch("preprocessing.media_apis._get_genre_map", return_value={}):
        # Create mock responses with varying similarity
        exact_match = {
            "results": [
                {
                    "title": "Inception",
                    "popularity": 50.0,
                    "vote_average": 8.0,
                    "release_date": "2010-07-16",
                    "genre_ids": []
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
                    "genre_ids": []
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
                    "genre_ids": []
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


def test_query_tmdb_sorts_by_confidence():
    """Test that TMDB query results are sorted by confidence."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), \
         patch("requests.get") as mock_get, \
         patch("preprocessing.media_apis._get_genre_map", return_value={}):
        # Create mock response with multiple results
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Star Wars: The Last Jedi",  # Less similar to query
                    "popularity": 70.0,
                    "vote_average": 7.0,
                    "release_date": "2017-12-15",
                    "genre_ids": []
                },
                {
                    "title": "Star Wars",  # More similar to query
                    "popularity": 60.0,
                    "vote_average": 8.0,
                    "release_date": "1977-05-25",
                    "genre_ids": []
                },
                {
                    "title": "Star Wars: The Empire Strikes Back",
                    "popularity": 65.0,
                    "vote_average": 8.5,
                    "release_date": "1980-05-21",
                    "genre_ids": []
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Call the function
        results = query_tmdb("movie", "Star Wars")
        
        # Verify results are sorted by confidence
        assert len(results) == 3
        assert results[0]["canonical_title"] == "Star Wars"  # Most similar should be first
        assert results[0]["confidence"] > results[1]["confidence"]
        assert results[1]["confidence"] > results[2]["confidence"]


def test_query_tmdb_limits_results():
    """Test that TMDB query limits results to top 5."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), \
         patch("requests.get") as mock_get, \
         patch("preprocessing.media_apis._get_genre_map", return_value={}):
        # Create mock response with more than 5 results
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"title": f"Movie {i}", "popularity": 50.0, "vote_average": 7.0, 
                 "release_date": "2020-01-01", "genre_ids": []} 
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
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}), \
         patch("requests.get") as mock_get, \
         patch("preprocessing.media_apis._get_genre_map", return_value={}):
        # Create mock response with missing fields
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Movie With Missing Fields",
                    # Missing: popularity, vote_average, release_date, poster_path
                    "genre_ids": []
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

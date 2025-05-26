"""
Tests for the Streamlit app's media entries loading functionality.
"""

import json
from unittest.mock import patch, mock_open

import pytest

from app import streamlit_app

# Sample media entries for testing
SAMPLE_MEDIA_ENTRIES = [
    {
        "title": "Test Movie",
        "canonical_title": "Test Movie",
        "type": "Movie",
        "start_date": "2023-01-01",
        "finish_date": "2023-01-01",
        "duration_days": 0,
        "status": "completed",
        "tags": {"genre": ["Action"], "platform": ["Theater"], "mood": ["Exciting"]},
        "confidence": 0.95,
        "raw_text": "Watched Test Movie",
        "warnings": [],
    }
]


@pytest.fixture(autouse=True)
def mock_streamlit_error():
    """Fixture to mock streamlit error call."""
    with patch("app.streamlit_app.st.error") as mock_error:
        yield mock_error


def test_load_media_entries_file_exists():
    """Test loading media entries when the file exists."""
    mock_json = json.dumps(SAMPLE_MEDIA_ENTRIES)

    with patch("os.path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data=mock_json)
    ):
        entries = streamlit_app.load_media_entries()
        assert entries == SAMPLE_MEDIA_ENTRIES


def test_load_media_entries_file_not_found():
    """Test loading media entries when the file doesn't exist."""
    with patch("os.path.exists", return_value=False), patch(
        "streamlit.error"
    ) as mock_st_error:
        entries = streamlit_app.load_media_entries()
        assert entries == []
        mock_st_error.assert_called_once()


def test_load_media_entries_invalid_json():
    """Test loading media entries when the JSON is malformed."""
    invalid_json = "{ this is not valid JSON }"
    
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=invalid_json)), \
         patch("streamlit.error") as mock_st_error:
        entries = streamlit_app.load_media_entries()
        assert entries == []
        mock_st_error.assert_called_once()


def test_main_function_imports():
    """Smoke test to ensure the main function imports correctly."""
    assert callable(streamlit_app.main)

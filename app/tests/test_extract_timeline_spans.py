"""
Tests for the Streamlit app's media entries loading functionality.
"""

import json
import logging
from unittest.mock import patch, mock_open

import pytest
import streamlit as st

from app import extract_timeline_spans


@pytest.fixture(autouse=True, name="mock_streamlit_error")
def fixture_mock_streamlit_error():
    """Fixture to mock streamlit error call."""
    with patch("app.extract_timeline_spans.st.error") as mock_error:
        yield mock_error


@pytest.fixture(autouse=True)
def fixture_clear_cache():
    """Fixture to clear Streamlit cache before each test."""
    # Clear the cache before each test
    st.cache_data.clear()


def test_load_media_entries_file_exists(sample_entries):
    """Test loading media entries when the file exists."""
    mock_json = json.dumps(sample_entries)

    with patch("os.path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data=mock_json)
    ):
        entries = extract_timeline_spans.load_media_entries()
        assert entries == sample_entries


def test_load_media_entries_file_not_found(mock_streamlit_error):
    """Test loading media entries when the file doesn't exist."""
    with patch("os.path.exists", return_value=False):
        entries = extract_timeline_spans.load_media_entries()

    assert entries == []
    mock_streamlit_error.assert_called_once_with(
        "File not found: preprocessing/processed_data/media_entries.json"
    )


def test_load_media_entries_invalid_json(caplog, mock_streamlit_error):
    """Test loading media entries when the JSON is malformed."""
    invalid_json = "{ this is not valid JSON }"

    with patch("os.path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data=invalid_json)
    ), caplog.at_level(logging.ERROR):
        entries = extract_timeline_spans.load_media_entries()

    assert entries == []
    mock_streamlit_error.assert_called_once_with(
        "Error decoding JSON from preprocessing/processed_data/media_entries.json"
    )
    assert "JSON decode error" in caplog.text

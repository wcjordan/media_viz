"""
Tests for the Streamlit app's media entries loading functionality.
"""

from datetime import datetime
import json
import logging
from unittest.mock import patch, mock_open

import pytest
import streamlit as st


from app.media_entries import (
    _extract_timeline_spans,
    _generate_week_axis,
    _get_timeline_range,
    load_media_entries,
)


@pytest.fixture(autouse=True, name="mock_streamlit_error")
def fixture_mock_streamlit_error():
    """Fixture to mock streamlit error call."""
    with patch("app.media_entries.st.error") as mock_error:
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
        entries = load_media_entries()
        assert entries == sample_entries


def test_load_media_entries_file_not_found(mock_streamlit_error):
    """Test loading media entries when the file doesn't exist."""
    with patch("os.path.exists", return_value=False):
        entries = load_media_entries()

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
        entries = load_media_entries()

    assert entries == []
    mock_streamlit_error.assert_called_once_with(
        "Error decoding JSON from preprocessing/processed_data/media_entries.json"
    )
    assert "JSON decode error" in caplog.text


def test_get_timeline_range(sample_entries):
    """Test getting min and max dates from entries."""
    min_date, max_date = _get_timeline_range(sample_entries)

    # Min date should be adjusted to start of week
    assert min_date.year == 2021
    assert min_date.month == 2
    assert min_date.day == 1

    # Max date should be adjusted to end of week
    assert max_date.year == 2021
    assert max_date.month == 10
    assert max_date.day == 4


def test_generate_week_axis():
    """Test generating week axis DataFrame."""
    min_date = datetime(2023, 1, 1)
    max_date = datetime(2023, 1, 31)

    weeks_df = _generate_week_axis(min_date, max_date)

    # Should have 5 weeks (Jan 1-7, 8-14, 15-21, 22-28, 29-31)
    assert len(weeks_df) == 5
    assert weeks_df["week_index"].tolist() == [0, 1, 2, 3, 4]
    assert all(weeks_df["year"] == 2023)

    # Check first and last week
    assert weeks_df.iloc[0]["start_date"] == min_date
    assert weeks_df.iloc[-1]["end_date"] >= max_date


def test_extract_timeline_spans(sample_entries):
    """Test extracting timeline spans from entries."""
    spans, min_date, max_date = _extract_timeline_spans(sample_entries)

    # Check min and max dates
    assert min_date is not None
    assert max_date is not None
    assert min_date < max_date

    # Check spans
    assert len(spans) > 0
    assert "entry_idx" in spans[0]


def test_extract_timeline_spans_empty():
    """Test extracting timeline spans with empty entries."""
    spans, min_date, max_date = _extract_timeline_spans([])

    # Check min and max dates
    assert min_date is None
    assert max_date is None
    assert len(spans) == 0


def test_extract_timeline_spans_missing_dates():
    """Test preparing timeline data with entries missing dates."""
    entries = [
        {
            "title": "No Dates Entry",
            "canonical_title": "No Dates Entry",
            "type": "Movie",
            "tags": {},
        }
    ]

    spans, min_date, max_date = _extract_timeline_spans(entries)

    # Should have weeks but no spans
    assert min_date is None
    assert max_date is None
    assert len(spans) == 0

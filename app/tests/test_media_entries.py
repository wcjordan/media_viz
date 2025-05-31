"""
Tests for the Streamlit app's media entries loading functionality.
"""

import json
import logging
from datetime import datetime
from unittest.mock import patch, mock_open

import pytest
import streamlit as st


from app.media_entries import (
    extract_timeline_spans,
    _get_timeline_range,
    load_media_entries,
)
from app.utils import compute_week_index


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


def test_extract_timeline_spans(sample_entries):
    """Test extracting timeline spans from entries."""
    spans, min_date, max_date = extract_timeline_spans(sample_entries)

    # Check min and max dates
    assert min_date is not None
    assert max_date is not None
    assert min_date < max_date

    # Check spans
    assert len(spans) > 0
    assert "entry_idx" in spans[0]

    # Verify date field calculations
    first_span = next(span for span in spans if span["title"] == "Test Movie")
    assert first_span["start_date"] == datetime(2021, 2, 1)
    assert first_span["end_date"] == datetime(2021, 2, 8)

    # Verify week index calculations
    assert first_span["start_week"] == 0
    assert first_span["end_week"] == 1

    # Check in-progress entries (only started_dates)
    game_span = next(span for span in spans if span["title"] == "In Progress Game")
    assert game_span["start_date"] is not None
    assert game_span["end_date"] is None
    expected_start_week = compute_week_index(game_span["start_date"], min_date)
    assert expected_start_week > 1
    assert game_span["start_week"] == expected_start_week
    assert game_span["end_week"] is None

    # Check finish-only entries (only finished_dates)
    book_span = next(span for span in spans if span["title"] == "Finished Book")
    assert book_span["start_date"] is None
    assert book_span["end_date"] is not None
    assert book_span["start_week"] is None
    expected_end_week = compute_week_index(book_span["end_date"], min_date)
    assert expected_end_week > 1
    assert book_span["end_week"] == expected_end_week


def test_extract_timeline_spans_empty():
    """Test extracting timeline spans with empty entries."""
    spans, min_date, max_date = extract_timeline_spans([])

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

    spans, min_date, max_date = extract_timeline_spans(entries)

    # Should have weeks but no spans
    assert min_date is None
    assert max_date is None
    assert len(spans) == 0


def test_extract_timeline_spans_multiple_dates(caplog, sample_entries):
    """Test handling of entries with multiple start/end dates."""
    entries = sample_entries[:1]
    entries[0]["started_dates"] = ["2021-02-01", "2021-03-01"]  # Multiple starts
    entries[0]["finished_dates"] = ["2021-02-15", "2021-03-15"]  # Multiple ends

    spans, _, _ = extract_timeline_spans(entries)

    # Should use minimum dates
    span = spans[0]
    assert span["start_date"] == datetime(2021, 2, 1)  # Min of start dates
    assert span["end_date"] == datetime(2021, 3, 15)  # Max of end dates

    # Should log warnings about multiple dates
    assert "Multiple start dates found" in caplog.text
    assert "Multiple end dates found" in caplog.text


def test_extract_timeline_spans_week_boundaries(sample_entries):
    """Test week calculations across different scenarios."""
    entries = sample_entries[:1]
    entries[0]["started_dates"] = ["2021-02-07"]  # Sunday
    entries[0]["finished_dates"] = ["2021-02-09"]  # Tuesday

    spans, min_date, _ = extract_timeline_spans(entries)
    span = spans[0]

    # Verify week indices are calculated correctly
    assert min_date == datetime(2021, 2, 1)  # Adjusted to start of week
    assert span["start_date"] == datetime(2021, 2, 7)  # Actual dates not adjusted
    assert span["end_date"] == datetime(2021, 2, 9)  # Actual dates not adjusted
    assert span["start_week"] == 1  # Sunday adjusted forward to Monday
    assert span["end_week"] == 1  # Tuesday is still in the same week

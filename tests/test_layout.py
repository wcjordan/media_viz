"""
Tests for the timeline layout functionality.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from app.streamlit_app import (
    calculate_opacity,
    compute_week_index,
    generate_week_axis,
    get_date_range,
    prepare_timeline_data,
)

# Sample media entries for testing
SAMPLE_ENTRIES = [
    {
        "title": "Test Movie",
        "canonical_title": "Test Movie",
        "type": "Movie",
        "start_date": "2023-01-01",
        "finish_date": "2023-01-15",
        "duration_days": 14,
        "status": "completed",
        "tags": {"genre": ["Action"], "platform": ["Theater"], "mood": ["Exciting"]},
        "confidence": 0.95,
        "raw_text": "Watched Test Movie",
        "warnings": [],
    },
    {
        "title": "In Progress Game",
        "canonical_title": "In Progress Game",
        "type": "Game",
        "start_date": "2023-02-01",
        "finish_date": None,
        "duration_days": None,
        "status": "in_progress",
        "tags": {"genre": ["RPG"], "platform": ["PC"], "mood": ["Exciting"]},
        "confidence": 0.9,
        "raw_text": "Started In Progress Game",
        "warnings": [],
    },
    {
        "title": "Finished Book",
        "canonical_title": "Finished Book",
        "type": "Book",
        "start_date": None,
        "finish_date": "2023-03-15",
        "duration_days": None,
        "status": "completed",
        "tags": {"genre": ["Fiction"], "platform": ["Kindle"], "mood": ["Thoughtful"]},
        "confidence": 0.85,
        "raw_text": "Finished Book",
        "warnings": [],
    },
    {
        "title": "Long TV Show",
        "canonical_title": "Long TV Show",
        "type": "TV",
        "start_date": "2023-01-01",
        "finish_date": "2023-12-31",
        "duration_days": 364,
        "status": "completed",
        "tags": {"genre": ["Drama"], "platform": ["Netflix"], "mood": ["Intense"]},
        "confidence": 0.95,
        "raw_text": "Finished Long TV Show",
        "warnings": [],
    },
]


def test_compute_week_index():
    """Test computing week index from date."""
    min_date = datetime(2023, 1, 1)
    
    # Same week
    assert compute_week_index("2023-01-01", min_date) == 0
    assert compute_week_index("2023-01-07", min_date) == 0
    
    # Next week
    assert compute_week_index("2023-01-08", min_date) == 1
    
    # Several weeks later
    assert compute_week_index("2023-02-01", min_date) == 4
    assert compute_week_index("2023-12-31", min_date) == 52


def test_get_date_range():
    """Test getting min and max dates from entries."""
    min_date, max_date = get_date_range(SAMPLE_ENTRIES)
    
    # Min date should be adjusted to start of week
    assert min_date.year == 2023
    assert min_date.month == 1
    assert min_date.day <= 1  # Could be earlier if Jan 1 wasn't a Monday
    
    # Max date should be adjusted to end of week
    assert max_date.year == 2023
    assert max_date.month == 12
    assert max_date.day >= 31  # Could be later if Dec 31 wasn't a Sunday


def test_generate_week_axis():
    """Test generating week axis DataFrame."""
    min_date = datetime(2023, 1, 1)
    max_date = datetime(2023, 1, 31)
    
    weeks_df = generate_week_axis(min_date, max_date)
    
    # Should have 5 weeks (Jan 1-7, 8-14, 15-21, 22-28, 29-31)
    assert len(weeks_df) == 5
    assert weeks_df["week_index"].tolist() == [0, 1, 2, 3, 4]
    assert all(weeks_df["year"] == 2023)
    
    # Check first and last week
    assert weeks_df.iloc[0]["start_date"] == min_date
    assert weeks_df.iloc[-1]["end_date"] >= max_date


def test_calculate_opacity():
    """Test opacity calculation for different scenarios."""
    # Completed entry (full opacity)
    assert calculate_opacity(0, 2, 1, True, True, False) == 0.9
    
    # In-progress entry (fade out)
    assert calculate_opacity(0, 10, 0, True, False, False) == 0.9  # Start week (full opacity)
    assert calculate_opacity(0, 10, 5, True, False, False) < 0.9  # Middle (partial opacity)
    assert calculate_opacity(0, 10, 10, True, False, False) == 0.2  # End (min opacity)
    
    # Finish-only entry (fade in)
    assert calculate_opacity(0, 10, 0, False, True, False) == 0.2  # Start (min opacity)
    assert calculate_opacity(0, 10, 5, False, True, False) < 0.9  # Middle (partial opacity)
    assert calculate_opacity(0, 10, 10, False, True, False) == 0.9  # End week (full opacity)
    
    # Long duration entry (fade out from start, fade in to end)
    assert calculate_opacity(0, 40, 0, True, True, True) == 0.9  # Start (full opacity)
    assert calculate_opacity(0, 40, 5, True, True, True) < 0.9  # Near start (fading)
    assert calculate_opacity(0, 40, 20, True, True, True) == 0.2  # Middle (min opacity)
    assert calculate_opacity(0, 40, 35, True, True, True) < 0.9  # Near end (fading)
    assert calculate_opacity(0, 40, 40, True, True, True) == 0.9  # End (full opacity)


def test_prepare_timeline_data():
    """Test preparing timeline data from entries."""
    weeks_df, bars_df = prepare_timeline_data(SAMPLE_ENTRIES)
    
    # Check weeks DataFrame
    assert not weeks_df.empty
    assert "week_index" in weeks_df.columns
    assert "year" in weeks_df.columns
    
    # Check bars DataFrame
    assert not bars_df.empty
    assert "entry_id" in bars_df.columns
    assert "week_index" in bars_df.columns
    assert "opacity" in bars_df.columns
    assert "color" in bars_df.columns
    
    # Check that we have the right number of entries
    unique_entries = bars_df["entry_id"].unique()
    assert len(unique_entries) == len(SAMPLE_ENTRIES)
    
    # Check that in-progress entry has decreasing opacity
    in_progress_bars = bars_df[bars_df["title"] == "In Progress Game"].sort_values("week_index")
    opacities = in_progress_bars["opacity"].tolist()
    assert opacities[0] > opacities[-1]  # First week should have higher opacity than last
    
    # Check that finish-only entry has increasing opacity
    finish_only_bars = bars_df[bars_df["title"] == "Finished Book"].sort_values("week_index")
    opacities = finish_only_bars["opacity"].tolist()
    assert opacities[0] < opacities[-1]  # First week should have lower opacity than last
    
    # Check that long entry has appropriate fade pattern
    long_entry_bars = bars_df[bars_df["title"] == "Long TV Show"].sort_values("week_index")
    opacities = long_entry_bars["opacity"].tolist()
    assert opacities[0] > opacities[len(opacities) // 2]  # Start higher than middle
    assert opacities[-1] > opacities[len(opacities) // 2]  # End higher than middle


def test_prepare_timeline_data_empty():
    """Test preparing timeline data with empty entries."""
    weeks_df, bars_df = prepare_timeline_data([])
    
    assert weeks_df.empty
    assert bars_df.empty


def test_prepare_timeline_data_missing_dates():
    """Test preparing timeline data with entries missing dates."""
    entries = [
        {
            "title": "No Dates Entry",
            "canonical_title": "No Dates Entry",
            "type": "Movie",
            "tags": {},
        }
    ]
    
    weeks_df, bars_df = prepare_timeline_data(entries)
    
    # Should have weeks but no bars
    assert not weeks_df.empty
    assert bars_df.empty

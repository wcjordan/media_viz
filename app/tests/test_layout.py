"""
Tests for the timeline layout functionality.
"""

from datetime import datetime

from app.extract_timeline_spans import (
    _get_date_range,
    generate_week_axis,
    prepare_timeline_data,
)
from app.utils import compute_week_index


def test_compute_week_index():
    """Test computing week index from date."""
    min_date = datetime(2023, 1, 1)

    # Same week
    assert (
        compute_week_index(datetime.strptime("2023-01-01", "%Y-%m-%d"), min_date) == 0
    )
    assert (
        compute_week_index(datetime.strptime("2023-01-07", "%Y-%m-%d"), min_date) == 0
    )

    # Next week
    assert (
        compute_week_index(datetime.strptime("2023-01-08", "%Y-%m-%d"), min_date) == 1
    )

    # Several weeks later
    assert (
        compute_week_index(datetime.strptime("2023-02-01", "%Y-%m-%d"), min_date) == 4
    )
    assert (
        compute_week_index(datetime.strptime("2023-12-31", "%Y-%m-%d"), min_date) == 52
    )


def test_get_date_range(sample_entries):
    """Test getting min and max dates from entries."""
    min_date, max_date = _get_date_range(sample_entries)

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

    weeks_df = generate_week_axis(min_date, max_date)

    # Should have 5 weeks (Jan 1-7, 8-14, 15-21, 22-28, 29-31)
    assert len(weeks_df) == 5
    assert weeks_df["week_index"].tolist() == [0, 1, 2, 3, 4]
    assert all(weeks_df["year"] == 2023)

    # Check first and last week
    assert weeks_df.iloc[0]["start_date"] == min_date
    assert weeks_df.iloc[-1]["end_date"] >= max_date


def test_prepare_timeline_data(sample_entries):
    """Test preparing timeline data from entries."""
    spans, min_date, max_date = prepare_timeline_data(sample_entries)

    # Check min and max dates
    assert min_date is not None
    assert max_date is not None
    assert min_date < max_date

    # Check spans
    assert len(spans) > 0
    assert "entry_idx" in spans[0]


def test_prepare_timeline_data_empty():
    """Test preparing timeline data with empty entries."""
    spans, min_date, max_date = prepare_timeline_data([])

    # Check min and max dates
    assert min_date is None
    assert max_date is None
    assert len(spans) == 0


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

    spans, min_date, max_date = prepare_timeline_data(entries)

    # Should have weeks but no spans
    assert min_date is None
    assert max_date is None
    assert len(spans) == 0

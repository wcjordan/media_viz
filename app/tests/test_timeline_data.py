"""
Unit tests for timeline data preparation functions.
"""

from datetime import datetime

import pytest

from app.timeline_data import (
    _generate_week_axis,
    _generate_bars,
    _fade_in_span,
    _fade_out_span,
    SLICES_PER_WEEK,
    FADE_WEEKS_IN_PROGRESS,
    FADE_WEEKS_FINISH_ONLY,
    LONG_DURATION_WEEKS,
    MAX_OPACITY,
    MIN_OPACITY,
    MEDIA_TYPE_COLORS,
)


def test_generate_week_axis():
    """Test generating week axis DataFrame."""
    min_date = datetime(2023, 1, 1)
    max_date = datetime(2023, 1, 31)

    weeks_df = _generate_week_axis(min_date, max_date)

    # Should have 5 weeks (Jan 1-7, 8-14, 15-21, 22-28, 29-31)
    assert len(weeks_df) == 5 * SLICES_PER_WEEK
    assert weeks_df["week_index"].tolist() == list(range(5 * SLICES_PER_WEEK))
    assert all(weeks_df["year"] == 2023)

    # Check first and last week
    assert weeks_df.iloc[0]["week_label"] == datetime.strftime(min_date, "%b")
    assert weeks_df.iloc[-1]["week_label"] == datetime.strftime(max_date, "%b")


def test_fade_out_span():
    """Test fade-out span generation."""
    span_bars = []
    span_bar_template = {
        "entry_id": 1,
        "title": "Test Entry",
        "type": "Movie",
        "color": "#33FF57",
    }
    start_week = 5

    _fade_out_span(span_bars, span_bar_template, start_week)

    # Should create FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK bars
    expected_bars = FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK
    assert len(span_bars) == expected_bars

    # Check first bar (highest opacity)
    first_bar = span_bars[0]
    assert first_bar["bar_base"] == start_week * SLICES_PER_WEEK
    assert first_bar["bar_y"] == 1
    assert first_bar["opacity"] == MAX_OPACITY

    # Check last bar (lowest opacity)
    last_bar = span_bars[-1]
    assert last_bar["bar_base"] == start_week * SLICES_PER_WEEK + expected_bars - 1
    assert last_bar["bar_y"] == 1
    assert last_bar["opacity"] == MIN_OPACITY

    # Check opacity decreases monotonically
    opacities = [bar["opacity"] for bar in span_bars]
    assert all(opacities[i] >= opacities[i + 1] for i in range(len(opacities) - 1))

    # Check template fields are copied
    for bar in span_bars:
        assert bar["entry_id"] == 1
        assert bar["title"] == "Test Entry"
        assert bar["type"] == "Movie"
        assert bar["color"] == "#33FF57"


def test_fade_in_span():
    """Test fade-in span generation."""
    span_bars = []
    span_bar_template = {
        "entry_id": 2,
        "title": "Test Book",
        "type": "Book",
        "color": "#B478B4",
    }
    end_week = 10

    _fade_in_span(span_bars, span_bar_template, end_week)

    # Should create FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK bars
    expected_bars = FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK
    assert len(span_bars) == expected_bars

    # Check first bar (lowest opacity)
    first_bar = span_bars[0]
    expected_start = (end_week + 1 - FADE_WEEKS_FINISH_ONLY) * SLICES_PER_WEEK
    assert first_bar["bar_base"] == expected_start
    assert first_bar["bar_y"] == 1
    assert first_bar["opacity"] == MIN_OPACITY

    # Check last bar (highest opacity)
    last_bar = span_bars[-1]
    assert last_bar["bar_base"] == expected_start + expected_bars - 1
    assert last_bar["bar_y"] == 1
    assert last_bar["opacity"] == MAX_OPACITY

    # Check opacity increases monotonically
    opacities = [bar["opacity"] for bar in span_bars]
    assert all(opacities[i] <= opacities[i + 1] for i in range(len(opacities) - 1))

    # Check template fields are copied
    for bar in span_bars:
        assert bar["entry_id"] == 2
        assert bar["title"] == "Test Book"
        assert bar["type"] == "Book"
        assert bar["color"] == "#B478B4"


def test_generate_bars_short_duration_span():
    """Test generating bars for short duration spans (no fading needed)."""
    spans = [
        {
            "entry_idx": 1,
            "title": "Short Movie",
            "type": "Movie",
            "start_date": datetime(2021, 1, 1),
            "end_date": datetime(2021, 1, 8),
            "start_week": 0,
            "end_week": 1,  # 2 weeks duration (≤ LONG_DURATION_WEEKS)
            "tags": {"genre": ["Action"]},
        }
    ]

    bars_df = _generate_bars(spans)

    # Should have exactly one bar (no fading)
    assert len(bars_df) == 1

    bar = bars_df.iloc[0]
    assert bar["entry_id"] == 1
    assert bar["title"] == "Short Movie"
    assert bar["type"] == "Movie"
    assert bar["color"] == MEDIA_TYPE_COLORS["Movie"]
    assert bar["start_week"] == 0
    assert bar["end_week"] == 1
    assert bar["duration_weeks"] == 2
    assert bar["bar_base"] == 0  # start_week * SLICES_PER_WEEK
    assert bar["bar_y"] == 2 * SLICES_PER_WEEK  # duration_weeks * SLICES_PER_WEEK
    assert bar["opacity"] == MAX_OPACITY
    assert bar["tags"] == {"genre": ["Action"]}


def test_generate_bars_long_duration_span():
    """Test generating bars for long duration spans (fading needed)."""
    spans = [
        {
            "entry_idx": 2,
            "title": "Long TV Show",
            "type": "TV Show",
            "start_date": datetime(2021, 1, 1),
            "end_date": datetime(2021, 3, 1),
            "start_week": 0,
            "end_week": 10,  # 11 weeks duration (> LONG_DURATION_WEEKS)
            "tags": {"genre": ["Drama"]},
        }
    ]

    bars_df = _generate_bars(spans)

    # Should have fade-out + fade-in bars
    expected_bars = (FADE_WEEKS_IN_PROGRESS + FADE_WEEKS_FINISH_ONLY) * SLICES_PER_WEEK
    assert len(bars_df) == expected_bars

    # Check that we have both fade-out and fade-in bars
    fade_out_bars = bars_df[bars_df["bar_base"] < 5 * SLICES_PER_WEEK]  # First few weeks
    fade_in_bars = bars_df[bars_df["bar_base"] >= 5 * SLICES_PER_WEEK]  # Last few weeks

    assert len(fade_out_bars) == FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK
    assert len(fade_in_bars) == FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK

    # Check fade-out starts at max opacity
    assert fade_out_bars.iloc[0]["opacity"] == MAX_OPACITY
    # Check fade-in ends at max opacity
    assert fade_in_bars.iloc[-1]["opacity"] == MAX_OPACITY


def test_generate_bars_in_progress_span():
    """Test generating bars for in-progress spans (start_week only)."""
    spans = [
        {
            "entry_idx": 3,
            "title": "In Progress Game",
            "type": "Game",
            "start_date": datetime(2021, 1, 1),
            "end_date": None,
            "start_week": 5,
            "end_week": None,
            "tags": {"platform": ["PC"]},
        }
    ]

    bars_df = _generate_bars(spans)

    # Should have fade-out bars only
    expected_bars = FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK
    assert len(bars_df) == expected_bars

    # All bars should be fade-out pattern
    assert bars_df.iloc[0]["opacity"] == MAX_OPACITY
    assert bars_df.iloc[-1]["opacity"] == MIN_OPACITY

    # Check common fields
    for _, bar in bars_df.iterrows():
        assert bar["entry_id"] == 3
        assert bar["title"] == "In Progress Game"
        assert bar["type"] == "Game"
        assert bar["color"] == MEDIA_TYPE_COLORS["Game"]
        assert bar["start_week"] == 5
        assert bar["end_week"] is None


def test_generate_bars_finish_only_span():
    """Test generating bars for finish-only spans (end_week only)."""
    spans = [
        {
            "entry_idx": 4,
            "title": "Finished Book",
            "type": "Book",
            "start_date": None,
            "end_date": datetime(2021, 1, 15),
            "start_week": None,
            "end_week": 8,
            "tags": {"genre": ["Fiction"]},
        }
    ]

    bars_df = _generate_bars(spans)

    # Should have fade-in bars only
    expected_bars = FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK
    assert len(bars_df) == expected_bars

    # All bars should be fade-in pattern
    assert bars_df.iloc[0]["opacity"] == MIN_OPACITY
    assert bars_df.iloc[-1]["opacity"] == MAX_OPACITY

    # Check common fields
    for _, bar in bars_df.iterrows():
        assert bar["entry_id"] == 4
        assert bar["title"] == "Finished Book"
        assert bar["type"] == "Book"
        assert bar["color"] == MEDIA_TYPE_COLORS["Book"]
        assert bar["start_week"] is None
        assert bar["end_week"] == 8


def test_generate_bars_no_dates():
    """Test generating bars for spans with no dates (should be skipped)."""
    spans = [
        {
            "entry_idx": 5,
            "title": "No Dates Entry",
            "type": "Movie",
            "start_date": None,
            "end_date": None,
            "start_week": None,
            "end_week": None,
            "tags": {},
        }
    ]

    bars_df = _generate_bars(spans)

    # Should have no bars
    assert len(bars_df) == 0


def test_generate_bars_unknown_media_type():
    """Test generating bars for unknown media type."""
    spans = [
        {
            "entry_idx": 6,
            "title": "Unknown Media",
            "type": "Podcast",  # Not in MEDIA_TYPE_COLORS
            "start_date": datetime(2021, 1, 1),
            "end_date": datetime(2021, 1, 8),
            "start_week": 0,
            "end_week": 1,
            "tags": {},
        }
    ]

    bars_df = _generate_bars(spans)

    assert len(bars_df) == 1
    bar = bars_df.iloc[0]
    assert bar["color"] == MEDIA_TYPE_COLORS["Unknown"]
    assert bar["type"] == "Podcast"


def test_generate_bars_mixed_spans(sample_entries):
    """Test generating bars for mixed span types using sample_entries fixture."""
    # Create spans with different scenarios
    spans = [
        {
            "entry_idx": 0,
            "title": "Short Movie",
            "type": "Movie",
            "start_date": datetime(2021, 1, 1),
            "end_date": datetime(2021, 1, 8),
            "start_week": 0,
            "end_week": 1,  # Short duration
            "tags": {"genre": ["Action"]},
        },
        {
            "entry_idx": 1,
            "title": "In Progress Game",
            "type": "Game",
            "start_date": datetime(2021, 2, 1),
            "end_date": None,
            "start_week": 5,
            "end_week": None,  # In progress
            "tags": {"platform": ["PC"]},
        },
        {
            "entry_idx": 2,
            "title": "Finished Book",
            "type": "Book",
            "start_date": None,
            "end_date": datetime(2021, 3, 1),
            "start_week": None,
            "end_week": 10,  # Finish only
            "tags": {"genre": ["Fiction"]},
        },
    ]

    bars_df = _generate_bars(spans)

    # Should have bars for all three types
    expected_bars = (
        1  # Short movie (1 bar)
        + FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK  # In progress game
        + FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK  # Finished book
    )
    assert len(bars_df) == expected_bars

    # Check we have bars for each entry
    entry_ids = bars_df["entry_id"].unique()
    assert set(entry_ids) == {0, 1, 2}

    # Check media type colors are correct
    movie_bars = bars_df[bars_df["entry_id"] == 0]
    assert all(movie_bars["color"] == MEDIA_TYPE_COLORS["Movie"])

    game_bars = bars_df[bars_df["entry_id"] == 1]
    assert all(game_bars["color"] == MEDIA_TYPE_COLORS["Game"])

    book_bars = bars_df[bars_df["entry_id"] == 2]
    assert all(book_bars["color"] == MEDIA_TYPE_COLORS["Book"])


def test_generate_bars_edge_case_long_duration_boundary():
    """Test the boundary case for long duration detection."""
    # Test exactly at LONG_DURATION_WEEKS threshold
    spans = [
        {
            "entry_idx": 1,
            "title": "Boundary Case",
            "type": "TV Show",
            "start_date": datetime(2021, 1, 1),
            "end_date": datetime(2021, 1, 8),
            "start_week": 0,
            "end_week": LONG_DURATION_WEEKS,  # Exactly at threshold
            "tags": {},
        }
    ]

    bars_df = _generate_bars(spans)

    # Should be treated as short duration (no fading)
    assert len(bars_df) == 1
    assert bars_df.iloc[0]["opacity"] == MAX_OPACITY

    # Test just over the threshold
    spans[0]["end_week"] = LONG_DURATION_WEEKS + 1
    bars_df = _generate_bars(spans)

    # Should be treated as long duration (with fading)
    expected_bars = (FADE_WEEKS_IN_PROGRESS + FADE_WEEKS_FINISH_ONLY) * SLICES_PER_WEEK
    assert len(bars_df) == expected_bars

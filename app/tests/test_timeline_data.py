"""
Unit tests for timeline data preparation functions.
"""

from datetime import datetime

from app.timeline_data import (
    _generate_week_axis,
    _generate_bars,
    _fade_in_span,
    _fade_out_span,
    SLICES_PER_WEEK,
    FADE_WEEKS_IN_PROGRESS,
    FADE_WEEKS_FINISH_ONLY,
    MAX_SHORT_DURATION_WEEKS,
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
        "title": "Test Entry",
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
    opacities = [next_bar["opacity"] for next_bar in span_bars]
    assert all(opacities[i] >= opacities[i + 1] for i in range(len(opacities) - 1))

    # Check template fields are copied
    for next_bar in span_bars:
        assert next_bar["title"] == "Test Entry"


def test_fade_in_span():
    """Test fade-in span generation."""
    span_bars = []
    span_bar_template = {
        "title": "Test Book",
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
    opacities = [next_bar["opacity"] for next_bar in span_bars]
    assert all(opacities[i] <= opacities[i + 1] for i in range(len(opacities) - 1))

    # Check template fields are copied
    for next_bar in span_bars:
        assert next_bar["title"] == "Test Book"


def test_generate_bars_short_duration_span():
    """Test generating bars for short duration spans (no fading needed)."""
    spans = [
        {
            "title": "Short Movie",
            "start_week": 0,
            "end_week": 1,  # ≤ MAX_SHORT_DURATION_WEEKS
        }
    ]

    bars_df = _generate_bars(spans)

    # Should have exactly one bar (no fading)
    assert len(bars_df) == 1

    first_bar = bars_df.iloc[0]
    assert first_bar["title"] == "Short Movie"
    assert first_bar["start_week"] == 0
    assert first_bar["end_week"] == 1
    assert first_bar["duration_weeks"] == 2
    assert first_bar["bar_base"] == 0  # start_week * SLICES_PER_WEEK
    assert first_bar["bar_y"] == 2 * SLICES_PER_WEEK  # duration_weeks * SLICES_PER_WEEK
    assert first_bar["opacity"] == MAX_OPACITY


def test_generate_bars_long_duration_span():
    """Test generating bars for long duration spans (fading needed)."""
    spans = [
        {
            "title": "Long TV Show",
            "start_week": 1,
            "end_week": MAX_SHORT_DURATION_WEEKS + 1,
        }
    ]

    bars_df = _generate_bars(spans)

    # Should have fade-out + fade-in bars
    expected_bars = (FADE_WEEKS_IN_PROGRESS + FADE_WEEKS_FINISH_ONLY) * SLICES_PER_WEEK
    assert len(bars_df) == expected_bars

    # Check that we have both fade-out and fade-in bars
    fade_out_bars = bars_df[
        bars_df["bar_base"] < 5 * SLICES_PER_WEEK
    ]  # First few weeks
    fade_in_bars = bars_df[bars_df["bar_base"] >= 5 * SLICES_PER_WEEK]  # Last few weeks

    # Check fade-out starts at max opacity
    assert fade_out_bars.iloc[0]["opacity"] == MAX_OPACITY
    # Check fade-in ends at max opacity
    assert fade_in_bars.iloc[-1]["opacity"] == MAX_OPACITY


def test_generate_bars_in_progress_span():
    """Test generating bars for in-progress spans (start_week only)."""
    spans = [
        {
            "title": "In Progress Game",
            "start_week": 5,
            "end_week": None,
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
    for _, next_bar in bars_df.iterrows():
        assert next_bar["title"] == "In Progress Game"
        assert next_bar["start_week"] == 5
        assert next_bar["end_week"] is None


def test_generate_bars_finish_only_span():
    """Test generating bars for finish-only spans (end_week only)."""
    spans = [
        {
            "title": "Finished Book",
            "start_week": None,
            "end_week": 8,
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
    for _, next_bar in bars_df.iterrows():
        assert next_bar["title"] == "Finished Book"
        assert next_bar["start_week"] is None
        assert next_bar["end_week"] == 8


def test_generate_bars_no_dates():
    """Test generating bars for spans with no dates (should be skipped)."""
    spans = [
        {
            "title": "No Dates Entry",
            "start_week": None,
            "end_week": None,
        }
    ]

    bars_df = _generate_bars(spans)

    # Should have no bars
    assert len(bars_df) == 0


def test_generate_bars_unknown_media_type():
    """Test generating bars for unknown media type."""
    spans = [
        {
            "title": "Unknown Media",
            "type": "Podcast",  # Unknown type not in MEDIA_TYPE_COLORS
            "start_week": 0,
            "end_week": 1,
        }
    ]

    bars_df = _generate_bars(spans)

    assert len(bars_df) == 1
    first_bar = bars_df.iloc[0]
    assert first_bar["color"] == MEDIA_TYPE_COLORS["Unknown"]
    assert first_bar["type"] == "Podcast"


def test_generate_bars_mixed_spans():
    """Test generating bars for mixed span types using sample_entries fixture."""
    # Create spans with different scenarios
    spans = [
        {
            "entry_idx": 0,
            "title": "Short Movie",
            "type": "Movie",
            "start_week": 0,
            "end_week": 1,  # Short duration
        },
        {
            "entry_idx": 1,
            "title": "In Progress Game",
            "type": "Game",
            "start_week": 5,
            "end_week": None,  # In progress
        },
        {
            "entry_idx": 2,
            "title": "Finished Book",
            "type": "Book",
            "start_week": None,
            "end_week": 10,  # Finish only
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
    assert len(movie_bars) == 1

    game_bars = bars_df[bars_df["entry_id"] == 1]
    assert all(game_bars["color"] == MEDIA_TYPE_COLORS["Game"])
    assert len(game_bars) == FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK

    book_bars = bars_df[bars_df["entry_id"] == 2]
    assert all(book_bars["color"] == MEDIA_TYPE_COLORS["Book"])
    assert len(book_bars) == FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK


def test_generate_bars_edge_case_long_duration_boundary():
    """Test the boundary case for long duration detection."""
    # Test exactly at MAX_SHORT_DURATION_WEEKS threshold
    spans = [
        {
            "start_week": 1,  # Start at 1 week since the duration count is inclusive on both start & end sides
            "end_week": MAX_SHORT_DURATION_WEEKS,
        }
    ]

    bars_df = _generate_bars(spans)

    # Should be treated as short duration (no fading)
    assert len(bars_df) == 1
    assert bars_df.iloc[0]["opacity"] == MAX_OPACITY

    # Test just over the threshold
    spans[0]["end_week"] = MAX_SHORT_DURATION_WEEKS + 1
    bars_df = _generate_bars(spans)

    # Should be treated as long duration (with fading)
    expected_bars = (FADE_WEEKS_IN_PROGRESS + FADE_WEEKS_FINISH_ONLY) * SLICES_PER_WEEK
    assert len(bars_df) == expected_bars

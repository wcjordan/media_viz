"""
Unit tests for timeline data preparation functions.
"""

from datetime import datetime

from app.timeline_data import (
    _generate_week_axis,
    _generate_bars,
    _fade_in_span,
    _fade_out_span,
    _allocate_slots,
    SLICES_PER_WEEK,
    FADE_WEEKS_IN_PROGRESS,
    FADE_WEEKS_FINISH_ONLY,
    MAX_OPACITY,
    MIN_OPACITY,
    MEDIA_TYPE_COLORS,
    MAX_SLOTS,
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
    """Test generating bars for short duration spans so that the fade out and in are contiguous."""
    start_week = 1
    total_weeks = 4
    spans = [
        {
            "entry_idx": 0,
            "title": "Short Movie",
            "start_week": start_week,
            "end_week": total_weeks,  # Use an odd number to ensure the fade out and in match mid week
        }
    ]

    bars_df = _generate_bars(spans)

    # Should have exactly one bar (no fading)
    assert len(bars_df) == total_weeks * SLICES_PER_WEEK

    first_bar = bars_df.iloc[0]
    assert first_bar["title"] == "Short Movie"
    assert first_bar["start_week"] == start_week
    assert first_bar["end_week"] == total_weeks
    assert first_bar["duration_weeks"] == total_weeks
    assert first_bar["bar_base"] == start_week * SLICES_PER_WEEK
    assert first_bar["bar_y"] == 1
    assert first_bar["opacity"] == MAX_OPACITY
    assert first_bar["slot"] == 0  # Should be assigned to first slot

    assert bars_df.iloc[-1]["opacity"] == MAX_OPACITY
    midpoint = len(bars_df) // 2
    assert bars_df.iloc[midpoint - 1]["opacity"] == bars_df.iloc[midpoint]["opacity"]

    opacity_group_sizes = bars_df.groupby("opacity").size()
    for size in opacity_group_sizes:
        assert size == 2


def test_generate_bars_long_duration_span():
    """Test generating bars for long duration spans so that the fade out and in have a gap."""
    start_week = 1
    total_weeks = FADE_WEEKS_IN_PROGRESS + FADE_WEEKS_FINISH_ONLY + 1

    spans = [
        {
            "entry_idx": 0,
            "title": "Long TV Show",
            "start_week": start_week,
            "end_week": total_weeks,
        }
    ]

    bars_df = _generate_bars(spans)

    # Should have a less than the full duration due to the gap between fade-out & fade-in segments
    assert len(bars_df) < total_weeks * SLICES_PER_WEEK

    assert bars_df.iloc[0]["opacity"] == MAX_OPACITY
    assert bars_df.iloc[-1]["opacity"] == MAX_OPACITY

    midpoint = len(bars_df) // 2
    before_mid_bar = bars_df.iloc[midpoint - 1]
    after_mid_bar = bars_df.iloc[midpoint]
    assert before_mid_bar["opacity"] == MIN_OPACITY
    assert after_mid_bar["opacity"] == MIN_OPACITY
    assert before_mid_bar["bar_base"] + 1 < after_mid_bar["bar_base"]

    # Check that slots are assigned (could be same or different for fade-out/fade-in)
    assert "slot" in bars_df.columns
    assert all(bars_df["slot"] >= 0)
    assert all(bars_df["slot"] < MAX_SLOTS)


def test_generate_bars_in_progress_span():
    """Test generating bars for in-progress spans (start_week only)."""
    spans = [
        {
            "entry_idx": 0,
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
        assert next_bar["slot"] == 0  # Should be assigned to first slot


def test_generate_bars_finish_only_span():
    """Test generating bars for finish-only spans (end_week only)."""
    spans = [
        {
            "entry_idx": 0,
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
        assert next_bar["slot"] == 0  # Should be assigned to first slot


def test_generate_bars_no_dates():
    """Test generating bars for spans with no dates (should be skipped)."""
    spans = [
        {
            "entry_idx": 0,
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
            "entry_idx": 0,
            "title": "Unknown Media",
            "type": "Podcast",  # Unknown type not in MEDIA_TYPE_COLORS
            "start_week": 0,
            "end_week": 1,
        }
    ]

    bars_df = _generate_bars(spans)

    first_bar = bars_df.iloc[0]
    assert first_bar["color"] == MEDIA_TYPE_COLORS["Unknown"]
    assert first_bar["type"] == "Podcast"
    assert first_bar["slot"] == 0


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
        2 * SLICES_PER_WEEK  # 2 weeks fading in and out
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
    assert len(movie_bars) == 2 * SLICES_PER_WEEK  # 2 weeks fading
    assert all(movie_bars["slot"] >= 0)
    assert all(movie_bars["slot"] < MAX_SLOTS)

    game_bars = bars_df[bars_df["entry_id"] == 1]
    assert all(game_bars["color"] == MEDIA_TYPE_COLORS["Game"])
    assert len(game_bars) == FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK
    assert all(game_bars["slot"] >= 0)
    assert all(game_bars["slot"] < MAX_SLOTS)

    book_bars = bars_df[bars_df["entry_id"] == 2]
    assert all(book_bars["color"] == MEDIA_TYPE_COLORS["Book"])
    assert len(book_bars) == FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK
    assert all(book_bars["slot"] >= 0)
    assert all(book_bars["slot"] < MAX_SLOTS)


def test_allocate_slots_basic():
    """Test basic slot allocation functionality."""
    spans = [
        {
            "entry_idx": 0,
            "title": "First Entry",
            "start_week": 0,
            "end_week": 2,
        },
        {
            "entry_idx": 1,
            "title": "Second Entry",
            "start_week": 1,
            "end_week": 3,
        },
        {
            "entry_idx": 2,
            "title": "Third Entry",
            "start_week": 4,
            "end_week": 6,
        },
    ]

    slot_allocations = _allocate_slots(spans)

    # All entries should get slots
    assert len(slot_allocations) == 3
    assert 0 in slot_allocations
    assert 1 in slot_allocations
    assert 2 in slot_allocations

    # First entry should get slot 0
    assert slot_allocations[0] == 0
    # Second entry overlaps with first, should get slot 1
    assert slot_allocations[1] == 1
    # Third entry doesn't overlap, can reuse slot 0
    assert slot_allocations[2] == 0


def test_allocate_slots_overflow():
    """Test slot allocation when there are more overlapping spans than slots."""
    # Create more overlapping spans than we have slots
    spans = []
    for i in range(MAX_SLOTS + 2):
        spans.append(
            {
                "entry_idx": i,
                "title": f"Entry {i}",
                "start_week": 0,
                "end_week": 2,
            }
        )

    slot_allocations = _allocate_slots(spans)

    # Only MAX_SLOTS entries should get allocated
    assert len(slot_allocations) == MAX_SLOTS

    # Check that allocated slots are valid
    for slot in slot_allocations.values():
        assert 0 <= slot < MAX_SLOTS


def test_allocate_slots_long_span_reuse():
    """Test that long spans can reuse slots for fade-in after fade-out."""
    long_duration = FADE_WEEKS_IN_PROGRESS + FADE_WEEKS_FINISH_ONLY + 2
    spans = [
        {
            "entry_idx": 0,
            "title": "Long Span",
            "start_week": 0,
            "end_week": long_duration,
        },
        {
            "entry_idx": 1,
            "title": "Middle Span",
            "start_week": FADE_WEEKS_IN_PROGRESS + 1,
            "end_week": FADE_WEEKS_IN_PROGRESS + 2,
        },
    ]

    slot_allocations = _allocate_slots(spans)

    # Both should get allocated
    assert len(slot_allocations) == 2

    # Long span should have separate slots for fade-out and fade-in
    long_span_slots = slot_allocations[0]
    assert isinstance(long_span_slots, dict)
    assert "fade_out_slot" in long_span_slots
    assert "fade_in_slot" in long_span_slots

    # Middle span should get a regular slot
    assert isinstance(slot_allocations[1], int)

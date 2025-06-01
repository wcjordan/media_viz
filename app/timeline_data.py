"""
This module prepares media entries into spans for the timeline visualization
"""

import logging
from datetime import datetime, timedelta
import random
from typing import Dict, List

import numpy as np
import pandas as pd

from app.utils import MAX_SLOTS, is_debug_mode

logger = logging.getLogger(__name__)

# Constants for visualization
# Number of weeks for fade-out gradient for in-progress entries
FADE_WEEKS_IN_PROGRESS = 4
# Number of weeks for fade-in gradient for finish-only entries
FADE_WEEKS_FINISH_ONLY = 4
MAX_OPACITY = 0.9  # Maximum opacity for bars
MIN_OPACITY = 0.0  # Minimum opacity for faded bars
# Number of subslices per week for finer granularity of the opacity gradient
SLICES_PER_WEEK = 7
# Number of weeks to skip before freeing a slot for a new entry
VERTICAL_SPACING_WEEKS = 1

# Color mapping for media types
MEDIA_TYPE_COLORS = {
    "Book": "#B478B4",  # Purple
    "Game": "#D1805F",  # Orange
    "Movie": "#33FF57",  # Green
    "TV Show": "#75E4EC",  # Teal
    "Unknown": "#AAAAAA",  # Gray
}


def _generate_week_axis(min_date: datetime, max_date: datetime) -> pd.DataFrame:
    """
    Generate a DataFrame with all weeks between min_date and max_date.

    Args:
        min_date: Minimum date as a datetime object
        max_date: Maximum date as a datetime object

    Returns:
        DataFrame with columns: week_index, start_date, end_date, year
    """
    weeks = []
    current_date = min_date
    week_index = 0

    while current_date <= max_date:
        for _ in range(SLICES_PER_WEEK):
            weeks.append(
                {
                    "week_index": week_index,
                    "year": current_date.year,
                    "week_label": current_date.strftime(
                        "%b %d" if is_debug_mode() else "%b"
                    ),
                }
            )
            week_index += 1
        current_date = current_date + timedelta(days=7)
    return pd.DataFrame(weeks)


def _add_span_bar(
    span_bars: List[Dict],
    span_bar_template: Dict,
    bar_base: int,
    bar_y: int,
    opacity: float,
):
    """
    Add a span bar dict to the list of span_bars by adding values to a copy of the template.
    Args:
        span_bars: List to append the created span bar dict
        span_bar_template: Template dict for the span bar
        bar_base: The week index to use as the base for the bar
        bar_y: The duration to use as the height of the bar
        opacity: The opacity value for the bar
    """
    span_bar = span_bar_template.copy()
    span_bar["bar_base"] = bar_base
    span_bar["bar_y"] = bar_y
    span_bar["opacity"] = opacity
    span_bars.append(span_bar)


def _fade_out_span(
    span_bars: List[Dict],
    span_bar_template: Dict,
    start_week: int,
    duration_slices: int = FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK,
):
    """
    Create a fade-out span for a long duration entry starting from the start week.
    Args:
        span_bars: List to append the created span bar dict
        span_bar_template: Template dict for the span bar
        start_week: The week index to start fading out from
        duration_slices: Optional; the duration for the fade-out effect specified in slices
    """
    bar_start = start_week * SLICES_PER_WEEK
    opacities = np.linspace(
        MAX_OPACITY, MIN_OPACITY, FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK
    )
    opacities = opacities[:duration_slices]
    for i, opacity in enumerate(opacities):
        _add_span_bar(
            span_bars,
            span_bar_template,
            bar_start + i,
            1,
            round(opacity, 2),
        )


def _fade_in_span(
    span_bars: List[Dict],
    span_bar_template: Dict,
    end_week: int,
    duration_slices: int = FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK,
):
    """
    Create a fade-in span for a long duration entry ending at the end week.
    Args:
        span_bars: List to append the created span bar dict
        span_bar_template: Template dict for the span bar
        end_week: The week index to end fading in at
        duration_slices: Optional; the duration for the fade-in effect specified in slices
    """
    bar_start = (end_week + 1) * SLICES_PER_WEEK - duration_slices
    opacities = np.linspace(
        MIN_OPACITY, MAX_OPACITY, FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK
    )
    opacities = opacities[-duration_slices:]
    for i, opacity in enumerate(opacities):
        _add_span_bar(
            span_bars,
            span_bar_template,
            bar_start + i,
            1,
            round(opacity, 2),
        )


def _future_blocks_clear(
    future_blocks: List[Dict], start_slice: int, free_slice: int
) -> bool:
    """
    Check if the future blocks do not overlap with the given slice range.

    Args:
        future_blocks: List of future block dictionaries
        start_slice: Start slice index
        free_slice: Free slice index

    Returns:
        True if no overlaps, False otherwise
    """
    for block in future_blocks:
        if not (
            block["free_slice"] <= start_slice or block["start_slice"] >= free_slice
        ):
            return False
    return True


def _allocate_slot_to_span(
    slot_allocations: Dict[int, int],
    future_blocks_by_slot: List[List[Dict]],
    slot_free_at: List[int],
    span: Dict,
):
    """
    Allocate a slot to a span, ensuring no overlaps with existing spans.
    Args:
        slot_allocations: Dictionary mapping entry_idx to slot number
        future_blocks_by_slot: List of future blocks for each slot
        slot_free_at: List tracking when each slot will be free
        span: Span dictionary containing entry_idx, start_week, and end_week

    Returns:
        None; modifies slot_allocations in place
    """
    start_week = span.get("start_week")
    end_week = span.get("end_week")
    entry_idx = span.get("entry_idx")

    if start_week is None and end_week is None:
        return

    # Calculate the time range this span will occupy
    # Handles prepping a future block if this span will fade out and back in
    if end_week is None:
        end_week = start_week + FADE_WEEKS_IN_PROGRESS - 1
    elif start_week is None:
        start_week = end_week + 1 - FADE_WEEKS_FINISH_ONLY

    start_slice = start_week * SLICES_PER_WEEK
    free_week = end_week + 1 + VERTICAL_SPACING_WEEKS
    free_slice = free_week * SLICES_PER_WEEK

    next_future_block = None
    if free_week - start_week > FADE_WEEKS_IN_PROGRESS + FADE_WEEKS_FINISH_ONLY:
        next_future_block = {
            "start_slice": (
                (free_week - FADE_WEEKS_FINISH_ONLY - VERTICAL_SPACING_WEEKS)
                * SLICES_PER_WEEK
            ),
            "free_slice": free_slice,
            "entry_idx": entry_idx,
        }
        free_week = start_week + FADE_WEEKS_IN_PROGRESS + VERTICAL_SPACING_WEEKS
        free_slice = free_week * SLICES_PER_WEEK

    # Find a free slot for this span
    # Sort slots by the first slot which is free earliest
    sorted_slot_free_at = sorted(
        enumerate(slot_free_at), key=lambda x: (x[1], random.random())
    )

    slot = None
    for slot_to_check, _ in sorted_slot_free_at:
        logger.debug(
            "Checking slot %s, it will be free at %s. %s requires start_slice %s and will block til free_slice %s",
            slot_to_check,
            slot_free_at[slot_to_check],
            span.get("title"),
            start_slice,
            free_slice,
        )
        if slot_free_at[slot_to_check] <= start_slice and _future_blocks_clear(
            future_blocks_by_slot[slot_to_check], start_slice, free_slice
        ):

            slot = slot_to_check
            slot_free_at[slot] = free_slice
            break

    if slot is None:
        logger.warning(
            "No available slots for span '%s' - skipping, start_date: %s, end_date: %s",
            span.get("title"),
            span.get("start_date"),
            span.get("end_date"),
        )
        return

    slot_allocations[entry_idx] = slot
    if next_future_block:
        future_blocks_by_slot[slot].append(next_future_block)


def _allocate_slots(spans: List[Dict]) -> Dict[int, int]:
    """
    Allocate horizontal slots for spans to prevent overlapping.
    Note we also pad out spans by an extra VERTICAL_SPACING_WEEKS to allow vertical spacing

    Args:
        spans: List of span dictionaries

    Returns:
        Dictionary mapping entry_idx to slot number (0 to MAX_SLOTS-1)
    """
    slot_allocations = {}

    # Track any future fade-in blocks by slot to avoid collisions
    future_blocks_by_slot = [[] for _ in range(MAX_SLOTS)]

    # Track when each slot will be free (by slice index)
    slot_free_at = [0] * MAX_SLOTS

    # Sort spans by start time (including fade-in starts)
    # This ensures that we can schedule by packing the earliest spans first
    sorted_spans = sorted(
        spans,
        key=lambda x: (
            x.get("start_week")
            if x.get("start_week") is not None
            else x.get("end_week", 0) + 1 - FADE_WEEKS_FINISH_ONLY
        ),
    )

    for span in sorted_spans:
        _allocate_slot_to_span(
            slot_allocations, future_blocks_by_slot, slot_free_at, span
        )

    return slot_allocations


def _create_bar_template_from_span(
    slot_allocations: Dict[int, int], span: Dict
) -> Dict:
    """
    Create a template dictionary for a span bar from the given span data.
    Args:
        slot_allocations: Dictionary mapping entry_idx to slot number
        span: Dictionary containing span data
    Returns:
        Template dictionary with keys: entry_id, title, type, color, start_date,
            start_week, end_date, end_week, tags, poster_path.
    """
    entry_idx = span.get("entry_idx")
    return {
        "entry_id": entry_idx,
        "title": span.get("title"),
        "type": span.get("type"),
        "color": MEDIA_TYPE_COLORS.get(span.get("type"), MEDIA_TYPE_COLORS["Unknown"]),
        "start_date": span.get("start_date"),
        "start_week": span.get("start_week"),
        "end_date": span.get("end_date"),
        "end_week": span.get("end_week"),
        "tags": span.get("tags", {}),
        "slot": slot_allocations[entry_idx],
        "poster_path": span.get("poster_path"),
    }


def _generate_bars(spans: List[Dict]) -> pd.DataFrame:
    """
    Generate a DataFrame of bars for the timeline visualization.
    Args:
        spans: List of dictionaries containing each span of media entry data for the timeline.
    Returns:
        DataFrame with columns: entry_id, title, type, color, start_date, start_week, end_date, end_week,
            duration_weeks, tags, bar_base, bar_y, opacity, & slot.
    """
    slot_allocations = _allocate_slots(spans)

    span_bars = []
    for span in spans:
        start_week = span.get("start_week", None)
        end_week = span.get("end_week", None)
        entry_idx = span.get("entry_idx")

        if start_week is None and end_week is None:
            continue

        # Skip if no slot was allocated
        if entry_idx not in slot_allocations:
            continue

        # Create spans for each week in a range when fading is needed
        span_bar_template = _create_bar_template_from_span(slot_allocations, span)
        if start_week is not None and end_week is not None:
            duration_weeks = end_week - start_week + 1
            span_bar_template["duration_weeks"] = duration_weeks

            duration_slices = duration_weeks * SLICES_PER_WEEK
            duration_in = min(
                duration_slices // 2, FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK
            )
            duration_out = min(
                duration_slices - duration_in, FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK
            )

            if duration_out > 0:
                _fade_out_span(span_bars, span_bar_template, start_week, duration_out)
            if duration_in > 0:
                # Modify the entry_idx so we show the poster again if the duration is long enough
                span_bar_copy = span_bar_template.copy()
                if duration_weeks > FADE_WEEKS_IN_PROGRESS * 3:
                    span_bar_copy["entry_id"] = f"{entry_idx} (end)"
                _fade_in_span(span_bars, span_bar_copy, end_week, duration_in)

        elif start_week is not None:
            _fade_out_span(span_bars, span_bar_template, start_week)

        else:
            _fade_in_span(span_bars, span_bar_template, end_week)

    bars_df = pd.DataFrame(span_bars)
    return bars_df


def prepare_timeline_data(spans, min_date, max_date):
    """
    Prepare data for the timeline visualization.
    Args:
        spans: List of spans with entry indices and dates
        min_date: Minimum date for the timeline
        max_date: Maximum date for the timeline

    Returns:
        Tuple of (weeks_df, bars_df) where weeks_df contains week axis data
        and bars_df contains bar data for the timeline.
    """
    weeks_df = _generate_week_axis(min_date, max_date)
    bars_df = _generate_bars(spans)

    return weeks_df, bars_df

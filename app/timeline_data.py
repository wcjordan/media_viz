"""
This module prepares media entries into spans for the timeline visualization
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Constants for visualization
# Number of weeks for fade-out gradient for in-progress entries
FADE_WEEKS_IN_PROGRESS = 4
# Number of weeks for fade-in gradient for finish-only entries
FADE_WEEKS_FINISH_ONLY = 4
MAX_OPACITY = 0.9  # Maximum opacity for bars
MIN_OPACITY = 0.0  # Minimum opacity for faded bars
# Number of subslices per week for finer granularity of the opacity gradient
SLICES_PER_WEEK = 4
# Maximum number of horizontal slots for the timeline
MAX_SLOTS = 5

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
                    "week_label": current_date.strftime("%b"),
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


def _allocate_slots(spans: List[Dict]) -> Dict[int, int]:
    """
    Allocate horizontal slots for spans to prevent overlapping.

    Args:
        spans: List of span dictionaries sorted by start time

    Returns:
        Dictionary mapping entry_idx to slot number (0 to MAX_SLOTS-1)
    """
    slot_allocations = {}
    # Track when each slot becomes free (slice index)
    slot_free_at = [0] * MAX_SLOTS

    for span in spans:
        start_week = span.get("start_week")
        end_week = span.get("end_week")
        entry_idx = span.get("entry_idx")

        if start_week is None and end_week is None:
            continue

        # Calculate the time range this span will occupy
        if start_week is not None and end_week is not None:
            # Full span - occupies from start to end
            start_slice = start_week * SLICES_PER_WEEK
            duration_weeks = end_week - start_week + 1
            duration_slices = duration_weeks * SLICES_PER_WEEK

            # Check if span is long enough to have a gap between fade-out and fade-in
            duration_in = min(
                duration_slices // 2, FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK
            )
            duration_out = min(
                duration_slices - duration_in, FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK
            )

            if duration_out + duration_in < duration_slices:
                # Long span with gap - can reuse slot for fade-in
                fade_out_end = start_slice + duration_out
                fade_in_start = (end_week + 1) * SLICES_PER_WEEK - duration_in

                # Find slot for fade-out
                fade_out_slot = None
                for slot in range(MAX_SLOTS):
                    if slot_free_at[slot] <= start_slice:
                        fade_out_slot = slot
                        slot_free_at[slot] = fade_out_end
                        break

                # Find slot for fade-in (can be different)
                fade_in_slot = None
                for slot in range(MAX_SLOTS):
                    if slot_free_at[slot] <= fade_in_start:
                        fade_in_slot = slot
                        slot_free_at[slot] = fade_in_start + duration_in
                        break

                if fade_out_slot is not None and fade_in_slot is not None:
                    # Store both slots for this entry
                    slot_allocations[entry_idx] = {
                        "fade_out_slot": fade_out_slot,
                        "fade_in_slot": fade_in_slot,
                    }
                else:
                    logger.warning(
                        f"No available slots for span '{span.get('title')}' - skipping"
                    )
            else:
                # Short span - needs single slot for entire duration
                end_slice = start_slice + duration_slices
                slot = None
                for s in range(MAX_SLOTS):
                    if slot_free_at[s] <= start_slice:
                        slot = s
                        slot_free_at[s] = end_slice
                        break

                if slot is not None:
                    slot_allocations[entry_idx] = slot
                else:
                    logger.warning(
                        f"No available slots for span '{span.get('title')}' - skipping"
                    )

        elif start_week is not None:
            # In-progress span
            start_slice = start_week * SLICES_PER_WEEK
            end_slice = start_slice + FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK

            slot = None
            for s in range(MAX_SLOTS):
                if slot_free_at[s] <= start_slice:
                    slot = s
                    slot_free_at[s] = end_slice
                    break

            if slot is not None:
                slot_allocations[entry_idx] = slot
            else:
                logger.warning(
                    f"No available slots for in-progress span '{span.get('title')}' - skipping"
                )

        else:
            # Finish-only span
            end_slice = (end_week + 1) * SLICES_PER_WEEK
            start_slice = end_slice - FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK

            slot = None
            for s in range(MAX_SLOTS):
                if slot_free_at[s] <= start_slice:
                    slot = s
                    slot_free_at[s] = end_slice
                    break

            if slot is not None:
                slot_allocations[entry_idx] = slot
            else:
                logger.warning(
                    f"No available slots for finish-only span '{span.get('title')}' - skipping"
                )

    return slot_allocations


def _generate_bars(spans: List[Dict]) -> pd.DataFrame:
    """
    Generate a DataFrame of bars for the timeline visualization.
    Args:
        spans: List of dictionaries containing each span of media entry data for the timeline.
    Returns:
        DataFrame with columns: entry_id, title, type, color, start_date, start_week, end_date, end_week,
            duration_weeks, tags, bar_base, bar_y, opacity, slot.
    """
    # Sort spans by start time for slot allocation
    sorted_spans = sorted(
        spans,
        key=lambda x: (
            (
                x.get("start_week")
                if x.get("start_week") is not None
                else x.get("end_week", float("inf"))
            ),
            x.get("end_week") if x.get("end_week") is not None else float("inf"),
        ),
    )

    # Allocate slots
    slot_allocations = _allocate_slots(sorted_spans)

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

        media_type = span.get("type")
        color = MEDIA_TYPE_COLORS.get(media_type, MEDIA_TYPE_COLORS["Unknown"])
        span_bar_template = {
            "entry_id": entry_idx,
            "title": span.get("title"),
            "type": media_type,
            "color": color,
            "start_date": span.get("start_date"),
            "start_week": start_week,
            "end_date": span.get("end_date"),
            "end_week": end_week,
            "tags": span.get("tags", {}),
        }

        slot_info = slot_allocations[entry_idx]

        # Create spans for each week in a range when fading is needed
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

            if isinstance(slot_info, dict):
                # Long span with separate slots for fade-out and fade-in
                if duration_out > 0:
                    fade_out_template = span_bar_template.copy()
                    fade_out_template["slot"] = slot_info["fade_out_slot"]
                    _fade_out_span(
                        span_bars, fade_out_template, start_week, duration_out
                    )
                if duration_in > 0:
                    fade_in_template = span_bar_template.copy()
                    fade_in_template["slot"] = slot_info["fade_in_slot"]
                    _fade_in_span(span_bars, fade_in_template, end_week, duration_in)
            else:
                # Short span with single slot
                span_bar_template["slot"] = slot_info
                if duration_out > 0:
                    _fade_out_span(
                        span_bars, span_bar_template, start_week, duration_out
                    )
                if duration_in > 0:
                    _fade_in_span(span_bars, span_bar_template, end_week, duration_in)

        elif start_week is not None:
            span_bar_template["slot"] = slot_info
            _fade_out_span(span_bars, span_bar_template, start_week)

        else:
            span_bar_template["slot"] = slot_info
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

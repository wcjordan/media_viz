"""
This module prepares media entries into spans for the timeline visualization
"""

from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd

# Constants for visualization
FADE_WEEKS_IN_PROGRESS = (
    4  # Number of weeks for fade-out gradient for in-progress entries
)
FADE_WEEKS_FINISH_ONLY = (
    4  # Number of weeks for fade-in gradient for finish-only entries
)
LONG_DURATION_WEEKS = FADE_WEEKS_IN_PROGRESS + FADE_WEEKS_FINISH_ONLY - 2
MAX_OPACITY = 0.9  # Maximum opacity for bars
MIN_OPACITY = 0.0  # Minimum opacity for faded bars
SLICES_PER_WEEK = (
    4  # Number of subslices per week for finer granularity of the opacity gradient
)

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


def _fade_out_span(span_bars: List[Dict], span_bar_template: Dict, start_week: int):
    """
    Create a fade-out span for a long duration entry starting from the start week.
    Args:
        span_bars: List to append the created span bar dict
        span_bar_template: Template dict for the span bar
        start_week: The week index to start fading out from
    """
    bar_start = start_week * SLICES_PER_WEEK
    opacities = np.linspace(
        MAX_OPACITY, MIN_OPACITY, FADE_WEEKS_IN_PROGRESS * SLICES_PER_WEEK
    )
    for i, opacity in enumerate(opacities):
        _add_span_bar(
            span_bars,
            span_bar_template,
            bar_start + i,
            1,
            opacity,
        )


def _fade_in_span(span_bars: List[Dict], span_bar_template: Dict, end_week: int):
    """
    Create a fade-in span for a long duration entry ending at the end week.
    Args:
        span_bars: List to append the created span bar dict
        span_bar_template: Template dict for the span bar
        end_week: The week index to end fading in at
    """
    bar_start = (end_week + 1 - FADE_WEEKS_FINISH_ONLY) * SLICES_PER_WEEK
    opacities = np.linspace(
        MIN_OPACITY, MAX_OPACITY, FADE_WEEKS_FINISH_ONLY * SLICES_PER_WEEK
    )
    for i, opacity in enumerate(opacities):
        _add_span_bar(
            span_bars,
            span_bar_template,
            bar_start + i,
            1,
            opacity,
        )


def _generate_bars(spans: List[Dict]) -> pd.DataFrame:
    """
    Generate a DataFrame of bars for the timeline visualization.
    Args:
        spans: List of dictionaries containing each span of media entry data for the timeline.
    Returns:
        DataFrame with columns: entry_id, title, type, color, start_date, start_week, end_date, end_week,
            duration_weeks, tags, bar_base, bar_y, & opacity.
    """
    span_bars = []
    for span in spans:
        start_week = span.get("start_week", None)
        end_week = span.get("end_week", None)
        if start_week is None and end_week is None:
            continue

        media_type = span.get("type")
        color = MEDIA_TYPE_COLORS.get(media_type, MEDIA_TYPE_COLORS["Unknown"])
        span_bar_template = {
            "entry_id": span.get("entry_idx"),
            "title": span.get("title"),
            "type": media_type,
            "color": color,
            "start_date": span.get("start_date"),
            "start_week": start_week,
            "end_date": span.get("end_date"),
            "end_week": end_week,
            "tags": span.get("tags", {}),
        }

        # Create spans for each week in a range when fading is needed
        if start_week is not None and end_week is not None:
            duration_weeks = end_week - start_week + 1
            span_bar_template["duration_weeks"] = duration_weeks
            if duration_weeks <= LONG_DURATION_WEEKS:
                # Short duration, no fade needed
                bar_start = start_week * SLICES_PER_WEEK
                bar_duration = duration_weeks * SLICES_PER_WEEK
                _add_span_bar(
                    span_bars, span_bar_template, bar_start, bar_duration, MAX_OPACITY
                )
            else:
                # Long duration, create 2 spans one fading out from the start and one fading in to the finish
                _fade_out_span(span_bars, span_bar_template, start_week)
                _fade_in_span(span_bars, span_bar_template, end_week)

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

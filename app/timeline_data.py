"""
This module prepares media entries into spans for the timeline visualization
"""

from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd

# Constants for visualization
FADE_WEEKS_IN_PROGRESS = (
    10  # Number of weeks for fade-out gradient for in-progress entries
)
FADE_WEEKS_FINISH_ONLY = (
    12  # Number of weeks for fade-in gradient for finish-only entries
)
LONG_DURATION_MONTHS = (
    8  # Entries longer than this will be split into separate segments
)
MAX_OPACITY = 0.9  # Maximum opacity for bars
MIN_OPACITY = 0.2  # Minimum opacity for faded bars

# Color mapping for media types
MEDIA_TYPE_COLORS = {
    "Movie": "#FF5733",  # Orange-red
    "TV": "#33A8FF",  # Blue
    "Game": "#33FF57",  # Green
    "Book": "#D433FF",  # Purple
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
        week_end = current_date + timedelta(days=6)
        weeks.append(
            {
                "week_index": week_index,
                "start_date": current_date,
                "end_date": week_end,
                "year": current_date.year,
                "month": current_date.month,
                "week_label": current_date.strftime("%b"),
            }
        )
        current_date = week_end + timedelta(days=1)
        week_index += 1

    return pd.DataFrame(weeks)


def calculate_opacity(  # pylint: disable=too-many-return-statements
    start_week: int,
    end_week: int,
    current_week: int,
    long_duration: bool,
) -> float:
    """
    Calculate the opacity for a bar segment based on fade parameters.

    Args:
        start_week: Week index for the start date
        end_week: Week index for the end date
        current_week: Current week being rendered
        long_duration: Whether this is a long duration entry

    Returns:
        Opacity value between MIN_OPACITY and MAX_OPACITY
    """
    # For entries with both start and end dates
    has_start = start_week is not None
    has_end = end_week is not None
    if has_start and has_end:
        if long_duration:
            # For long entries, fade out from start and fade in to end
            if current_week - start_week < FADE_WEEKS_IN_PROGRESS:
                # Fade out from start
                progress = (current_week - start_week) / FADE_WEEKS_IN_PROGRESS
                return MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * (1 - progress)
            if end_week - current_week < FADE_WEEKS_FINISH_ONLY:
                # Fade in to end
                progress = (end_week - current_week) / FADE_WEEKS_FINISH_ONLY
                return MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * (1 - progress)
            # Middle section with minimum opacity
            return MIN_OPACITY
        # Normal entry with full opacity
        return MAX_OPACITY

    # For in-progress entries (start only)
    if has_start and not has_end:
        # Fade out over FADE_WEEKS_IN_PROGRESS weeks
        weeks_from_start = current_week - start_week
        if weeks_from_start < FADE_WEEKS_IN_PROGRESS:
            progress = weeks_from_start / FADE_WEEKS_IN_PROGRESS
            return MAX_OPACITY * (1 - progress)
        return MIN_OPACITY

    # For finish-only entries
    if not has_start and has_end:
        # Fade in over FADE_WEEKS_FINISH_ONLY weeks
        weeks_to_end = end_week - current_week
        if weeks_to_end < FADE_WEEKS_FINISH_ONLY:
            progress = weeks_to_end / FADE_WEEKS_FINISH_ONLY
            return MAX_OPACITY * (1 - progress)
        return MIN_OPACITY

    # Default case
    return MAX_OPACITY


def _generate_bars(spans: List[Dict]) -> pd.DataFrame:
    """
    Generate a DataFrame of bars for the timeline visualization.
    Args:
        spans: List of dictionaries containing each span of media entry data for the timeline.
    Returns:
        DataFrame with columns: entry_id, title, type, week_index, color, opacity,
        start_date, end_date, duration_days, tags
    """
    bars = []
    for span in spans:
        start_week = span.get("start_week", None)
        end_week = span.get("end_week", None)

        if start_week is None and end_week is None:
            continue

        # TODO handle fade logic when missing a start of finish
        duration_weeks = (
            end_week - start_week
            if start_week is not None and end_week is not None
            else 0
        )
        long_duration = duration_weeks > (
            LONG_DURATION_MONTHS * 4
        )  # Approx. 4 weeks per month

        # For finish-only entries, estimate a start date
        if start_week is None:
            start_week = max(0, end_week - FADE_WEEKS_FINISH_ONLY)

        # For start-only entries, estimate an end date
        if end_week is None:
            end_week = start_week + FADE_WEEKS_IN_PROGRESS

        media_type = span.get("type")
        color = MEDIA_TYPE_COLORS.get(media_type, MEDIA_TYPE_COLORS["Unknown"])

        # For each week in the entry's span
        for week in range(start_week, end_week + 1):
            opacity = calculate_opacity(start_week, end_week, week, long_duration)

            if opacity > 0:
                bars.append(
                    {
                        "entry_id": span.get("entry_idx"),
                        "title": span.get("title"),
                        "type": media_type,
                        "week_index": week,
                        "color": color,
                        "opacity": opacity,
                        "start_date": span.get("start_date"),
                        "end_date": span.get("end_date"),
                        "duration_days": duration_weeks * 7,
                        "tags": span.get("tags", {}),
                    }
                )

    bars_df = pd.DataFrame(bars)
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

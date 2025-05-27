"""
Streamlit application to visualize media consumption data.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

from app.timeline_chart import create_timeline_chart
from app.utils import compute_week_index, get_datetime


logger = logging.getLogger(__name__)
# Configure logging
logging.basicConfig(
    level=logging.WARN,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="app/app.log",
    filemode="w",
)


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


@st.cache_data
def load_media_entries(file_path="preprocessing/processed_data/media_entries.json"):
    """
    Load media entries from the JSON file.

    Args:
        file_path: Path to the media entries JSON file

    Returns:
        List of media entry dictionaries
    """
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            st.error(f"File not found: {file_path}")
            return []
    except json.JSONDecodeError as e:
        st.error(f"Error decoding JSON from {file_path}")
        logger.error("JSON decode error: %s", e)
        return []


def _get_date_range(entries: List[Dict]) -> Tuple[datetime, datetime]:
    """
    Get the minimum and maximum dates from all entries.

    Args:
        entries: List of media entry dictionaries

    Returns:
        Tuple of (min_date, max_date) as datetime objects
    """
    min_date = get_datetime("2021-03-01")  # Default minimum date
    max_date = get_datetime("2021-05-31")  # Default maximum date
    for entry in entries:
        for date in entry.get("started_dates", []) + entry.get("finished_dates", []):
            date_obj = get_datetime(date)
            if date_obj < min_date:
                min_date = date_obj
            if date_obj > max_date:
                max_date = date_obj

    # Ensure min_date is the start of a week (Monday)
    weekday = min_date.weekday()
    min_date = min_date - timedelta(days=weekday)

    # Ensure max_date is the end of a week (Sunday)
    weekday = max_date.weekday()
    max_date = max_date + timedelta(days=6 - weekday)

    return min_date, max_date


def generate_week_axis(min_date: datetime, max_date: datetime) -> pd.DataFrame:
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
                "week_label": f"{current_date.strftime('%b %d')} - {week_end.strftime('%b %d')}",
            }
        )
        current_date = week_end + timedelta(days=1)
        week_index += 1

    return pd.DataFrame(weeks)


def calculate_opacity(
    start_week: int,
    end_week: int,
    current_week: int,
    has_start: bool,
    has_end: bool,
    long_duration: bool,
) -> float:
    """
    Calculate the opacity for a bar segment based on fade parameters.

    Args:
        start_week: Week index for the start date
        end_week: Week index for the end date
        current_week: Current week being rendered
        has_start: Whether the entry has a start date
        has_end: Whether the entry has an end date
        long_duration: Whether this is a long duration entry

    Returns:
        Opacity value between MIN_OPACITY and MAX_OPACITY
    """
    # For entries with both start and end dates
    if has_start and has_end:
        if long_duration:
            # For long entries, fade out from start and fade in to end
            if current_week - start_week < FADE_WEEKS_IN_PROGRESS:
                # Fade out from start
                progress = (current_week - start_week) / FADE_WEEKS_IN_PROGRESS
                return MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * (1 - progress)
            elif end_week - current_week < FADE_WEEKS_FINISH_ONLY:
                # Fade in to end
                progress = (end_week - current_week) / FADE_WEEKS_FINISH_ONLY
                return MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * (1 - progress)
            else:
                # Middle section with minimum opacity
                return MIN_OPACITY
        else:
            # Normal entry with full opacity
            return MAX_OPACITY

    # For in-progress entries (start only)
    elif has_start and not has_end:
        # Fade out over FADE_WEEKS_IN_PROGRESS weeks
        weeks_from_start = current_week - start_week
        if weeks_from_start < FADE_WEEKS_IN_PROGRESS:
            progress = weeks_from_start / FADE_WEEKS_IN_PROGRESS
            return MAX_OPACITY * (1 - progress)
        else:
            return MIN_OPACITY

    # For finish-only entries
    elif not has_start and has_end:
        # Fade in over FADE_WEEKS_FINISH_ONLY weeks
        weeks_to_end = end_week - current_week
        if weeks_to_end < FADE_WEEKS_FINISH_ONLY:
            progress = weeks_to_end / FADE_WEEKS_FINISH_ONLY
            return MAX_OPACITY * (1 - progress)
        else:
            return MIN_OPACITY

    # Default case
    return MAX_OPACITY


def prepare_timeline_data(entries: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Prepare data for the timeline visualization.

    Args:
        entries: List of media entry dictionaries

    Returns:
        Tuple of (spans, min_date, max_date)
    """
    if not entries:
        logger.warning("No media entries provided for timeline preparation.")
        return pd.DataFrame(), pd.DataFrame()

    # Get date range and generate week axis
    min_date, max_date = _get_date_range(entries)
    logger.warning(
        "Preparing timeline data from %s to %s",
        min_date.strftime("%Y-%m-%d"),
        max_date.strftime("%Y-%m-%d"),
    )

    # Collect spans data
    spans = []

    for entry_idx, entry in enumerate(entries):
        tagged_entry = entry.get("tagged", {})
        media_type = tagged_entry.get("type", "Unknown")

        has_start = "started_dates" in entry and entry["started_dates"]
        has_end = "finished_dates" in entry and entry["finished_dates"]

        # Skip entries with no dates
        if not has_start and not has_end:
            continue

        # Calculate week indices
        min_start_date = (
            min(get_datetime(date) for date in entry.get("started_dates", []))
            if has_start
            else None
        )
        min_end_date = (
            min(get_datetime(date) for date in entry.get("finished_dates", []))
            if has_end
            else None
        )
        start_week = compute_week_index(min_start_date, min_date) if has_start else None
        end_week = compute_week_index(min_end_date, min_date) if has_end else None

        # For finish-only entries, estimate a start date
        if not has_start and has_end:
            start_week = max(0, end_week - FADE_WEEKS_FINISH_ONLY)

        # For start-only entries, estimate an end date
        if has_start and not has_end:
            end_week = start_week + FADE_WEEKS_IN_PROGRESS

        spans.append(
            {
                "entry_idx": entry_idx,
                "title": tagged_entry.get("canonical_title", "Unknown"),
                "type": media_type,
                "start_week": start_week,
                "end_week": end_week,
                "tags": tagged_entry.get("tags", {}),
            }
        )

    return spans, min_date, max_date


def generate_bars(spans: List[Dict]) -> pd.DataFrame:
    bars = []
    for span in spans:
        start_week = span.get("start_week", None)
        end_week = span.get("end_week", None)

        has_start = start_week is not None
        has_end = end_week is not None
        duration_weeks = (
            end_week - start_week
            if start_week is not None and end_week is not None
            else 0
        )
        long_duration = duration_weeks > (
            LONG_DURATION_MONTHS * 4
        )  # Approx. 4 weeks per month

        media_type = span.get("type")
        color = MEDIA_TYPE_COLORS.get(media_type, MEDIA_TYPE_COLORS["Unknown"])

        # For each week in the entry's span
        for week in range(start_week, end_week + 1):
            opacity = calculate_opacity(
                start_week, end_week, week, has_start, has_end, long_duration
            )

            if opacity > 0:
                bars.append(
                    {
                        "entry_id": span.get("entry_idx"),
                        "title": span.get("title"),
                        "type": media_type,
                        "week_index": week,
                        "color": color,
                        "opacity": opacity,
                        "start_date": start_week,
                        "end_date": end_week,
                        "duration_days": duration_weeks * 7,
                        "tags": span.get("tags", {}),
                    }
                )

    bars_df = pd.DataFrame(bars)
    return bars_df


def main():
    """Main Streamlit application."""

    # Set page title and header
    st.set_page_config(page_title="Media Timeline", page_icon="📚", layout="wide")

    st.title("Media Timeline")
    st.subheader("Interactive Visualization of Media Consumption")

    # Add a reload button
    if st.button("Reload Data"):
        st.cache_data.clear()
        st.rerun()

    # Load and display the media entries
    media_entries = load_media_entries()

    if media_entries:
        st.write(f"Loaded {len(media_entries)} media entries")

        # Create tabs for different views
        tab1, tab2 = st.tabs(["Timeline Visualization", "Raw JSON Data"])

        with tab1:
            # Prepare data for timeline
            spans, min_date, max_date = prepare_timeline_data(media_entries)
            weeks_df = generate_week_axis(min_date, max_date)
            bars_df = generate_bars(spans)

            # Create and display timeline chart
            fig = create_timeline_chart(weeks_df, bars_df)
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            # Display raw JSON data
            st.json(media_entries)
    else:
        st.warning("No media entries found. Please run the preprocessing script first.")


if __name__ == "__main__":
    main()

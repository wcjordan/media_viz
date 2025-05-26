"""
Streamlit application to visualize media consumption data.
"""

from datetime import datetime
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

logger = logging.getLogger(__name__)
# Configure logging
logging.basicConfig(
    level=logging.WARN,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="app/app.log",
    filemode="w",
)


# Constants for visualization

FADE_WEEKS_IN_PROGRESS = 10 # Number of weeks for fade-out gradient for in-progress entries
FADE_WEEKS_FINISH_ONLY = 12 # Number of weeks for fade-in gradient for finish-only entries
LONG_DURATION_MONTHS = 8  # Entries longer than this will be split into separate segments
MAX_OPACITY = 0.9  # Maximum opacity for bars
MIN_OPACITY = 0.2  # Minimum opacity for faded bars
BAR_HEIGHT = 2.0  # Height of each bar
BAR_SPACING = 0.2  # Spacing between bars in the same week

# Color mapping for media types
MEDIA_TYPE_COLORS = {
    "Movie": "#FF5733",  # Orange-red
    "TV": "#33A8FF",  # Blue
    "Game": "#33FF57",  # Green
    "Book": "#D433FF",  # Purple
    "Unknown": "#AAAAAA",  # Gray
}


def _get_datetime(date_str: str) -> datetime:
    """
    Convert a %Y-%m-%d date string to a naive datetime object.

    Returns:
        Datetime object
    """
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=None)


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


def _compute_week_index(entry_date: datetime, min_date: datetime) -> int:
    """
    Compute the week index for a given date relative to the minimum date.

    Args:
        entry_date: datetime representing an entry start of finish date
        min_date: Minimum date as a datetime object

    Returns:
        Week index (integer)
    """
    delta = entry_date - min_date
    return delta.days // 7


def _get_date_range(entries: List[Dict]) -> Tuple[datetime, datetime]:
    """
    Get the minimum and maximum dates from all entries.

    Args:
        entries: List of media entry dictionaries

    Returns:
        Tuple of (min_date, max_date) as datetime objects
    """
    min_date = _get_datetime("2021-03-01")  # Default minimum date
    max_date = _get_datetime("2021-05-31")  # Default maximum date
    for entry in entries:
        for date in entry.get("started_dates", []) + entry.get("finished_dates", []):
            date_obj = _get_datetime(date)
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
        Tuple of (weeks_df, bars_df) DataFrames
    """
    if not entries:
        logger.warning("No media entries provided for timeline preparation.")
        return pd.DataFrame(), pd.DataFrame()

    # Get date range and generate week axis
    min_date, max_date = _get_date_range(entries)
    logger.warning(
        "Preparing timeline data from %s to %s", min_date.strftime("%Y-%m-%d"), max_date.strftime("%Y-%m-%d")
    )
    weeks_df = generate_week_axis(min_date, max_date)

    # Prepare bars data
    bars = []

    for entry_idx, entry in enumerate(entries):
        tagged_entry = entry.get("tagged", {})
        media_type = tagged_entry.get("type", "Unknown")
        color = MEDIA_TYPE_COLORS.get(media_type, MEDIA_TYPE_COLORS["Unknown"])

        has_start = "started_dates" in entry and entry["started_dates"]
        has_end = "finished_dates" in entry and entry["finished_dates"]

        # Skip entries with no dates
        if not has_start and not has_end:
            continue

        # Calculate week indices
        min_start_date = min(
            _get_datetime(date) for date in entry.get("started_dates", [])
        ) if has_start else None
        min_end_date = min(
            _get_datetime(date) for date in entry.get("finished_dates", [])
        ) if has_end else None
        start_week = (
            _compute_week_index(min_start_date, min_date) if has_start else None
        )
        end_week = (
            _compute_week_index(min_end_date, min_date) if has_end else None
        )

        # For finish-only entries, estimate a start date
        if not has_start and has_end:
            start_week = max(0, end_week - FADE_WEEKS_FINISH_ONLY)

        # For start-only entries, estimate an end date
        if has_start and not has_end:
            end_week = start_week + FADE_WEEKS_IN_PROGRESS

        # Check if this is a long duration entry
        duration_weeks = (
            end_week - start_week
            if start_week is not None and end_week is not None
            else 0
        )
        long_duration = duration_weeks > (
            LONG_DURATION_MONTHS * 4
        )  # Approx. 4 weeks per month

        # For each week in the entry's span
        for week in range(start_week, end_week + 1):
            opacity = calculate_opacity(
                start_week, end_week, week, has_start, has_end, long_duration
            )

            if opacity > 0:
                bars.append(
                    {
                        "entry_id": entry_idx,
                        "title": entry.get("title", "Unknown"),
                        "canonical_title": entry.get(
                            "canonical_title", entry.get("title", "Unknown")
                        ),
                        "type": media_type,
                        "week_index": week,
                        "color": color,
                        "opacity": opacity,
                        "raw_text": entry.get("raw_text", ""),
                        "start_date": entry.get("start_date", ""),
                        "finish_date": entry.get("finish_date", ""),
                        "duration_days": entry.get("duration_days", 0),
                        "status": entry.get("status", "unknown"),
                        "tags": entry.get("tags", {}),
                    }
                )

    bars_df = pd.DataFrame(bars)
    return weeks_df, bars_df


def create_timeline_chart(weeks_df: pd.DataFrame, bars_df: pd.DataFrame) -> go.Figure:
    """
    Create a Plotly figure for the timeline visualization.

    Args:
        weeks_df: DataFrame with week information
        bars_df: DataFrame with bar information

    Returns:
        Plotly Figure object
    """
    if weeks_df.empty or bars_df.empty:
        # Return empty figure if no data
        fig = go.Figure()
        fig.update_layout(title="No data available for timeline", height=600)
        return fig

    # Create figure
    fig = go.Figure()

    # Add year dividers
    years = weeks_df["year"].unique()
    for i, year in enumerate(years):
        year_weeks = weeks_df[weeks_df["year"] == year]
        min_week = year_weeks["week_index"].min()
        max_week = year_weeks["week_index"].max()
        logger.warning(
            "Adding year divider for %s: weeks %d to %d", year, min_week, max_week
        )

        # Add year label
        fig.add_annotation(
            x=-0.5,
            y=min_week - 0.5,
            text=str(year),
            showarrow=False,
            font=dict(size=16, color="white"),
            xanchor="right",
            yanchor="bottom",
        )

    # Group bars by week for horizontal stacking
    grouped_bars = bars_df.groupby("week_index")

    # Add bars for each entry
    for week_idx, group in grouped_bars:
        # Stack bars horizontally within each week
        for i, (_, bar) in enumerate(group.iterrows()):
            # Calculate horizontal position for stacking
            x_offset = i * BAR_SPACING

            # Add bar
            fig.add_trace(
                go.Scatter(
                    x=[x_offset, x_offset + BAR_HEIGHT],
                    y=[bar["week_index"], bar["week_index"]],
                    mode="lines",
                    line=dict(
                        color=f"rgba{tuple(int(bar['color'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (bar['opacity'],)}",
                        width=10,
                    ),
                    name=bar["canonical_title"],
                    text=f"{bar['canonical_title']} ({bar['type']})<br>"
                    f"Status: {bar['status']}<br>"
                    f"Start: {bar['start_date']}<br>"
                    f"Finish: {bar['finish_date']}<br>"
                    f"Duration: {bar['duration_days']} days<br>"
                    f"Raw text: {bar['raw_text']}",
                    hoverinfo="text",
                    showlegend=False,
                )
            )

    # Update layout
    fig.update_layout(
        title="Media Timeline",
        height=len(weeks_df) * 15,  # Scale height based on number of weeks
        width=800,
        plot_bgcolor="rgba(25, 25, 25, 1)",
        paper_bgcolor="rgba(25, 25, 25, 1)",
        font=dict(color="white"),
        margin=dict(l=100, r=50, t=50, b=50),
        xaxis=dict(
            title="",
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-0.5, 5],  # Adjust based on maximum number of stacked items
        ),
        yaxis=dict(
            title="",
            showgrid=True,
            gridcolor="rgba(100, 100, 100, 0.2)",
            tickvals=weeks_df["week_index"].tolist(),
            ticktext=weeks_df["week_label"].tolist(),
            autorange="reversed",  # Reverse y-axis to have most recent at top
        ),
        hoverlabel=dict(
            bgcolor="rgba(50, 50, 50, 0.9)", font_size=12, font_family="Arial"
        ),
    )

    return fig


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
            weeks_df, bars_df = prepare_timeline_data(media_entries)

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

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

from app.utils import compute_week_index, get_datetime


logger = logging.getLogger(__name__)


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


def _get_timeline_range(entries: List[Dict]) -> Tuple[datetime, datetime]:
    """
    Get the minimum and maximum dates from all entries for the timeline.

    Args:
        entries: List of media entry dictionaries

    Returns:
        Tuple of (min_date, max_date) as datetime objects
    """
    all_started_dates = [
        get_datetime(item)
        for sublist in [entry.get("started_dates", []) for entry in entries]
        for item in sublist
    ]
    all_finished_dates = [
        get_datetime(item)
        for sublist in [entry.get("finished_dates", []) for entry in entries]
        for item in sublist
    ]
    all_dates = all_started_dates + all_finished_dates

    if not all_dates:
        logger.warning("No dates provided for date range calculation.")
        return None, None

    min_date = min(all_dates)
    max_date = max(all_dates)

    # Ensure min_date is the start of a week (Monday)
    weekday = min_date.weekday()
    min_date = min_date - timedelta(days=weekday)

    # Ensure max_date is the start of a week (Monday)
    weekday = max_date.weekday()
    max_date = max_date - timedelta(days=weekday)

    return min_date, max_date


def extract_timeline_spans(entries: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extract timeline spans from media entries.

    Args:
        entries: List of media entry dictionaries

    Returns:
        Tuple of (spans, min_date, max_date)
    """
    if not entries:
        logger.warning("No media entries provided for timeline preparation.")
        return [], None, None

    # Get date range and generate week axis
    min_date, max_date = _get_timeline_range(entries)

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
        max_end_date = (
            max(get_datetime(date) for date in entry.get("finished_dates", []))
            if has_end
            else None
        )
        start_week = compute_week_index(min_start_date, min_date) if has_start else None
        end_week = compute_week_index(max_end_date, min_date) if has_end else None
        if len(entry.get("started_dates", [])) > 1:
            logger.warning(
                "Multiple start dates found for entry %s: %s",
                entry_idx,
                entry.get("started_dates", []),
            )
        if len(entry.get("finished_dates", [])) > 1:
            logger.warning(
                "Multiple end dates found for entry %s: %s",
                entry_idx,
                entry.get("finished_dates", []),
            )

        spans.append(
            {
                "entry_idx": entry_idx,
                "title": tagged_entry.get("canonical_title", "Unknown"),
                "type": media_type,
                "tags": tagged_entry.get("tags", {}),
                "poster_path": tagged_entry.get("poster_path", ""),
                "start_date": min_start_date,
                "end_date": max_end_date,
                "start_week": start_week,
                "end_week": end_week,
            }
        )

    return spans, min_date, max_date


if __name__ == "__main__":
    # TODO add example usage
    pass

"""
Tests for timeline chart generation functionality.
"""

import pandas as pd
import plotly.graph_objects as go

from app.timeline_chart import BAR_WIDTH, create_timeline_chart
from app.utils import MAX_SLOTS


def test_create_timeline_chart_happy_path():
    """Test creating a timeline chart with valid data."""
    # Create sample weeks DataFrame
    weeks_df = pd.DataFrame(
        {
            "week_index": [0, 1, 2, 3, 4, 5],
            "year": [2021, 2021, 2021, 2021, 2021, 2021],
            "week_label": ["Jan", "Jan", "Jan", "Feb", "Feb", "Feb"],
        }
    )

    # Create sample bars DataFrame
    bars_df = pd.DataFrame(
        {
            "entry_id": [1, 2, 3],
            "title": ["Test Movie", "Test Game", "Test Book"],
            "type": ["Movie", "Game", "Book"],
            "color": ["#33FF57", "#D1805F", "#B478B4"],
            "opacity": [0.9, 0.7, 0.8],
            "bar_base": [0, 2, 4],
            "bar_y": [2, 1, 3],
            "slot": [0, 1, 2],
            "start_week": [0, 2, 4],
            "end_week": [1, 2, 6],
            "start_date": ["2021-01-01", "2021-01-15", "2021-02-01"],
            "end_date": ["2021-01-08", "2021-01-15", "2021-02-22"],
            "duration_weeks": [2, 1, 3],
        }
    )

    # Create the chart
    fig = create_timeline_chart(weeks_df, bars_df)

    # Verify it's a Plotly figure
    assert isinstance(fig, go.Figure)

    # Check that we have the expected number of traces (one per bar + annotations)
    assert len(fig.data) == 3  # One trace per bar

    # Verify all traces are Bar traces
    for trace in fig.data:
        assert isinstance(trace, go.Bar)
        assert trace.orientation == "v"
        assert trace.showlegend is False

    # Check layout properties
    layout = fig.layout

    # Check axis configuration
    assert layout.xaxis.range == (0, MAX_SLOTS * BAR_WIDTH)
    assert layout.yaxis.tickvals == (0, 1, 2, 3, 4, 5)

    # Check that year annotations are present
    annotations = fig.layout.annotations
    assert len(annotations) >= 1  # Should have at least one year annotation

    # Verify first annotation is for the year
    year_annotation = annotations[0]
    assert year_annotation.text == "2021"
    assert year_annotation.font.color == "white"
    assert year_annotation.font.size == 16


def test_create_timeline_chart_empty_data():
    """Test creating a timeline chart with empty data."""
    empty_weeks_df = pd.DataFrame()
    empty_bars_df = pd.DataFrame()

    fig = create_timeline_chart(empty_weeks_df, empty_bars_df)

    # Should return a valid figure with no data message
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0  # No traces
    assert fig.layout.height == 600
    assert "No data available for timeline" in fig.layout.title.text


def test_create_timeline_chart_with_nan_values():
    """Test creating a timeline chart with NaN values in data."""
    weeks_df = pd.DataFrame(
        {
            "week_index": [0, 1],
            "year": [2021, 2021],
            "week_label": ["Jan", "Jan"],
        }
    )

    # Create bars with some NaN values (in-progress or finish-only entries)
    bars_df = pd.DataFrame(
        {
            "entry_id": [1, 2],
            "title": ["In Progress", "Finish Only"],
            "type": ["Game", "Book"],
            "color": ["#D1805F", "#B478B4"],
            "opacity": [0.9, 0.8],
            "bar_base": [0, 1],
            "bar_y": [1, 1],
            "slot": [0, 1],
            "start_week": [0, float("nan")],  # NaN for finish-only
            "end_week": [float("nan"), 1],  # NaN for in-progress
            "start_date": ["2021-01-01", None],
            "end_date": [None, "2021-01-08"],
            "duration_weeks": [float("nan"), float("nan")],
        }
    )

    # Should not raise an error
    fig = create_timeline_chart(weeks_df, bars_df)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2  # Two bars

    # Check that tooltips handle NaN values appropriately
    for trace in fig.data:
        assert trace.hovertemplate is not None
        # Should contain title and type info at minimum
        assert "Game" in trace.hovertemplate or "Book" in trace.hovertemplate


def test_create_timeline_chart_multiple_years():
    """Test creating a timeline chart spanning multiple years."""
    weeks_df = pd.DataFrame(
        {
            "week_index": [0, 1, 52, 53],
            "year": [2021, 2021, 2022, 2022],
            "week_label": ["Jan", "Jan", "Jan", "Jan"],
        }
    )

    bars_df = pd.DataFrame(
        {
            "entry_id": [1],
            "title": ["Cross-Year Entry"],
            "type": ["TV Show"],
            "color": ["#75E4EC"],
            "opacity": [0.9],
            "bar_base": [0],
            "bar_y": [53],
            "slot": [0],
            "start_week": [0],
            "end_week": [53],
            "start_date": ["2021-01-01"],
            "end_date": ["2022-01-01"],
            "duration_weeks": [53],
        }
    )

    fig = create_timeline_chart(weeks_df, bars_df)

    # Should have annotations for both years
    annotations = fig.layout.annotations
    year_texts = [ann.text for ann in annotations]
    assert "2021" in year_texts
    assert "2022" in year_texts

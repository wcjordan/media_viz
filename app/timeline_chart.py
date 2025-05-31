"""
Generate a timeline chart using Plotly for vizualizing media entries.
"""

import logging
import math

import numpy as np
import plotly.graph_objects as go
import pandas as pd

from app.utils import MAX_SLOTS, is_debug_mode

logger = logging.getLogger(__name__)

BAR_WIDTH = 1.0
BAR_SPACING = 0.05  # Spacing between bars on the x-axis


def create_timeline_chart(weeks_df: pd.DataFrame, bars_df: pd.DataFrame) -> go.Figure:
    """
    Create a Plotly figure for the timeline visualization.

    Args:
        weeks_df: DataFrame with week information
        bars_df: DataFrame with bar information

    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    if weeks_df.empty or bars_df.empty:
        # Return empty figure if no data
        fig.update_layout(title="No data available for timeline", height=600)
        return fig

    # Add year dividers
    years = weeks_df["year"].unique()
    for _, year in enumerate(years):
        year_weeks = weeks_df[weeks_df["year"] == year]
        min_week = year_weeks["week_index"].min()

        # Add year label
        fig.add_annotation(
            x=0,
            y=min_week - 0.5,
            text=str(year),
            showarrow=False,
            font={"size": 16, "color": "white"},
            xanchor="right",
            yanchor="bottom",
        )

    # Add bars for entries
    for _, next_bar in bars_df.iterrows():
        rgba_tuple = tuple(
            int(next_bar["color"].lstrip("#")[i : (i + 2)], 16) for i in (0, 2, 4)
        ) + (next_bar["opacity"],)

        tooltip_list = [f"{next_bar['title']} ({next_bar['type']})"]
        if not np.isnan(next_bar["start_week"]):
            tooltip_list.append(
                f"Start: {next_bar['start_date']} ({next_bar['start_week']:.0f})"
            )
        if not np.isnan(next_bar["end_week"]):
            tooltip_list.append(
                f"Finish: {next_bar['end_date']} ({next_bar['end_week']:.0f})"
            )
        if not np.isnan(next_bar["duration_weeks"]):
            tooltip_list.append(f"Duration: {next_bar['duration_weeks']:.0f} week(s)")
        tooltip = "<br>".join(tooltip_list)

        extra_spacing = (BAR_WIDTH - BAR_SPACING) * (
            math.pow(1 - next_bar["opacity"], 2) / 12
        )

        fig.add_trace(
            go.Bar(
                x=[next_bar["slot"] * BAR_WIDTH + BAR_SPACING + extra_spacing],
                y=[next_bar["bar_y"]],
                base=[next_bar["bar_base"]],
                orientation="v",
                marker_color=f"rgba{rgba_tuple}",
                width=BAR_WIDTH - BAR_SPACING - 2 * extra_spacing,
                hovertemplate=tooltip,
                showlegend=False,
                offsetgroup=1,
                offset=0,
            )
        )

    # Drop tick text if same as prior week
    # Since the tick text is the name of the month, this means we just show each month name once
    tick_text = weeks_df["week_label"].tolist()
    tick_text = [
        tick_text[i] if i == 0 or tick_text[i] != tick_text[i - 1] else ""
        for i in range(len(tick_text))
    ]

    # Update layout
    min_week = weeks_df["week_index"].min()
    max_week = weeks_df["week_index"].max()
    fig.update_layout(
        height=4000,
        plot_bgcolor="rgba(25, 25, 25, 1)",
        paper_bgcolor="rgba(25, 25, 25, 1)",
        font={"color": "white"},
        margin={"l": 50, "r": 5, "t": 0, "b": 0},
        xaxis={
            "range": [0, MAX_SLOTS * BAR_WIDTH],
            "showgrid": False,
            "showticklabels": False,
            "zeroline": False,
        },
        yaxis={
            "range": [max_week + 10, min_week - 10],
            "showgrid": is_debug_mode(),
            "tickvals": weeks_df["week_index"].tolist(),
            "ticktext": tick_text,
            "zeroline": False,
        },
        hoverlabel={
            "bgcolor": "rgba(50, 50, 50, 0.9)",
            "font_size": 12,
            "font_family": "Arial",
        },
    )

    return fig

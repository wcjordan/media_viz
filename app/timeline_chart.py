"""
Generate a timeline chart using Plotly for vizualizing media entries.
"""

import logging

import numpy as np
import plotly.graph_objects as go
import pandas as pd

logger = logging.getLogger(__name__)

BAR_WIDTH = 0.10
BAR_SPACING = 0.02  # Spacing between bars on the x-axis


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

    fig = go.Figure()

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
        x_offset = next_bar["entry_id"] * BAR_WIDTH

        rgba_tuple = tuple(
            int(next_bar["color"].lstrip("#")[i : (i + 2)], 16) for i in (0, 2, 4)
        ) + (next_bar['opacity'],)

        tooltip_list = [f"{next_bar['title']} ({next_bar['type']})"]
        if not np.isnan(next_bar['start_week']):
            tooltip_list.append(f"Start: {next_bar['start_date']} ({next_bar['start_week']:.0f})")
        if not np.isnan(next_bar['end_week']):
            tooltip_list.append(f"Finish: {next_bar['end_date']} ({next_bar['end_week']:.0f})")
        if not np.isnan(next_bar['duration_weeks']):
            tooltip_list.append(f"Duration: {next_bar['duration_weeks']:.0f} week(s)")
        tooltip = "<br>".join(tooltip_list)

        fig.add_trace(
            go.Bar(
                x=[x_offset],
                y=[next_bar['bar_y']],
                base=[next_bar['bar_base']],
                orientation='v',
                marker_color=f"rgba{rgba_tuple}",
                width=BAR_WIDTH - BAR_SPACING,
                hovertemplate=tooltip,
                showlegend=False,
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
    fig.update_layout(
        width=800,
        plot_bgcolor="rgba(25, 25, 25, 1)",
        paper_bgcolor="rgba(25, 25, 25, 1)",
        font={"color": "white"},
        margin={"l": 50, "r": 5, "t": 5, "b": 5},
        xaxis={
            "title": "",
            "range": [0, 5],
            "showgrid": False,
            "showticklabels": False,
            "zeroline": False,
        },
        yaxis={
            "autorange": "reversed",  # Reverse y-axis to have most recent at top
            "showgrid": False,
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

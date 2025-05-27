"""
Generate a timeline chart using Plotly for vizualizing media entries.
"""

import logging

import plotly.graph_objects as go
import pandas as pd

logger = logging.getLogger(__name__)

BAR_WIDTH = 1.0  # Width of each bar
BAR_SPACING = 0.1  # Spacing between bars in the same week


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
            font={"size": 16, "color": "white"},
            xanchor="right",
            yanchor="bottom",
        )

    # Group bars by week for horizontal stacking
    grouped_bars = bars_df.groupby("week_index")

    # Add bars for each entry
    for week_idx, group in grouped_bars:
        # Stack bars horizontally within each week
        for i, (_, next_bar) in enumerate(group.iterrows()):
            # Calculate horizontal position for stacking
            x_offset = next_bar["entry_id"] * 0.2

            # Add bar
            rgb_tuple = tuple(
                int(next_bar["color"].lstrip("#")[i : (i + 2)], 16) for i in (0, 2, 4)
            )
            fig.add_trace(
                go.Scatter(
                    x=[x_offset, x_offset + 0.1],
                    y=[week_idx, week_idx],
                    mode="lines",
                    line={
                        "color": f"rgba{rgb_tuple + (next_bar['opacity'],)}",
                        "width": 10,
                    },
                    name=next_bar["title"],
                    text=f"{next_bar['title']} ({next_bar['type']})<br>"
                    f"Start: {next_bar['start_date']}<br>"
                    f"Finish: {next_bar['end_date']}<br>"
                    f"Duration: {next_bar['duration_days']} days<br>",
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
        font={"color": "white"},
        margin={"l": 100, "r": 50, "t": 50, "b": 50},
        xaxis={
            "title": "",
            "showgrid": False,
            "zeroline": False,
            "showticklabels": False,
            "range": [-0.5, 5],
        },
        yaxis={
            "title": "",
            "showgrid": True,
            "gridcolor": "rgba(100, 100, 100, 0.2)",
            "tickvals": weeks_df["week_index"].tolist(),
            "ticktext": weeks_df["week_label"].tolist(),
            "autorange": "reversed",  # Reverse y-axis to have most recent at top
        },
        hoverlabel={
            "bgcolor": "rgba(50, 50, 50, 0.9)",
            "font_size": 12,
            "font_family": "Arial",
        },
    )

    return fig

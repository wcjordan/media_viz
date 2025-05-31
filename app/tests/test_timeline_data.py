"""
Unit tests for timeline data preparation functions.
"""

from datetime import datetime

from app.timeline_data import _generate_week_axis, SLICES_PER_WEEK


def test_generate_week_axis():
    """Test generating week axis DataFrame."""
    min_date = datetime(2023, 1, 1)
    max_date = datetime(2023, 1, 31)

    weeks_df = _generate_week_axis(min_date, max_date)

    # Should have 5 weeks (Jan 1-7, 8-14, 15-21, 22-28, 29-31)
    assert len(weeks_df) == 5 * SLICES_PER_WEEK
    assert weeks_df["week_index"].tolist() == list(range(5 * SLICES_PER_WEEK))
    assert all(weeks_df["year"] == 2023)

    # Check first and last week
    assert weeks_df.iloc[0]["week_label"] == datetime.strftime(min_date, "%b")
    assert weeks_df.iloc[-1]["week_label"] == datetime.strftime(max_date, "%b")

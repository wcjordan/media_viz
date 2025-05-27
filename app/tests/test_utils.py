"""
Tests for the timeline layout functionality.
"""

from datetime import datetime

from app.utils import compute_week_index


def test_compute_week_index():
    """Test computing week index from date."""
    min_date = datetime(2023, 1, 1)

    # Same week
    assert (
        compute_week_index(datetime.strptime("2023-01-01", "%Y-%m-%d"), min_date) == 0
    )
    assert (
        compute_week_index(datetime.strptime("2023-01-07", "%Y-%m-%d"), min_date) == 0
    )

    # Next week
    assert (
        compute_week_index(datetime.strptime("2023-01-08", "%Y-%m-%d"), min_date) == 1
    )

    # Several weeks later
    assert (
        compute_week_index(datetime.strptime("2023-02-01", "%Y-%m-%d"), min_date) == 4
    )
    assert (
        compute_week_index(datetime.strptime("2023-12-31", "%Y-%m-%d"), min_date) == 52
    )

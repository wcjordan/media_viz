"""Unit tests for the preprocessing module."""

import io
from unittest.mock import mock_open, patch

from preprocessing.preprocess import load_weekly_records


def test_year_propagation():
    """Test that the year is correctly propagated through multiple date ranges."""
    # Create a mock CSV file in memory
    csv_content = io.StringIO(
        """,Notes
           Jan 1-6 (2023),Started Book A
           Jan 29-Feb 4,Finished Book A
           Dec 29-Dec 31,Started Game B
           Jan 1-4 (2024),Finished Game B"""
    )
    csv_content = "\n".join(
        [line.strip() for line in csv_content.getvalue().splitlines()]
    )

    # Mock the open function to return our StringIO object
    with patch("builtins.open", mock_open(read_data=csv_content)):
        records = load_weekly_records("dummy_path.csv")

    # Check that years are correctly propagated
    assert records[0]["start_date"].startswith("2023-")  # Assuming current year is 2023
    assert records[0]["end_date"].startswith("2023-")
    assert records[1]["start_date"].startswith("2023-")
    assert records[1]["end_date"].startswith("2023-")
    assert records[2]["start_date"].startswith("2023-")  # December
    assert records[2]["end_date"].startswith("2023-")
    assert records[3]["start_date"].startswith(
        "2024-"
    )  # January continues with new year
    assert records[3]["end_date"].startswith("2024-")

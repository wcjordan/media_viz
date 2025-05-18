"""Unit tests for the preprocessing module."""

import io
import logging
from unittest.mock import mock_open, patch

from preprocessing.preprocess import parse_date_range, load_weekly_records


def test_parse_date_range_simple():
    """Test parsing a simple date range within the same month."""
    start_date, end_date, current_year = parse_date_range("Feb 1-6", 2023)
    assert start_date == "2023-02-01"
    assert end_date == "2023-02-06"
    assert current_year == 2023


def test_parse_date_range_cross_month():
    """Test parsing a date range that crosses months."""
    start_date, end_date, current_year = parse_date_range("Jan 28-Feb 3", 2023)
    assert start_date == "2023-01-28"
    assert end_date == "2023-02-03"
    assert current_year == 2023


def test_parse_date_range_new_year():
    """Test parsing a date range that crosses into a new year."""
    start_date, end_date, current_year = parse_date_range("Jan 1-6 (2024)", 2023)
    assert start_date == "2024-01-01"
    assert end_date == "2024-01-06"
    assert current_year == 2024


def test_parse_date_range_cross_year(caplog):
    """Test parsing a date range that crosses years."""
    with caplog.at_level(logging.WARNING):
        start_date, end_date, current_year = parse_date_range("Dec 28-Jan 3", 2023)
    assert (
        "Error parsing end date 'Jan 3': Rows are not expected to cross years"
        in caplog.text
    )
    assert start_date is None
    assert end_date is None
    assert current_year == 2023


def test_parse_date_range_single_date(caplog):
    """Test parsing a single date (not a range)."""
    with caplog.at_level(logging.WARNING):
        start_date, end_date, current_year = parse_date_range("Mar 15", 2023)
    assert "No range found in date 'Mar 15'" in caplog.text
    assert start_date is None
    assert end_date is None
    assert current_year == 2023


def test_parse_date_range_no_start_month(caplog):
    """Test parsing a date range with no start month."""
    with caplog.at_level(logging.WARNING):
        start_date, end_date, current_year = parse_date_range("15-Mar 20", 2023)
    assert (
        "Error parsing start date '15': Month not found in start date string"
        in caplog.text
    )
    assert start_date is None
    assert end_date is None
    assert current_year == 2023


def test_parse_date_range_different_separators():
    """Test parsing date ranges with different separators."""
    # Hyphen
    start_date, end_date, current_year = parse_date_range("Apr 1-5", 2023)
    assert start_date == "2023-04-01"
    assert end_date == "2023-04-05"
    assert current_year == 2023

    # En dash
    start_date, end_date, current_year = parse_date_range("Apr 1–5", 2023)
    assert start_date == "2023-04-01"
    assert end_date == "2023-04-05"
    assert current_year == 2023

    # Word "to"
    start_date, end_date, current_year = parse_date_range("Apr 1 to 5", 2023)
    assert start_date == "2023-04-01"
    assert end_date == "2023-04-05"
    assert current_year == 2023


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
        records = load_weekly_records("preprocessing/dummy_path.csv")

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

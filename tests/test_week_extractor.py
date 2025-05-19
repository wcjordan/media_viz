"""Unit tests for the week record extraction functionality."""

import logging

from preprocessing.week_extractor import _parse_date_range


def test_parse_date_range_simple():
    """Test parsing a simple date range within the same month."""
    start_date, end_date, current_year = _parse_date_range("Feb 1-6", 2023)
    assert start_date == "2023-02-01"
    assert end_date == "2023-02-06"
    assert current_year == 2023


def test_parse_date_range_cross_month():
    """Test parsing a date range that crosses months."""
    start_date, end_date, current_year = _parse_date_range("Jan 28-Feb 3", 2023)
    assert start_date == "2023-01-28"
    assert end_date == "2023-02-03"
    assert current_year == 2023


def test_parse_date_range_new_year():
    """Test parsing a date range that crosses into a new year."""
    start_date, end_date, current_year = _parse_date_range("Jan 1-6 (2024)", 2023)
    assert start_date == "2024-01-01"
    assert end_date == "2024-01-06"
    assert current_year == 2024


def test_parse_date_range_cross_year(caplog):
    """Test parsing a date range that crosses years."""
    with caplog.at_level(logging.WARNING):
        start_date, end_date, current_year = _parse_date_range("Dec 28-Jan 3", 2023)
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
        start_date, end_date, current_year = _parse_date_range("Mar 15", 2023)
    assert "No range found in date 'Mar 15'" in caplog.text
    assert start_date is None
    assert end_date is None
    assert current_year == 2023


def test_parse_date_range_no_start_month(caplog):
    """Test parsing a date range with no start month."""
    with caplog.at_level(logging.WARNING):
        start_date, end_date, current_year = _parse_date_range("15-Mar 20", 2023)
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
    start_date, end_date, current_year = _parse_date_range("Apr 1-5", 2023)
    assert start_date == "2023-04-01"
    assert end_date == "2023-04-05"
    assert current_year == 2023

    # En dash
    start_date, end_date, current_year = _parse_date_range("Apr 1–5", 2023)
    assert start_date == "2023-04-01"
    assert end_date == "2023-04-05"
    assert current_year == 2023

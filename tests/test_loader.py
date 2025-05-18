import pytest
from datetime import datetime
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from preprocess import parse_date_range, load_weekly_records

def test_parse_date_range_simple():
    """Test parsing a simple date range within the same month."""
    start_date, end_date = parse_date_range("Feb 1-6", 2023)
    assert start_date == "2023-02-01"
    assert end_date == "2023-02-06"

def test_parse_date_range_cross_month():
    """Test parsing a date range that crosses months."""
    start_date, end_date = parse_date_range("Jan 28-Feb 3", 2023)
    assert start_date == "2023-01-28"
    assert end_date == "2023-02-03"

def test_parse_date_range_cross_year():
    """Test parsing a date range that crosses years."""
    start_date, end_date = parse_date_range("Dec 28-Jan 3", 2023)
    assert start_date == "2023-12-28"
    assert end_date == "2024-01-03"

def test_parse_date_range_single_date():
    """Test parsing a single date (not a range)."""
    start_date, end_date = parse_date_range("Mar 15", 2023)
    assert start_date == "2023-03-15"
    assert end_date == "2023-03-15"

def test_parse_date_range_abbreviated_start():
    """Test parsing a date range with abbreviated start (just the day)."""
    start_date, end_date = parse_date_range("15-Mar 20", 2023)
    assert start_date == "2023-03-15"
    assert end_date == "2023-03-20"

def test_parse_date_range_different_separators():
    """Test parsing date ranges with different separators."""
    # Hyphen
    start_date, end_date = parse_date_range("Apr 1-5", 2023)
    assert start_date == "2023-04-01"
    assert end_date == "2023-04-05"
    
    # En dash
    start_date, end_date = parse_date_range("Apr 1–5", 2023)
    assert start_date == "2023-04-01"
    assert end_date == "2023-04-05"
    
    # Word "to"
    start_date, end_date = parse_date_range("Apr 1 to 5", 2023)
    assert start_date == "2023-04-01"
    assert end_date == "2023-04-05"

def test_year_propagation():
    """Test that the year is correctly propagated through multiple date ranges."""
    # Create a mock CSV file in memory
    import io
    import csv
    from unittest.mock import patch
    
    csv_content = io.StringIO("""DateRange,Notes
Feb 1-6,Started Book A
Feb 7-13,Finished Book A
Dec 28-Jan 3,Started Game B
Jan 4-10,Finished Game B""")
    
    # Mock the open function to return our StringIO object
    with patch('builtins.open', return_value=csv_content):
        records = load_weekly_records("dummy_path.csv")
    
    # Check that years are correctly propagated
    assert records[0]['start_date'].startswith("2023-")  # Assuming current year is 2023
    assert records[1]['start_date'].startswith("2023-")
    assert records[2]['start_date'].startswith("2023-")  # December
    assert records[2]['end_date'].startswith("2024-")    # January of next year
    assert records[3]['start_date'].startswith("2024-")  # January continues with new year

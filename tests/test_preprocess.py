"""Unit tests for the preprocessing module."""

import io
from unittest.mock import mock_open, patch


from preprocessing.preprocess import (
    load_weekly_records,
    process_and_save,
    calculate_statistics,
)


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


def test_process_and_save():
    """Test the end-to-end processing and saving functionality."""
    # Create mock data
    csv_content = io.StringIO(
        """,Notes
           Jan 1-6 (2023),Started The Hobbit
           Jan 29-Feb 4,Finished The Hobbit"""
    )
    csv_content = "\n".join(
        [line.strip() for line in csv_content.getvalue().splitlines()]
    )

    # Mock dependencies
    with patch("builtins.open", mock_open()) as mock_file:
        # Configure the mock to return our CSV content when opened for reading
        mock_file.return_value.__enter__.return_value.read.return_value = csv_content

        # Mock the extract_entries function
        with patch("preprocessing.preprocess.extract_entries") as mock_extract:
            mock_extract.return_value = [
                {"title": "The Hobbit", "action": "started", "date": "2023-01-01"},
                {"title": "The Hobbit", "action": "finished", "date": "2023-02-01"},
            ]

            # Mock the apply_tagging function
            with patch("preprocessing.preprocess.apply_tagging") as mock_tag:
                mock_tag.return_value = [
                    {
                        "title": "The Hobbit",
                        "canonical_title": "The Hobbit",
                        "type": "Book",
                        "action": "started",
                        "date": "2023-01-01",
                        "tags": {"genre": ["Fantasy"]},
                        "confidence": 0.9,
                    },
                    {
                        "title": "The Hobbit",
                        "canonical_title": "The Hobbit",
                        "type": "Book",
                        "action": "finished",
                        "date": "2023-02-01",
                        "tags": {"genre": ["Fantasy"]},
                        "confidence": 0.9,
                    },
                ]

                # Call the function under test
                stats = process_and_save("input.csv", "output.json")

    # Verify the results
    assert stats["total_entries"] == 2
    assert stats["by_type"]["Book"] == 2
    assert mock_file.call_count > 0  # File was opened
    assert mock_extract.call_count > 0  # extract_entries was called
    assert mock_tag.call_count > 0  # apply_tagging was called


def test_calculate_statistics():
    """Test the statistics calculation function."""
    entries = [
        {
            "title": "Game A",
            "type": "Game",
            "action": "started",
            "date": "2023-01-01",
            "confidence": 0.9,
        },
        {
            "title": "Game A",
            "type": "Game",
            "action": "finished",
            "date": "2023-02-01",
            "confidence": 0.9,
        },
        {
            "title": "Book B",
            "type": "Book",
            "action": "started",
            "date": "2023-03-01",
            "confidence": 0.4,
            "warnings": ["Low confidence match"],
        },
        {
            "title": "Movie C",
            "type": "Movie",
            "action": "finished",
            "date": "2023-04-01",
            "confidence": 1.0,
        },
    ]

    stats = calculate_statistics(entries)

    assert stats["total_entries"] == 4
    assert stats["by_type"]["Game"] == 2
    assert stats["by_type"]["Book"] == 1
    assert stats["by_type"]["Movie"] == 1
    assert stats["low_confidence"] == 1
    assert stats["with_warnings"] == 1
    assert stats["hint_applied"] == 1

"""Unit tests for the preprocessing module."""

import io
from unittest.mock import mock_open, patch


from preprocessing.preprocess import (
    calculate_statistics,
    _load_weekly_records,
    process_and_save,
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
        records = _load_weekly_records("dummy_path.csv")

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
    with patch("builtins.open", mock_open(read_data=csv_content)), patch(
        "os.path.exists", return_value=True
    ), patch("preprocessing.preprocess.extract_entries") as mock_extract, patch(
        "preprocessing.preprocess.apply_tagging"
    ) as mock_tag:
        mock_extract.return_value = [
            {"title": "The Hobbit", "action": "started", "date": "2023-01-01"},
            {"title": "The Hobbit", "action": "finished", "date": "2023-02-01"},
        ]

        mock_tag.return_value = [
            {
                "tagged": {
                    "canonical_title": "The Hobbit",
                    "type": "Book",
                    "tags": {"genre": ["Fantasy"]},
                    "confidence": 0.9,
                },
                "original_titles": ["The Hobbit"],
                "started_dates": ["2023-01-01"],
                "finished_dates": [],
            },
            {
                "tagged": {
                    "canonical_title": "The Hobbit",
                    "type": "Book",
                    "tags": {"genre": ["Fantasy"]},
                    "confidence": 0.9,
                },
                "original_titles": ["The Hobbit"],
                "started_dates": [],
                "finished_dates": ["2023-02-01"],
            },
        ]

        # Call the function under test
        stats = process_and_save("input.csv", "output.json")

    # Verify the results
    assert stats["total_entries"] == 2
    assert stats["by_type"]["Book"] == 2
    assert mock_extract.call_count > 0  # extract_entries was called
    assert mock_tag.call_count > 0  # apply_tagging was called


def test_group_entries():
    """Test the _group_entries function that groups individual entries by title."""
    from preprocessing.preprocess import _group_entries

    # Test with multiple entries for the same title
    individual_entries = [
        {"title": "The Hobbit", "action": "started", "date": "2023-01-01"},
        {"title": "The Hobbit", "action": "finished", "date": "2023-02-01"},
        {"title": "Game of Thrones", "action": "started", "date": "2023-03-01"},
    ]

    grouped = _group_entries(individual_entries)
    
    # Should have 2 entries (one for each unique title)
    assert len(grouped) == 2
    
    # Find The Hobbit entry
    hobbit_entry = next(entry for entry in grouped if entry["title"] == "The Hobbit")
    assert hobbit_entry["started_dates"] == ["2023-01-01"]
    assert hobbit_entry["finished_dates"] == ["2023-02-01"]
    
    # Find Game of Thrones entry
    got_entry = next(entry for entry in grouped if entry["title"] == "Game of Thrones")
    assert got_entry["started_dates"] == ["2023-03-01"]
    assert got_entry["finished_dates"] == []


def test_group_entries_edge_cases():
    """Test edge cases for the _group_entries function."""
    from preprocessing.preprocess import _group_entries
    
    # Test with empty list
    assert _group_entries([]) == []
    
    # Test with entries missing title
    entries_missing_title = [
        {"action": "started", "date": "2023-01-01"},
        {"title": "", "action": "started", "date": "2023-01-02"},
    ]
    grouped = _group_entries(entries_missing_title)
    assert len(grouped) == 0  # Should skip entries without title
    
    # Test with duplicate dates
    duplicate_dates = [
        {"title": "Book A", "action": "started", "date": "2023-01-01"},
        {"title": "Book A", "action": "started", "date": "2023-01-01"},  # Duplicate
        {"title": "Book A", "action": "finished", "date": "2023-02-01"},
        {"title": "Book A", "action": "finished", "date": "2023-02-01"},  # Duplicate
    ]
    grouped = _group_entries(duplicate_dates)
    assert len(grouped) == 1
    assert grouped[0]["started_dates"] == ["2023-01-01"]  # No duplicates
    assert grouped[0]["finished_dates"] == ["2023-02-01"]  # No duplicates
    
    # Test with unknown action
    unknown_action = [
        {"title": "Book A", "action": "unknown", "date": "2023-01-01"},
    ]
    grouped = _group_entries(unknown_action)
    assert len(grouped) == 1
    assert grouped[0]["started_dates"] == []
    assert grouped[0]["finished_dates"] == []


def test_calculate_statistics():
    """Test the statistics calculation function."""
    tagged_entries = [
        {
            "canonical_title": "Game A",
            "type": "Game",
            "confidence": 0.9,
        },
        {
            "canonical_title": "Game A",
            "type": "Game",
            "confidence": 0.9,
        },
        {
            "canonical_title": "Book B",
            "type": "Book",
            "confidence": 0.4,
            "warnings": ["Low confidence match"],
        },
        {
            "canonical_title": "Movie C",
            "type": "Movie",
            "confidence": 1.0,
        },
    ]
    entries = [{"tagged": entry} for entry in tagged_entries]
    stats = calculate_statistics(entries)

    assert stats["total_entries"] == 4
    assert stats["by_type"]["Game"] == 2
    assert stats["by_type"]["Book"] == 1
    assert stats["by_type"]["Movie"] == 1
    assert stats["low_confidence"] == 1

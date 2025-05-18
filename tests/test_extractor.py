"""Unit tests for the media entry extraction functionality."""

import pytest
from preprocessing.preprocess import extract_entries


def test_extract_single_entry():
    """Test extracting a single media entry from notes."""
    record = {
        "start_date": "2023-01-01",
        "end_date": "2023-01-07",
        "raw_notes": "Started reading The Hobbit",
    }

    entries = extract_entries(record)

    assert len(entries) == 1
    assert entries[0]["raw_text"] == "Started reading The Hobbit"
    assert entries[0]["action"] == "started"
    assert entries[0]["title"] == "The Hobbit"
    assert entries[0]["start_date"] == "2023-01-01"
    assert entries[0]["end_date"] == "2023-01-07"


def test_extract_multiple_entries():
    """Test extracting multiple media entries from notes with & separator."""
    record = {
        "start_date": "2023-02-01",
        "end_date": "2023-02-07",
        "raw_notes": "Started playing Elden Ring & Finished reading Dune",
    }

    entries = extract_entries(record)

    assert len(entries) == 2

    assert entries[0]["raw_text"] == "Started playing Elden Ring"
    assert entries[0]["action"] == "started"
    assert entries[0]["title"] == "Elden Ring"

    assert entries[1]["raw_text"] == "Finished reading Dune"
    assert entries[1]["action"] == "finished"
    assert entries[1]["title"] == "Dune"


def test_extract_entries_with_newlines():
    """Test extracting entries separated by newlines."""
    record = {
        "start_date": "2023-03-01",
        "end_date": "2023-03-07",
        "raw_notes": "Watched The Last of Us\nStarted Hogwarts Legacy",
    }

    entries = extract_entries(record)

    assert len(entries) == 2

    assert entries[0]["raw_text"] == "Watched The Last of Us"
    assert entries[0]["action"] == "watched"
    assert entries[0]["title"] == "The Last of Us"

    assert entries[1]["raw_text"] == "Started Hogwarts Legacy"
    assert entries[1]["action"] == "started"
    assert entries[1]["title"] == "Hogwarts Legacy"


def test_various_action_phrasings():
    """Test different phrasings for actions."""
    test_cases = [
        ("Started The Witcher 3", "started", "The Witcher 3"),
        ("Finished reading Lord of the Rings", "finished", "Lord of the Rings"),
        ("Watched Succession", "watched", "Succession"),
        ("Playing Cyberpunk 2077", "playing", "Cyberpunk 2077"),
        ("Reading Foundation", "reading", "Foundation"),
        ("Completed God of War", "completed", "God of War"),
        ("Began Breath of the Wild", "started", "Breath of the Wild"),
        ("Continuing Breaking Bad", "continuing", "Breaking Bad"),
    ]

    for raw_text, expected_action, expected_title in test_cases:
        record = {
            "start_date": "2023-04-01",
            "end_date": "2023-04-07",
            "raw_notes": raw_text,
        }

        entries = extract_entries(record)

        assert len(entries) == 1
        assert entries[0]["action"] == expected_action
        assert entries[0]["title"] == expected_title


def test_general_mention():
    """Test handling of entries without explicit actions."""
    record = {
        "start_date": "2023-05-01",
        "end_date": "2023-05-07",
        "raw_notes": "The Legend of Zelda",
    }

    entries = extract_entries(record)

    assert len(entries) == 1
    assert entries[0]["action"] == "mentioned"
    assert entries[0]["title"] == "The Legend of Zelda"


def test_empty_or_invalid_record():
    """Test handling of empty or invalid records."""
    # Empty raw_notes
    record = {"start_date": "2023-06-01", "end_date": "2023-06-07", "raw_notes": ""}

    entries = extract_entries(record)
    assert len(entries) == 0

    # Missing dates
    record = {"raw_notes": "Started Final Fantasy XVI"}

    entries = extract_entries(record)
    assert len(entries) == 0

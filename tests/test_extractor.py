"""Unit tests for the media entry extraction functionality."""

from preprocessing.preprocess import extract_entries


def test_extract_single_entry():
    """Test extracting a single media entry from notes."""
    record = {
        "start_date": "2023-01-01",
        "end_date": "2023-01-07",
        "raw_notes": "Started The Hobbit",
    }

    entries = extract_entries(record)

    assert len(entries) == 1
    assert entries[0]["action"] == "started"
    assert entries[0]["title"] == "The Hobbit"
    assert entries[0]["date"] == "2023-01-01"


def test_extract_multiple_entries():
    """Test extracting multiple media entries from notes with & separator."""
    record = {
        "start_date": "2023-02-01",
        "end_date": "2023-02-07",
        "raw_notes": "Started Elden Ring & Cyberpunk 2077",
    }

    entries = extract_entries(record)

    assert len(entries) == 2

    assert entries[0]["action"] == "started"
    assert entries[0]["title"] == "Elden Ring"
    assert entries[0]["date"] == "2023-02-01"

    assert entries[1]["action"] == "started"
    assert entries[1]["title"] == "Cyberpunk 2077"
    assert entries[1]["date"] == "2023-02-01"


def test_extract_entries_with_newlines():
    """Test extracting entries separated by newlines."""
    record = {
        "start_date": "2023-03-01",
        "end_date": "2023-03-07",
        "raw_notes": "Finished The Last of Us\nStarted Hogwarts Legacy",
    }

    entries = extract_entries(record)

    assert len(entries) == 2

    assert entries[0]["action"] == "finished"
    assert entries[0]["title"] == "The Last of Us"
    assert entries[0]["date"] == "2023-03-01"

    assert entries[1]["action"] == "started"
    assert entries[1]["title"] == "Hogwarts Legacy"
    assert entries[1]["date"] == "2023-03-01"


def test_single_week_action_phrasings():
    """Test different phrasings for actions which indicate the media was started and finished in the week."""
    test_cases = [
        ("Read Lord of the Rings", "Lord of the Rings"),
        ("Watched Succession", "Succession"),
        ("Played Cyberpunk 2077", "Cyberpunk 2077"),
    ]

    for raw_text, expected_title in test_cases:
        record = {
            "start_date": "2023-04-01",
            "end_date": "2023-04-07",
            "raw_notes": raw_text,
        }

        entries = extract_entries(record)

        assert len(entries) == 2
        assert entries[0]["title"] == expected_title
        assert entries[1]["title"] == expected_title
        assert entries[0]["action"] == "finished"
        assert entries[1]["action"] == "started"
        assert entries[0]["date"] == "2023-04-01"
        assert entries[1]["date"] == "2023-04-01"


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

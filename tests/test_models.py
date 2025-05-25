"""Unit tests for the Pydantic models."""

import json

import pytest
from pydantic import ValidationError

from preprocessing.models import MediaEntry, TaggedEntry, MediaTags


def test_media_tags_model():
    """Test the MediaTags model."""
    # Test with default values
    tags = MediaTags()
    assert tags.genre == []
    assert tags.platform == []
    assert tags.mood == []

    # Test with provided values
    tags = MediaTags(genre=["Fantasy", "Adventure"], platform=["PS5"], mood=["Epic"])
    assert tags.genre == ["Fantasy", "Adventure"]
    assert tags.platform == ["PS5"]
    assert tags.mood == ["Epic"]

    # Test serialization
    tags_dict = tags.model_dump()
    assert tags_dict["genre"] == ["Fantasy", "Adventure"]
    assert tags_dict["platform"] == ["PS5"]
    assert tags_dict["mood"] == ["Epic"]


def test_tagged_entry_model():
    """Test the TaggedEntry model."""
    # Test with minimal required fields
    tagged = TaggedEntry(
        canonical_title="Final Fantasy VII Remake",
        type="Game",
        confidence=0.92,
        source="igdb",
    )
    assert tagged.canonical_title == "Final Fantasy VII Remake"
    assert tagged.type == "Game"
    assert tagged.confidence == 0.92
    assert tagged.source == "igdb"
    assert tagged.tags.genre == []
    assert tagged.poster_path is None

    # Test with all fields
    tagged = TaggedEntry(
        canonical_title="Final Fantasy VII Remake",
        type="Game",
        tags=MediaTags(genre=["JRPG"], platform=["PS5"]),
        confidence=0.92,
        source="igdb",
        poster_path="https://example.com/poster.jpg",
    )
    assert tagged.canonical_title == "Final Fantasy VII Remake"
    assert tagged.type == "Game"
    assert tagged.tags.genre == ["JRPG"]
    assert tagged.tags.platform == ["PS5"]
    assert tagged.confidence == 0.92
    assert tagged.source == "igdb"
    assert tagged.poster_path == "https://example.com/poster.jpg"


def test_media_entry_model():
    """Test the MediaEntry model."""
    # Test with minimal required fields
    entry = MediaEntry(
        canonical_title="Final Fantasy VII Remake",
        original_titles=["FF7"],
        tagged=TaggedEntry(
            canonical_title="Final Fantasy VII Remake",
            type="Game",
            confidence=0.92,
            source="igdb",
        ),
    )
    assert entry.canonical_title == "Final Fantasy VII Remake"
    assert entry.original_titles == ["FF7"]
    assert entry.started_dates == []
    assert entry.finished_dates == []
    assert entry.duration_days is None
    assert entry.status == "unknown"

    # Test with all fields
    entry = MediaEntry(
        canonical_title="Final Fantasy VII Remake",
        original_titles=["FF7", "Final Fantasy 7"],
        tagged=TaggedEntry(
            canonical_title="Final Fantasy VII Remake",
            type="Game",
            tags=MediaTags(genre=["JRPG"], platform=["PS5"]),
            confidence=0.92,
            source="igdb",
        ),
        started_dates=["2023-02-14"],
        finished_dates=["2023-03-07"],
    )
    assert entry.canonical_title == "Final Fantasy VII Remake"
    assert entry.original_titles == ["FF7", "Final Fantasy 7"]
    assert entry.started_dates == ["2023-02-14"]
    assert entry.finished_dates == ["2023-03-07"]
    assert entry.duration_days == 21
    assert entry.status == "completed"


def test_media_entry_date_validation():
    """Test date validation in the MediaEntry model."""
    # Test with invalid date format
    with pytest.raises(ValidationError):
        MediaEntry(
            canonical_title="Test",
            original_titles=["Test"],
            tagged=TaggedEntry(
                canonical_title="Test",
                type="Book",
                confidence=0.9,
                source="openlibrary",
            ),
            started_dates=["02/14/2023"],  # Invalid format
        )


def test_media_entry_json_serialization():
    """Test JSON serialization of the MediaEntry model."""
    entry = MediaEntry(
        canonical_title="Final Fantasy VII Remake",
        original_titles=["FF7", "Final Fantasy 7"],
        tagged=TaggedEntry(
            canonical_title="Final Fantasy VII Remake",
            type="Game",
            tags=MediaTags(genre=["JRPG"], platform=["PS5"]),
            confidence=0.92,
            source="igdb",
        ),
        started_dates=["2023-02-14"],
        finished_dates=["2023-03-07"],
    )

    # Convert to JSON and back
    entry_json = entry.model_dump_json()
    entry_dict = json.loads(entry_json)

    # Verify structure
    assert entry_dict["canonical_title"] == "Final Fantasy VII Remake"
    assert entry_dict["original_titles"] == ["FF7", "Final Fantasy 7"]
    assert entry_dict["tagged"]["canonical_title"] == "Final Fantasy VII Remake"
    assert entry_dict["tagged"]["type"] == "Game"
    assert entry_dict["tagged"]["tags"]["genre"] == ["JRPG"]
    assert entry_dict["tagged"]["tags"]["platform"] == ["PS5"]
    assert entry_dict["tagged"]["confidence"] == 0.92
    assert entry_dict["tagged"]["source"] == "igdb"
    assert entry_dict["started_dates"] == ["2023-02-14"]
    assert entry_dict["finished_dates"] == ["2023-03-07"]

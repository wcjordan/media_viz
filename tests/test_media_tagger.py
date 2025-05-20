"""Unit tests for the media tagging functionality."""

import os
from unittest.mock import patch, mock_open
import yaml

import pytest

from preprocessing.media_tagger import (
    _load_hints,
    _query_tmdb,
    _query_igdb,
    _query_openlibrary,
    apply_tagging,
)


@pytest.fixture(name="sample_hints")
def fixture_sample_hints():
    """Sample hints data for testing."""
    return {
        "FF7": {
            "canonical_title": "Final Fantasy VII Remake",
            "type": "Game",
            "tags": {
                "platform": ["PS5"],
                "genre": ["JRPG", "Adventure"],
                "mood": ["Epic"],
            },
        },
        "LOTR": {
            "canonical_title": "The Lord of the Rings",
            "type": "Book",
            "tags": {
                "genre": ["Fantasy"],
                "mood": ["Epic"],
            },
        },
    }


@pytest.fixture(name="sample_entries")
def fixture_sample_entries():
    """Sample media entries for testing."""
    return [
        {"title": "Started FF7", "action": "started", "date": "2023-01-01"},
        {"title": "Finished The Hobbit", "action": "finished", "date": "2023-02-15"},
        {"title": "Watched Succession", "action": "watched", "date": "2023-03-10"},
    ]


def test_load_hints_success(sample_hints):
    """Test loading hints from a YAML file successfully."""
    mock_yaml_content = yaml.dump(sample_hints)

    with patch("builtins.open", mock_open(read_data=mock_yaml_content)):
        with patch("os.path.exists", return_value=True):
            hints = _load_hints("fake_path.yaml")

    assert hints == sample_hints
    assert "FF7" in hints
    assert hints["FF7"]["canonical_title"] == "Final Fantasy VII Remake"


def test_load_hints_file_not_found():
    """Test handling when hints file is not found."""
    with patch("os.path.exists", return_value=False):
        hints = _load_hints("nonexistent_file.yaml")

    assert hints == {}


def test_load_hints_invalid_yaml():
    """Test handling invalid YAML content."""
    invalid_yaml = "invalid: yaml: content: - ["

    with patch("builtins.open", mock_open(read_data=invalid_yaml)):
        with patch("os.path.exists", return_value=True):
            hints = _load_hints("invalid.yaml")

    assert hints == {}


def test_query_tmdb():
    """Test querying TMDB API."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}):
        api_hits = _query_tmdb("The Matrix")

    # Since this is a stub, we're just checking the structure
    assert api_hits is not None
    assert isinstance(api_hits, list)
    assert all("type" in hit for hit in api_hits)
    assert all(0 <= hit.get("confidence", 0) <= 1 for hit in api_hits)


def test_query_tmdb_no_api_key():
    """Test querying TMDB API with no API key."""
    with patch.dict(os.environ, {}, clear=True):
        api_hits = _query_tmdb("The Matrix")

    assert api_hits is None


def test_query_igdb():
    """Test querying IGDB API."""
    with patch.dict(os.environ, {"IGDB_API_KEY": "fake_key"}):
        api_hits = _query_igdb("Elden Ring")

    # Since this is a stub, we're just checking the structure
    assert api_hits is not None
    assert isinstance(api_hits, list)
    assert all("type" in hit for hit in api_hits)
    assert all(0 <= hit.get("confidence", 0) <= 1 for hit in api_hits)


def test_query_openlibrary():
    """Test querying Open Library API."""
    with patch.dict(os.environ, {"OPENLIBRARY_API_KEY": "fake_key"}):
        api_hits = _query_openlibrary("The Hobbit")

    # Since this is a stub, we're just checking the structure
    assert api_hits is not None
    assert isinstance(api_hits, list)
    assert all("type" in hit for hit in api_hits)
    assert all(0 <= hit.get("confidence", 0) <= 1 for hit in api_hits)


def test_apply_tagging_with_hints(sample_entries, sample_hints):
    """Test applying tagging with hints."""
    mock_yaml_content = yaml.dump(sample_hints)

    with patch("builtins.open", mock_open(read_data=mock_yaml_content)):
        with patch("os.path.exists", return_value=True):
            tagged_entries = apply_tagging(sample_entries, "fake_path.yaml")

    # Check the entry that should match a hint
    ff7_entry = next(entry for entry in tagged_entries if "FF7" in entry["title"])
    assert ff7_entry["canonical_title"] == "Final Fantasy VII Remake"
    assert ff7_entry["type"] == "Game"
    assert ff7_entry["tags"]["platform"] == ["PS5"]
    assert ff7_entry["confidence"] == 1.0


def test_apply_tagging_with_api_calls(sample_entries):
    """Test applying tagging with API calls when no hints match."""
    # Mock the API calls
    with patch("preprocessing.media_tagger.load_hints", return_value={}):
        with patch("preprocessing.media_tagger.query_tmdb") as mock_tmdb:
            with patch("preprocessing.media_tagger.query_igdb") as mock_igdb:
                with patch(
                    "preprocessing.media_tagger.query_openlibrary"
                ) as mock_openlibrary:
                    # Set up mock returns
                    mock_tmdb.return_value = (
                        "Succession",
                        {"type": "TV", "tags": {"genre": ["Drama"]}},
                        0.9,
                    )
                    mock_openlibrary.return_value = (
                        "The Hobbit",
                        {"type": "Book", "tags": {"genre": ["Fantasy"]}},
                        0.8,
                    )
                    mock_igdb.return_value = (
                        "Elden Ring",
                        {"type": "Game", "tags": {"platform": ["PS5"]}},
                        0.85,
                    )

                    tagged_entries = apply_tagging(sample_entries)

    # Check the TV show entry
    succession_entry = next(
        entry for entry in tagged_entries if "Succession" in entry["title"]
    )
    assert succession_entry["canonical_title"] == "Succession"
    assert succession_entry["type"] == "TV"
    assert succession_entry["tags"]["genre"] == ["Drama"]
    assert succession_entry["confidence"] == 0.9

    # Check the book entry
    hobbit_entry = next(entry for entry in tagged_entries if "Hobbit" in entry["title"])
    assert hobbit_entry["canonical_title"] == "The Hobbit"
    assert hobbit_entry["type"] == "Book"
    assert hobbit_entry["tags"]["genre"] == ["Fantasy"]
    assert hobbit_entry["confidence"] == 0.8


def test_apply_tagging_api_failure(sample_entries):
    """Test applying tagging when API calls fail."""
    # Mock the API calls to fail
    with patch("preprocessing.media_tagger.load_hints", return_value={}):
        with patch(
            "preprocessing.media_tagger.query_tmdb", return_value=(None, None, 0.0)
        ):
            with patch(
                "preprocessing.media_tagger.query_igdb", return_value=(None, None, 0.0)
            ):
                with patch(
                    "preprocessing.media_tagger.query_openlibrary",
                    return_value=(None, None, 0.0),
                ):
                    tagged_entries = apply_tagging(sample_entries)

    # Check that fallback values are used
    for entry in tagged_entries:
        assert "canonical_title" in entry
        assert "type" in entry
        assert "tags" in entry
        assert entry["tags"] == {}
        assert entry["confidence"] == 0.1
        assert "warnings" in entry
        assert "Failed to fetch metadata from APIs" in entry["warnings"]


def test_apply_tagging_missing_title():
    """Test applying tagging to an entry with a missing title."""
    entries = [{"action": "started", "date": "2023-01-01"}]  # Missing title

    with patch("preprocessing.media_tagger.load_hints", return_value={}):
        tagged_entries = apply_tagging(entries)

    assert len(tagged_entries) == 1
    assert "canonical_title" not in tagged_entries[0]
    assert "type" not in tagged_entries[0]

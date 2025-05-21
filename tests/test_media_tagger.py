"""Unit tests for the media tagging functionality."""

import logging
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
        {"title": "FF7", "action": "started", "date": "2023-01-01"},
        {"title": "The Hobbit", "action": "finished", "date": "2023-02-15"},
        {"title": "Succesion", "action": "started", "date": "2023-03-10"},
    ]


def test_load_hints_success(sample_hints):
    """Test loading hints from a YAML file successfully."""
    mock_yaml_content = yaml.dump(sample_hints)

    with patch("builtins.open", mock_open(read_data=mock_yaml_content)), patch(
        "os.path.exists", return_value=True
    ):
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

    with patch("builtins.open", mock_open(read_data=invalid_yaml)), patch(
        "os.path.exists", return_value=True
    ):
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


def test_query_tmdb_no_api_key(caplog):
    """Test querying TMDB API with no API key."""
    with caplog.at_level(logging.WARNING), patch.dict(os.environ, {}, clear=True):
        api_hits = _query_tmdb("The Matrix")

    assert "TMDB_API_KEY not found in environment variables" in caplog.text
    assert api_hits == []


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


def test_apply_tagging_missing_title(caplog):
    """Test applying tagging to an entry with a missing title."""
    entries = [{"action": "started", "date": "2023-01-01"}]  # Missing title

    with caplog.at_level(logging.WARNING), patch(
        "preprocessing.media_tagger._load_hints", return_value={}
    ):
        tagged_entries = apply_tagging(entries)

    assert len(tagged_entries) == 0
    assert "Entry missing title, skipping tagging" in caplog.text


def test_apply_tagging_with_only_hints(sample_entries, sample_hints):
    """Test applying tagging with only hints and no API hits."""
    mock_yaml_content = yaml.dump(sample_hints)

    with patch("builtins.open", mock_open(read_data=mock_yaml_content)), patch(
        "os.path.exists", return_value=True
    ), patch("preprocessing.media_tagger._query_tmdb"), patch(
        "preprocessing.media_tagger._query_igdb"
    ), patch(
        "preprocessing.media_tagger._query_openlibrary"
    ):
        tagged_entries = apply_tagging(sample_entries, "fake_path.yaml")

    # Check the entry that should match a hint
    ff7_entry = next(entry for entry in tagged_entries if "FF7" in entry["title"])
    assert ff7_entry["canonical_title"] == "Final Fantasy VII Remake"
    assert ff7_entry["type"] == "Game"
    assert ff7_entry["tags"]["platform"] == ["PS5"]
    assert ff7_entry["confidence"] == 0.1
    assert ff7_entry["source"] == "fallback"


def test_apply_tagging_with_api_calls(sample_entries):
    """Test applying tagging with API calls when no hints match."""
    # Mock the API calls
    succession_entry = [
        entry for entry in sample_entries if entry["title"] == "Succesion"
    ]
    with patch("preprocessing.media_tagger._load_hints", return_value={}), patch(
        "preprocessing.media_tagger._query_tmdb"
    ) as mock_tmdb, patch("preprocessing.media_tagger._query_igdb") as mock_igdb, patch(
        "preprocessing.media_tagger._query_openlibrary"
    ) as mock_openlibrary:
        # Set up mock returns
        mock_tmdb.return_value = [
            {
                "canonical_title": "Succession",
                "type": "TV",
                "tags": {"genre": ["Drama"]},
                "confidence": 0.9,
                "source": "tmdb",
            }
        ]
        mock_openlibrary.return_value = [
            {
                "canonical_title": "The Hobbit",
                "type": "Book",
                "tags": {"genre": ["Fantasy"]},
                "confidence": 0.6,
                "source": "openlibrary",
            }
        ]
        mock_igdb.return_value = [
            {
                "canonical_title": "Elden Ring",
                "type": "Game",
                "tags": {"platform": ["PS5"]},
                "confidence": 0.55,
                "source": "igdb",
            }
        ]

        tagged_entries = apply_tagging(succession_entry)

    # Assert entry is tagged correctly
    assert len(tagged_entries) == 1
    tagged_entry = tagged_entries[0]
    assert tagged_entry["title"] == "Succesion"
    assert tagged_entry["action"] == "started"
    assert tagged_entry["canonical_title"] == "Succession"
    assert tagged_entry["type"] == "TV"
    assert tagged_entry["tags"]["genre"] == ["Drama"]
    assert tagged_entry["confidence"] == 0.9


def test_apply_tagging_api_failure(sample_entries, caplog):
    """Test applying tagging when API calls fail."""
    # Mock the API calls to fail
    ff7_entry = [entry for entry in sample_entries if entry["title"] == "FF7"]

    with caplog.at_level(logging.WARNING), patch(
        "preprocessing.media_tagger._load_hints", return_value={}
    ), patch("preprocessing.media_tagger._query_tmdb", return_value=[]), patch(
        "preprocessing.media_tagger._query_igdb", return_value=[]
    ), patch(
        "preprocessing.media_tagger._query_openlibrary",
        return_value=[],
    ):
        tagged_entries = apply_tagging(ff7_entry)

    # Check that fallback values are used
    assert "No API hits found for entry: {'title': 'FF7'," in caplog.text
    assert "Low confidence match for entry: {'title': 'FF7'," in caplog.text
    assert len(tagged_entries) == 1
    for entry in tagged_entries:
        assert entry["canonical_title"] == entry["title"]
        assert entry["type"] == "Other / Unknown"
        assert entry["tags"] == {}
        assert entry["confidence"] == 0.1
        assert entry["source"] == "fallback"


# TODO API calls + hints
# TODO API call with close confidence
# TODO API call with low confidence

"""Unit tests for the media tagging functionality."""

import logging
import os
from unittest.mock import patch, mock_open
import yaml

import pytest

from preprocessing.media_tagger import apply_tagging
from preprocessing.utils import load_hints
from preprocessing.media_apis import (
    query_tmdb,
    query_igdb,
    query_openlibrary,
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
        hints = load_hints("fake_path.yaml")

    assert hints == sample_hints
    assert "FF7" in hints
    assert hints["FF7"]["canonical_title"] == "Final Fantasy VII Remake"


def test_load_hints_file_not_found():
    """Test handling when hints file is not found."""
    with patch("os.path.exists", return_value=False):
        hints = load_hints("nonexistent_file.yaml")

    assert hints == {}


def test_load_hints_invalid_yaml():
    """Test handling invalid YAML content."""
    invalid_yaml = "invalid: yaml: content: - ["

    with patch("builtins.open", mock_open(read_data=invalid_yaml)), patch(
        "os.path.exists", return_value=True
    ):
        hints = load_hints("invalid.yaml")

    assert hints == {}


def test_query_tmdb():
    """Test querying TMDB API."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"}):
        api_hits = query_tmdb("movie", "The Matrix")

    # Since this is a stub, we're just checking the structure
    assert api_hits is not None
    assert isinstance(api_hits, list)
    assert all("type" in hit for hit in api_hits)
    assert all(0 <= hit.get("confidence", 0) <= 1 for hit in api_hits)


def test_query_tmdb_no_api_key(caplog):
    """Test querying TMDB API with no API key."""
    with caplog.at_level(logging.WARNING), patch.dict(os.environ, {}, clear=True):
        api_hits = query_tmdb("movie", "The Matrix")

    assert "TMDB_API_KEY not found in environment variables" in caplog.text
    assert not api_hits


def test_query_igdb():
    """Test querying IGDB API."""
    with patch.dict(os.environ, {"IGDB_API_KEY": "fake_key"}):
        api_hits = query_igdb("Elden Ring")

    # Since this is a stub, we're just checking the structure
    assert api_hits is not None
    assert isinstance(api_hits, list)
    assert all("type" in hit for hit in api_hits)
    assert all(0 <= hit.get("confidence", 0) <= 1 for hit in api_hits)


def test_query_openlibrary():
    """Test querying Open Library API."""
    with patch.dict(os.environ, {"OPENLIBRARY_API_KEY": "fake_key"}):
        api_hits = query_openlibrary("The Hobbit")

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
    ), patch("preprocessing.media_tagger.query_tmdb"), patch(
        "preprocessing.media_tagger.query_igdb"
    ), patch(
        "preprocessing.media_tagger.query_openlibrary"
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
    """Test applying tagging with API hits."""
    # Mock the API calls
    succession_entry = [
        entry for entry in sample_entries if entry["title"] == "Succesion"
    ]
    with patch("preprocessing.utils.load_hints", return_value={}), patch(
        "preprocessing.media_tagger.query_tmdb"
    ) as mock_tmdb, patch("preprocessing.media_tagger.query_igdb") as mock_igdb, patch(
        "preprocessing.media_tagger.query_openlibrary"
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
    assert tagged_entry["source"] == "tmdb"


def test_apply_tagging_api_failure(sample_entries, caplog):
    """Test applying tagging when API calls fail."""
    # Mock the API calls to fail
    ff7_entry = [entry for entry in sample_entries if entry["title"] == "FF7"]

    with caplog.at_level(logging.WARNING), patch(
        "preprocessing.media_tagger._load_hints", return_value={}
    ), patch("preprocessing.media_tagger.query_tmdb", return_value=[]), patch(
        "preprocessing.media_tagger.query_igdb", return_value=[]
    ), patch(
        "preprocessing.media_tagger.query_openlibrary",
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


def test_apply_tagging_with_api_calls_and_hints(sample_entries):
    """Test applying tagging with API hits and hints."""
    # Mock the API calls
    succession_entry = [entry for entry in sample_entries if entry["title"] == "FF7"]
    with patch("preprocessing.utils.load_hints", return_value={}), patch(
        "preprocessing.media_tagger.query_tmdb"
    ) as mock_tmdb, patch("preprocessing.media_tagger.query_igdb") as mock_igdb, patch(
        "preprocessing.media_tagger.query_openlibrary"
    ) as mock_openlibrary:
        # Set up mock returns
        mock_tmdb.return_value = [
            {
                "canonical_title": "Final Fantasy VII: Advent Children",
                "type": "Movie",
                "tags": {"genre": ["Animation"]},
                "confidence": 0.7,
                "source": "tmdb",
            }
        ]
        mock_openlibrary.return_value = []
        mock_igdb.return_value = [
            {
                "canonical_title": "Final Fantasy VII",
                "type": "Game",
                "tags": {"platform": ["PS1"]},
                "confidence": 0.9,
                "source": "igdb",
            },
            {
                "canonical_title": "Final Fantasy VII: Remake",
                "type": "Game",
                "tags": {"platform": ["PS5"]},
                "confidence": 0.85,
                "source": "igdb",
            },
        ]

        tagged_entries = apply_tagging(succession_entry)

    # Assert entry is tagged correctly
    assert len(tagged_entries) == 1
    tagged_entry = tagged_entries[0]
    assert tagged_entry["title"] == "FF7"
    assert tagged_entry["action"] == "started"
    assert tagged_entry["canonical_title"] == "Final Fantasy VII"
    assert tagged_entry["type"] == "Game"
    assert tagged_entry["tags"]["platform"] == ["PS1"]
    assert tagged_entry["confidence"] == 0.9
    assert tagged_entry["source"] == "igdb"


def test_apply_tagging_with_narrow_confidence(sample_entries, caplog):
    """Test applying tagging when multiple top API hits have a close confidence score."""
    # Mock the API calls
    hobbit_entry = [entry for entry in sample_entries if entry["title"] == "The Hobbit"]
    with caplog.at_level(logging.WARNING), patch(
        "preprocessing.media_tagger._load_hints", return_value={}
    ), patch("preprocessing.media_tagger.query_tmdb") as mock_tmdb, patch(
        "preprocessing.media_tagger.query_igdb"
    ) as mock_igdb, patch(
        "preprocessing.media_tagger.query_openlibrary"
    ) as mock_openlibrary:
        # Set up mock returns
        mock_tmdb.return_value = [
            {
                "canonical_title": "The Hobbit: An Unexpected Journey",
                "type": "Movie",
                "tags": {"genre": ["Adventure"]},
                "confidence": 0.9,
                "source": "tmdb",
            }
        ]
        mock_openlibrary.return_value = [
            {
                "canonical_title": "The Hobbit",
                "type": "Book",
                "tags": {"genre": ["Fantasy"]},
                "confidence": 1.0,
                "source": "openlibrary",
            }
        ]
        mock_igdb.return_value = []

        tagged_entries = apply_tagging(hobbit_entry)

    # Check for warnings about close confidence scores
    assert (
        "Multiple API hits with close confidence for {'title': 'The Hobbit',"
        in caplog.text
    )

    # Assert entry is tagged correctly
    assert len(tagged_entries) == 1
    tagged_entry = tagged_entries[0]
    assert tagged_entry["title"] == "The Hobbit"
    assert tagged_entry["action"] == "finished"
    assert tagged_entry["canonical_title"] == "The Hobbit"
    assert tagged_entry["type"] == "Book"
    assert tagged_entry["tags"]["genre"] == ["Fantasy"]
    assert tagged_entry["confidence"] == 1.0
    assert tagged_entry["source"] == "openlibrary"


def test_apply_tagging_fix_confidence_with_hint(sample_entries, caplog):
    """Test applying tagging with multiple hits resolved by hints."""
    # Mock the API calls
    hobbit_entry = [entry for entry in sample_entries if entry["title"] == "The Hobbit"]
    with caplog.at_level(logging.WARNING), patch(
        "preprocessing.media_tagger._load_hints"
    ) as mock_hints, patch("preprocessing.media_tagger.query_tmdb") as mock_tmdb, patch(
        "preprocessing.media_tagger.query_igdb"
    ) as mock_igdb, patch(
        "preprocessing.media_tagger.query_openlibrary"
    ) as mock_openlibrary:
        # Set up mock returns
        mock_hints.return_value = {
            "The Hobbit": {
                "type": "Movie",
            }
        }

        def tmdb_return_value(mode, _):
            return (
                [
                    {
                        "canonical_title": "The Hobbit: An Unexpected Journey",
                        "type": "Movie",
                        "tags": {"genre": ["Adventure"]},
                        "confidence": 0.9,
                        "source": "tmdb",
                    }
                ]
                if mode == "movie"
                else []
            )

        mock_tmdb.side_effect = tmdb_return_value
        mock_openlibrary.return_value = [
            {
                "canonical_title": "The Hobbit",
                "type": "Book",
                "tags": {"genre": ["Fantasy"]},
                "confidence": 1.0,
                "source": "openlibrary",
            }
        ]
        mock_igdb.return_value = []

        tagged_entries = apply_tagging(hobbit_entry)

    # Check for warnings about close confidence scores
    assert "Multiple API hits with close confidence" not in caplog.text

    # Assert entry is tagged correctly
    assert len(tagged_entries) == 1
    tagged_entry = tagged_entries[0]
    assert tagged_entry["title"] == "The Hobbit"
    assert tagged_entry["action"] == "finished"
    assert tagged_entry["canonical_title"] == "The Hobbit: An Unexpected Journey"
    assert tagged_entry["type"] == "Movie"
    assert tagged_entry["tags"]["genre"] == ["Adventure"]
    assert tagged_entry["confidence"] == 0.9
    assert tagged_entry["source"] == "tmdb"


def test_apply_tagging_with_low_confidence(sample_entries, caplog):
    """Test applying tagging when the top API hit has a low confidence score."""
    # Mock the API calls
    ff7_entry = [entry for entry in sample_entries if entry["title"] == "FF7"]
    with caplog.at_level(logging.WARNING), patch(
        "preprocessing.media_tagger._load_hints", return_value={}
    ), patch("preprocessing.media_tagger.query_tmdb") as mock_tmdb, patch(
        "preprocessing.media_tagger.query_igdb"
    ) as mock_igdb, patch(
        "preprocessing.media_tagger.query_openlibrary"
    ) as mock_openlibrary:
        # Set up mock returns
        mock_tmdb.return_value = []
        mock_openlibrary.return_value = []
        mock_igdb.return_value = [
            {
                "canonical_title": "Final Fantasy VII",
                "type": "Game",
                "tags": {"platform": ["PS1"]},
                "confidence": 0.2,
                "source": "igdb",
            },
        ]

        tagged_entries = apply_tagging(ff7_entry)

    # Check for warnings about close confidence scores
    assert "Low confidence match for entry: {'title': 'FF7'" in caplog.text

    # Assert entry is tagged correctly
    assert len(tagged_entries) == 1
    tagged_entry = tagged_entries[0]
    assert tagged_entry["title"] == "FF7"
    assert tagged_entry["action"] == "started"
    assert tagged_entry["canonical_title"] == "Final Fantasy VII"
    assert tagged_entry["type"] == "Game"
    assert tagged_entry["confidence"] == 0.2
    assert tagged_entry["source"] == "igdb"

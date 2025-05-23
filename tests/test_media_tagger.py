"""Unit tests for the media tagging functionality."""

import logging
from unittest.mock import patch

import pytest

from preprocessing import media_tagger
from preprocessing.media_tagger import apply_tagging


@pytest.fixture(autouse=True)
def reset_query_cache():
    """Reset query cache before each test to ensure consistent state."""
    media_tagger.QUERY_CACHE = {}
    media_tagger.MEDIA_DB_API_CALL_COUNTS = {}
    yield


@pytest.fixture(name="sample_entries")
def fixture_sample_entries():
    """Sample media entries for testing."""
    return [
        {"title": "FF7", "started_dates": ["2023-01-01"], "finished_dates": []},
        {"title": "The Hobbit", "started_dates": [], "finished_dates": ["2023-02-15"]},
        {"title": "Succesion", "started_dates": ["2023-03-10"], "finished_dates": []},
    ]


def test_apply_tagging_with_only_hints(sample_entries, sample_hints):
    """Test applying tagging with only hints and no API hits."""
    with patch(
        "preprocessing.media_tagger.load_hints", return_value=sample_hints
    ), patch("os.path.exists", return_value=True), patch(
        "preprocessing.media_tagger.query_tmdb"
    ), patch(
        "preprocessing.media_tagger.query_igdb"
    ), patch(
        "preprocessing.media_tagger.query_openlibrary"
    ):
        tagged_entries = apply_tagging(sample_entries, "fake_path.yaml")

    # Check the entry that should match a hint
    entry = next(
        entry for entry in tagged_entries if "FF7" == entry["original_titles"][0]
    )
    assert entry["canonical_title"] == "Final Fantasy VII Remake"
    assert "started_dates" in entry
    assert "finished_dates" in entry

    tagged_entry = entry["tagged"]
    assert tagged_entry["type"] == "Game"
    assert tagged_entry["tags"]["platform"] == ["PS5"]
    assert tagged_entry["confidence"] == 0.5
    assert tagged_entry["source"] == "hint"


def test_apply_tagging_with_api_calls(sample_entries):
    """Test applying tagging with API hits."""
    # Mock the API calls
    succession_entry = [
        entry for entry in sample_entries if entry["title"] == "Succesion"
    ]
    with patch("preprocessing.media_tagger.load_hints", return_value={}), patch(
        "preprocessing.media_tagger.query_tmdb"
    ) as mock_tmdb, patch("preprocessing.media_tagger.query_igdb") as mock_igdb, patch(
        "preprocessing.media_tagger.query_openlibrary"
    ) as mock_openlibrary:
        # Set up mock returns
        mock_tmdb.return_value = [
            {
                "canonical_title": "Succession",
                "type": "TV Show",
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
    entry = tagged_entries[0]
    assert entry["canonical_title"] == "Succession"
    assert entry["original_titles"][0] == "Succesion"
    assert "started_dates" in entry
    assert "finished_dates" in entry

    tagged_entry = entry["tagged"]
    assert tagged_entry["type"] == "TV Show"
    assert tagged_entry["tags"]["genre"] == ["Drama"]
    assert tagged_entry["confidence"] == 0.9
    assert tagged_entry["source"] == "tmdb"


def test_apply_tagging_api_failure(sample_entries, caplog):
    """Test applying tagging when API calls fail."""
    # Mock the API calls to fail
    ff7_entry = [entry for entry in sample_entries if entry["title"] == "FF7"]

    with caplog.at_level(logging.WARNING), patch(
        "preprocessing.media_tagger.load_hints", return_value={}
    ), patch("preprocessing.media_tagger.query_tmdb", return_value=[]), patch(
        "preprocessing.media_tagger.query_igdb", return_value=[]
    ), patch(
        "preprocessing.media_tagger.query_openlibrary",
        return_value=[],
    ):
        tagged_entries = apply_tagging(ff7_entry)

    # Check that fallback values are used
    assert "No API hits found for entry: {'title': 'FF7'}" in caplog.text
    assert "Low confidence match for entry: {'title': 'FF7'," in caplog.text
    assert len(tagged_entries) == 1
    for entry in tagged_entries:
        assert entry["canonical_title"] == entry["original_titles"][0]
        tagged_entry = entry["tagged"]
        assert tagged_entry["type"] == "Other / Unknown"
        assert tagged_entry["tags"] == {}
        assert tagged_entry["confidence"] == 0.1
        assert tagged_entry["source"] == "fallback"


def test_apply_tagging_with_api_calls_and_hints(sample_entries):
    """Test applying tagging with API hits and hints."""
    # Mock the API calls
    succession_entry = [entry for entry in sample_entries if entry["title"] == "FF7"]
    with patch("preprocessing.media_tagger.load_hints", return_value={}), patch(
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
    entry = tagged_entries[0]
    assert entry["canonical_title"] == "Final Fantasy VII"
    assert entry["original_titles"][0] == "FF7"
    assert "started_dates" in entry
    assert "finished_dates" in entry

    tagged_entry = entry["tagged"]
    assert tagged_entry["type"] == "Game"
    assert tagged_entry["tags"]["platform"] == ["PS1"]
    assert tagged_entry["confidence"] == 0.9
    assert tagged_entry["source"] == "igdb"


def test_apply_tagging_with_narrow_confidence(sample_entries, caplog):
    """Test applying tagging when multiple top API hits have a close confidence score."""
    # Mock the API calls
    hobbit_entry = [entry for entry in sample_entries if entry["title"] == "The Hobbit"]
    with caplog.at_level(logging.WARNING), patch(
        "preprocessing.media_tagger.load_hints", return_value={}
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
        "Multiple API hits with close confidence for {'title': 'The Hobbit'}"
        in caplog.text
    )

    # Assert entry is tagged correctly
    assert len(tagged_entries) == 1
    entry = tagged_entries[0]
    assert entry["canonical_title"] == "The Hobbit"
    assert entry["original_titles"][0] == "The Hobbit"
    assert "started_dates" in entry
    assert "finished_dates" in entry

    tagged_entry = entry["tagged"]
    assert tagged_entry["type"] == "Book"
    assert tagged_entry["tags"]["genre"] == ["Fantasy"]
    assert tagged_entry["confidence"] == 1.0
    assert tagged_entry["source"] == "openlibrary"


def test_apply_tagging_fix_confidence_with_hint(sample_entries, caplog):
    """Test applying tagging with multiple hits resolved by hints."""
    # Mock the API calls
    hobbit_entry = [entry for entry in sample_entries if entry["title"] == "The Hobbit"]
    with caplog.at_level(logging.WARNING), patch(
        "preprocessing.media_tagger.load_hints"
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
    entry = tagged_entries[0]
    assert entry["canonical_title"] == "The Hobbit: An Unexpected Journey"
    assert entry["original_titles"][0] == "The Hobbit"
    assert "started_dates" in entry
    assert "finished_dates" in entry

    tagged_entry = entry["tagged"]
    assert tagged_entry["type"] == "Movie"
    assert tagged_entry["tags"]["genre"] == ["Adventure"]
    assert tagged_entry["confidence"] == 0.9
    assert tagged_entry["source"] == "tmdb"


def test_apply_tagging_with_low_confidence(sample_entries, caplog):
    """Test applying tagging when the top API hit has a low confidence score."""
    # Mock the API calls
    ff7_entry = [entry for entry in sample_entries if entry["title"] == "FF7"]
    with caplog.at_level(logging.WARNING), patch(
        "preprocessing.media_tagger.load_hints", return_value={}
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
    entry = tagged_entries[0]
    assert entry["canonical_title"] == "Final Fantasy VII"
    assert entry["original_titles"][0] == "FF7"
    assert "started_dates" in entry
    assert "finished_dates" in entry

    tagged_entry = entry["tagged"]
    assert tagged_entry["type"] == "Game"
    assert tagged_entry["confidence"] == 0.2
    assert tagged_entry["source"] == "igdb"


def test_apply_tagging_only_queries_specified_type():
    """
    Test that only the appropriate API is queried when hint specifies the type.
    This minimizes unnecessary API calls and improves performance.
    """
    # Create entries for each media type
    movie_entry = [{"title": "Matrix", "action": "watched", "date": "2023-01-01"}]
    tv_entry = [{"title": "Succession", "action": "watched", "date": "2023-01-01"}]
    game_entry = [{"title": "Elden", "action": "played", "date": "2023-01-01"}]
    book_entry = [{"title": "LOTR", "action": "read", "date": "2023-01-01"}]

    with patch("preprocessing.media_tagger.load_hints") as mock_hints, patch(
        "preprocessing.media_tagger.query_tmdb"
    ) as mock_tmdb, patch("preprocessing.media_tagger.query_igdb") as mock_igdb, patch(
        "preprocessing.media_tagger.query_openlibrary"
    ) as mock_openlibrary:

        def reset_mocks():
            mock_tmdb.reset_mock()
            mock_igdb.reset_mock()
            mock_openlibrary.reset_mock()

        # Test Movie type
        mock_hints.return_value = {"Matrix": {"type": "Movie"}}
        mock_tmdb.return_value = [
            {
                "canonical_title": "The Matrix",
                "type": "Movie",
                "confidence": 0.9,
                "source": "tmdb",
                "tags": {},
            }
        ]

        apply_tagging(movie_entry)

        # Verify only movie API was called
        mock_tmdb.assert_called_once_with("movie", "Matrix")
        mock_igdb.assert_not_called()
        mock_openlibrary.assert_not_called()

        # Test TV type
        reset_mocks()
        mock_hints.return_value = {"Succession": {"type": "TV Show"}}
        mock_tmdb.return_value = [
            {
                "canonical_title": "Succession",
                "type": "TV Show",
                "confidence": 0.9,
                "source": "tmdb",
                "tags": {},
            }
        ]

        apply_tagging(tv_entry)

        # Verify only TV API was called
        mock_tmdb.assert_called_once_with("tv", "Succession")
        mock_igdb.assert_not_called()
        mock_openlibrary.assert_not_called()

        # Test Game type
        reset_mocks()
        mock_hints.return_value = {"Elden": {"type": "Game"}}
        mock_igdb.return_value = [
            {
                "canonical_title": "Elden Ring",
                "type": "Game",
                "confidence": 0.9,
                "source": "igdb",
                "tags": {},
            }
        ]

        apply_tagging(game_entry)

        # Verify only game API was called
        mock_tmdb.assert_not_called()
        mock_igdb.assert_called_once_with("Elden")
        mock_openlibrary.assert_not_called()

        # Test Book type
        reset_mocks()
        mock_hints.return_value = {"LOTR": {"type": "Book"}}
        mock_openlibrary.return_value = [
            {
                "canonical_title": "The Lord of the Rings",
                "type": "Book",
                "confidence": 0.9,
                "source": "openlibrary",
                "tags": {},
            }
        ]

        apply_tagging(book_entry)

        # Verify only book API was called
        mock_tmdb.assert_not_called()
        mock_igdb.assert_not_called()
        mock_openlibrary.assert_called_once_with("LOTR")


def test_use_canonical_title_from_hint():
    """Test that the canonical_title from hint is used when querying APIs."""
    entry = [{"title": "FF7", "action": "played", "date": "2023-01-01"}]

    with patch("preprocessing.media_tagger.load_hints") as mock_hints, patch(
        "preprocessing.media_tagger.query_igdb"
    ) as mock_igdb:
        # Set up mock hint with canonical_title
        mock_hints.return_value = {
            "FF7": {"canonical_title": "Final Fantasy VII Remake", "type": "Game"}
        }
        mock_igdb.return_value = [
            {
                "canonical_title": "Final Fantasy VII Remake",
                "type": "Game",
                "confidence": 0.9,
                "source": "igdb",
                "tags": {"platform": ["PS5"]},
            }
        ]

        apply_tagging(entry)

        # Verify API was called with canonical_title from hint
        mock_igdb.assert_called_once_with("Final Fantasy VII Remake")


def test_season_extraction_in_tagging():
    """Test that season information is correctly extracted and added back to canonical title."""
    # Test cases for different season formats
    expected_title = "Game of Thrones"
    test_cases = [
        {
            "title": "Game of Thrones s1",
            "expected_season": "s1",
        },
        {
            "title": "Game of Thrones s01e02",
            "expected_season": "s01",
        },
        {
            "title": "Game of Thrones s1 e2",
            "expected_season": "s1",
        },
        {
            "title": "Game of Thrones S1E1 ",
            "expected_season": "s1",
        },
    ]

    for test_case in test_cases:
        media_tagger.QUERY_CACHE = {}
        entry = {"title": test_case["title"], "action": "started", "date": "2023-01-01"}

        with patch("preprocessing.media_tagger.load_hints", return_value={}), patch(
            "preprocessing.media_tagger.query_tmdb"
        ) as mock_tmdb:
            # Set up mock return for TV API
            mock_tmdb.return_value = [
                {
                    "canonical_title": "Game of Thrones",
                    "type": "TV Show",
                    "confidence": 0.9,
                    "source": "tmdb",
                    "tags": {"genre": ["Drama", "Fantasy"]},
                }
            ]

            tagged_entries = apply_tagging([entry])

            # Verify season extraction and canonical title
            assert len(tagged_entries) == 1
            tagged_entry = tagged_entries[0]
            assert (
                tagged_entry["canonical_title"]
                == f"Game of Thrones {test_case['expected_season']}"
            )
            assert tagged_entry["tagged"]["type"] == "TV Show"

            # Verify API was called with the title without season information
            mock_tmdb.assert_called_with("tv", expected_title)

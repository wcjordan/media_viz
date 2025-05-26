"""Unit tests for the media tagging functionality."""

import logging
from unittest.mock import patch

import pytest

from preprocessing import media_tagger
from preprocessing.media_tagger import _combine_similar_entries, apply_tagging


@pytest.fixture(autouse=True, name="mock_dependencies")
def fixture_mock_dependencies():
    """Mock dependencies to avoid actual API calls."""
    with patch("preprocessing.media_tagger.load_hints") as mock_load_hints, patch(
        "preprocessing.media_tagger.query_tmdb"
    ) as mock_query_tmdb, patch(
        "preprocessing.media_tagger.query_igdb"
    ) as mock_query_igdb, patch(
        "preprocessing.media_tagger.query_openlibrary"
    ) as mock_query_openlibrary:
        mock_load_hints.side_effect = RuntimeError("Unmocked load_hints attempted")
        mock_query_tmdb.side_effect = RuntimeError("Unmocked query_tmdb attempted")
        mock_query_igdb.side_effect = RuntimeError("Unmocked query_igdb attempted")
        mock_query_openlibrary.side_effect = RuntimeError(
            "Unmocked query_openlibrary attempted"
        )
        yield mock_load_hints, mock_query_tmdb, mock_query_igdb, mock_query_openlibrary


@pytest.fixture(name="reset_dependency_mocks")
def fixture_reset_dependency_mocks(mock_dependencies):
    """Reset dependency mocks to avoid side effects between tests."""

    def _reset_mocks():
        """Reset all mocks to their initial state."""
        mock_load_hints, mock_query_tmdb, mock_query_igdb, mock_query_openlibrary = (
            mock_dependencies
        )
        mock_load_hints.reset_mock()
        mock_query_tmdb.reset_mock()
        mock_query_igdb.reset_mock()
        mock_query_openlibrary.reset_mock()

    return _reset_mocks


@pytest.fixture(name="reset_query_cache")
def fixture_reset_query_cache():
    """Reset query cache."""

    def _reset_query_cache():
        media_tagger.QUERY_CACHE = {}
        media_tagger.MEDIA_DB_API_CALL_COUNTS = {}

    return _reset_query_cache


@pytest.fixture(autouse=True)
def auto_reset_query_cache(reset_query_cache):
    """Reset query cache before each test to ensure consistent state."""
    reset_query_cache()


@pytest.fixture(name="setup_hints_mock")
def fixture_setup_hints_mock(mock_dependencies):
    """Setup mock for hints loading."""
    mock_load_hints, _, _, _ = mock_dependencies

    def _setup_hints_mock(hints=None):
        mock_load_hints.return_value = hints or {}
        mock_load_hints.side_effect = None
        return mock_load_hints

    return _setup_hints_mock


@pytest.fixture(name="sample_entries")
def fixture_sample_entries():
    """Sample media entries for testing."""
    return [
        {"title": "FF7", "started_dates": ["2023-01-01"], "finished_dates": []},
        {"title": "The Hobbit", "started_dates": [], "finished_dates": ["2023-02-15"]},
        {"title": "Succession", "started_dates": ["2023-03-10"], "finished_dates": []},
        {"title": "The Hobbit", "started_dates": ["2023-04-18"], "finished_dates": []},
    ]


@pytest.fixture(name="mock_api_responses")
def fixture_mock_api_responses():
    """Mock API responses for different media types."""
    return {
        "movie": {
            "The Hobbit": [
                {
                    "canonical_title": "The Hobbit: An Unexpected Journey",
                    "type": "Movie",
                    "tags": {"genre": ["Adventure"]},
                    "confidence": 0.9,
                    "source": "tmdb",
                }
            ],
        },
        "tv": {
            "Succession": [
                {
                    "canonical_title": "Succession",
                    "type": "TV Show",
                    "tags": {"genre": ["Drama"]},
                    "confidence": 0.9,
                    "source": "tmdb",
                }
            ],
        },
        "game": {
            "FF7": [
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
            ],
        },
        "book": {
            "The Hobbit": [
                {
                    "canonical_title": "The Hobbit",
                    "type": "Book",
                    "tags": {"genre": ["Fantasy"]},
                    "confidence": 1.0,
                    "source": "openlibrary",
                }
            ],
        },
    }


@pytest.fixture(name="setup_api_mocks")
def fixture_setup_api_mocks(mock_dependencies, mock_api_responses):
    """Setup mocks for API calls in media tagger tests."""

    def _setup_mocks(
        movie_response=None, tv_response=None, game_response=None, book_response=None
    ):
        _, mock_tmdb, mock_igdb, mock_openlibrary = mock_dependencies
        if (
            movie_response is None
            and tv_response is None
            and game_response is None
            and book_response is None
        ):
            movie_response = mock_api_responses["movie"]
            tv_response = mock_api_responses["tv"]
            game_response = mock_api_responses["game"]
            book_response = mock_api_responses["book"]

        # Configure mock returns based on parameters or use empty lists as default
        def tmdb_side_effect(mode, title):
            if mode == "movie" and movie_response is not None:
                if isinstance(movie_response, list):
                    return movie_response
                return movie_response.get(title, [])
            if mode == "tv" and tv_response is not None:
                if isinstance(tv_response, list):
                    return tv_response
                return tv_response.get(title, [])
            return []

        mock_tmdb.side_effect = tmdb_side_effect

        def igdb_side_effect(title):
            if game_response is not None:
                if isinstance(game_response, list):
                    return game_response
                return game_response.get(title, [])
            return []

        mock_igdb.side_effect = igdb_side_effect

        def openlibrary_side_effect(title):
            if book_response is not None:
                if isinstance(book_response, list):
                    return book_response
                return book_response.get(title, [])
            return []

        mock_openlibrary.side_effect = openlibrary_side_effect

        return mock_tmdb, mock_igdb, mock_openlibrary

    return _setup_mocks


def test_apply_tagging_with_only_hints(
    sample_entries, sample_hints, setup_api_mocks, setup_hints_mock
):
    """Test applying tagging with only hints and no API hits."""
    setup_hints_mock(sample_hints)
    setup_api_mocks(
        movie_response=[], tv_response=[], game_response=[], book_response=[]
    )

    tagged_entries = apply_tagging(sample_entries)

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


def test_apply_tagging_with_release_year_hint(
    caplog, setup_api_mocks, setup_hints_mock
):
    """Test applying tagging with release_year in the hint."""
    # Setup a hint with release_year
    setup_hints_mock(
        {
            "Sapiens": {
                "type": "Book",
                "release_year": "2011"
            }
        }
    )
    
    # Mock the API calls
    mock_tmdb, mock_igdb, mock_openlibrary = setup_api_mocks()
    
    # Create a test entry
    entry = {"title": "Sapiens", "started_dates": ["2023-01-01"], "finished_dates": []}
    
    # Apply tagging
    apply_tagging([entry])
    
    # Verify that the release_year was passed to the OpenLibrary API
    mock_openlibrary.assert_called_once()
    assert "2011" in str(mock_openlibrary.call_args)
    
    # Verify that other APIs were not called since the hint specified Book type
    mock_tmdb.assert_not_called()
    mock_igdb.assert_not_called()


def test_apply_tagging_with_api_calls(
    sample_entries, setup_api_mocks, setup_hints_mock
):
    """Test applying tagging with API hits."""
    # Mock the API calls
    setup_hints_mock()
    setup_api_mocks()

    succession_entry = [
        entry for entry in sample_entries if entry["title"] == "Succession"
    ]
    tagged_entries = apply_tagging(succession_entry)

    # Assert entry is tagged correctly
    assert len(tagged_entries) == 1
    entry = tagged_entries[0]
    assert entry["canonical_title"] == "Succession"
    assert entry["original_titles"][0] == "Succession"
    assert "started_dates" in entry
    assert "finished_dates" in entry

    tagged_entry = entry["tagged"]
    assert tagged_entry["type"] == "TV Show"
    assert tagged_entry["tags"]["genre"] == ["Drama"]
    assert tagged_entry["confidence"] == 0.9
    assert tagged_entry["source"] == "tmdb"


def test_apply_tagging_api_failure(
    sample_entries, caplog, setup_api_mocks, setup_hints_mock
):
    """Test applying tagging when API calls fail."""
    # Mock the API calls to fail
    setup_hints_mock()
    setup_api_mocks(
        movie_response=[], tv_response=[], game_response=[], book_response=[]
    )

    ff7_entry = [entry for entry in sample_entries if entry["title"] == "FF7"]
    with caplog.at_level(logging.WARNING):
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


def test_apply_tagging_with_api_calls_and_hints(
    mock_api_responses, sample_entries, setup_api_mocks, setup_hints_mock
):
    """Test applying tagging with API hits and hints."""
    # Mock the API calls
    setup_hints_mock()
    setup_api_mocks(
        movie_response=[
            {
                "canonical_title": "Final Fantasy VII: Advent Children",
                "type": "Movie",
                "tags": {"genre": ["Animation"]},
                "confidence": 0.7,
                "source": "tmdb",
            }
        ],
        game_response=mock_api_responses["game"]["FF7"],
    )

    ff7_entry = [entry for entry in sample_entries if entry["title"] == "FF7"]
    tagged_entries = apply_tagging(ff7_entry)

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


def test_apply_tagging_with_narrow_confidence(
    caplog, sample_entries, setup_api_mocks, setup_hints_mock
):
    """Test applying tagging when multiple top API hits have a close confidence score."""
    # Mock the API calls
    setup_api_mocks()
    setup_hints_mock()

    hobbit_entry = [
        entry for entry in sample_entries if entry["title"] == "The Hobbit"
    ][:1]
    with caplog.at_level(logging.WARNING):
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


def test_apply_tagging_fix_confidence_with_hint(
    caplog, sample_entries, setup_api_mocks, setup_hints_mock
):
    """Test applying tagging with multiple hits resolved by hints."""
    # Mock the API calls
    setup_api_mocks()
    setup_hints_mock(
        {
            "The Hobbit": {
                "type": "Movie",
            }
        }
    )

    hobbit_entry = [
        entry for entry in sample_entries if entry["title"] == "The Hobbit"
    ][:1]
    with caplog.at_level(logging.WARNING):
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


def test_apply_tagging_with_low_confidence(
    caplog, sample_entries, mock_api_responses, setup_api_mocks, setup_hints_mock
):
    """Test applying tagging when the top API hit has a low confidence score."""
    # Mock the API calls
    setup_hints_mock()

    low_confidence_response = mock_api_responses["game"]["FF7"][0]
    low_confidence_response["confidence"] = 0.2
    setup_api_mocks(game_response=[low_confidence_response])

    ff7_entry = [entry for entry in sample_entries if entry["title"] == "FF7"]
    with caplog.at_level(logging.WARNING):
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


def test_apply_tagging_only_queries_specified_type(
    sample_entries, setup_hints_mock, setup_api_mocks, reset_dependency_mocks
):
    """
    Test that only the appropriate API is queried when hint specifies the type.
    This minimizes unnecessary API calls and improves performance.
    """
    # Create entries for each media type
    movie_entries = [
        entry for entry in sample_entries if entry["title"] == "The Hobbit"
    ][:1]
    tv_entries = [entry for entry in sample_entries if entry["title"] == "Succession"]
    game_entries = [entry for entry in sample_entries if entry["title"] == "FF7"]
    book_entries = [
        entry for entry in sample_entries if entry["title"] == "The Hobbit"
    ][1:]

    mock_tmdb, mock_igdb, mock_openlibrary = setup_api_mocks()

    # Test Movie type
    setup_hints_mock({"The Hobbit": {"type": "Movie"}})
    apply_tagging(movie_entries)

    # Verify only movie API was called
    mock_tmdb.assert_called_once_with("movie", "The Hobbit")
    mock_igdb.assert_not_called()
    mock_openlibrary.assert_not_called()

    # Test TV type
    reset_dependency_mocks()
    setup_hints_mock({"Succession": {"type": "TV Show"}})
    apply_tagging(tv_entries)

    # Verify only TV API was called
    mock_tmdb.assert_called_once_with("tv", "Succession")
    mock_igdb.assert_not_called()
    mock_openlibrary.assert_not_called()

    # Test Game type
    reset_dependency_mocks()
    setup_hints_mock({"FF7": {"type": "Game"}})
    apply_tagging(game_entries)

    # Verify only game API was called
    mock_tmdb.assert_not_called()
    mock_igdb.assert_called_once_with("FF7")
    mock_openlibrary.assert_not_called()

    # Test Book type
    reset_dependency_mocks()
    setup_hints_mock({"The Hobbit": {"type": "Book"}})
    apply_tagging(book_entries)

    # Verify only book API was called
    mock_tmdb.assert_not_called()
    mock_igdb.assert_not_called()
    mock_openlibrary.assert_called_once_with("The Hobbit")


def test_use_canonical_title_from_hint(
    sample_entries, mock_api_responses, setup_hints_mock, setup_api_mocks
):
    """Test that the canonical_title from hint is used when querying APIs."""
    _, mock_igdb, _ = setup_api_mocks(
        game_response=[
            mock_api_responses["game"]["FF7"][1],
        ]
    )

    # Set up mock hint with canonical_title
    setup_hints_mock(
        {"FF7": {"canonical_title": "Final Fantasy VII Remake", "type": "Game"}}
    )

    ff7_entry = [entry for entry in sample_entries if entry["title"] == "FF7"]
    apply_tagging(ff7_entry)

    # Verify API was called with canonical_title from hint
    mock_igdb.assert_called_once_with("Final Fantasy VII Remake")


def test_season_extraction_in_tagging(
    mock_api_responses,
    setup_hints_mock,
    setup_api_mocks,
    reset_dependency_mocks,
    reset_query_cache,
):
    """Test that season information is correctly extracted and added back to canonical title."""
    # Test cases for different season formats
    expected_title = "Succession"
    test_cases = [
        {
            "title": "Succession s1",
            "expected_season": "s1",
        },
        {
            "title": "Succession s01e02",
            "expected_season": "s01",
        },
        {
            "title": "Succession s1 e2",
            "expected_season": "s1",
        },
        {
            "title": "Succession S1E1 ",
            "expected_season": "s1",
        },
    ]

    for test_case in test_cases:
        reset_query_cache()
        reset_dependency_mocks()
        entry = {"title": test_case["title"], "action": "started", "date": "2023-01-01"}

        setup_hints_mock()
        mock_tmdb, _, _ = setup_api_mocks(
            tv_response=mock_api_responses["tv"]["Succession"],
        )

        tagged_entries = apply_tagging([entry])

        # Verify season extraction and canonical title
        assert len(tagged_entries) == 1
        tagged_entry = tagged_entries[0]
        assert (
            tagged_entry["canonical_title"]
            == f"Succession {test_case['expected_season']}"
        )
        assert tagged_entry["tagged"]["type"] == "TV Show"

        # Verify API was called with the title without season information
        mock_tmdb.assert_called_once_with("tv", expected_title)


def test_combine_similar_entries():
    """Test the _combine_similar_entries function that combines entries with the same canonical title."""
    # Test with multiple entries for the same canonical title
    tagged_entries = [
        {
            "title": "FF7",
            "tagged": {
                "canonical_title": "Final Fantasy VII",
                "type": "Game",
                "tags": {"platform": ["PS1"]},
                "confidence": 0.9,
                "source": "igdb",
            },
            "started_dates": ["2023-01-01"],
            "finished_dates": [],
        },
        {
            "title": "Final Fantasy 7",
            "tagged": {
                "canonical_title": "Final Fantasy VII",
                "type": "Game",
                "tags": {"platform": ["PS1"]},
                "confidence": 0.85,
                "source": "igdb",
            },
            "started_dates": [],
            "finished_dates": ["2023-02-01"],
        },
        {
            "title": "The Hobbit",
            "tagged": {
                "canonical_title": "The Hobbit",
                "type": "Book",
                "tags": {"genre": ["Fantasy"]},
                "confidence": 0.95,
                "source": "openlibrary",
            },
            "started_dates": ["2023-03-01"],
            "finished_dates": ["2023-04-01"],
        },
    ]

    combined = _combine_similar_entries(tagged_entries)

    # Should have 2 entries (one for each unique canonical title + type)
    assert len(combined) == 2

    # Find Final Fantasy VII entry
    ff7_entry = next(
        entry for entry in combined if entry["canonical_title"] == "Final Fantasy VII"
    )
    assert sorted(ff7_entry["original_titles"]) == sorted(["FF7", "Final Fantasy 7"])
    assert ff7_entry["started_dates"] == ["2023-01-01"]
    assert ff7_entry["finished_dates"] == ["2023-02-01"]
    assert ff7_entry["tagged"]["type"] == "Game"

    # Find The Hobbit entry
    hobbit_entry = next(
        entry for entry in combined if entry["canonical_title"] == "The Hobbit"
    )
    assert hobbit_entry["original_titles"] == ["The Hobbit"]
    assert hobbit_entry["started_dates"] == ["2023-03-01"]
    assert hobbit_entry["finished_dates"] == ["2023-04-01"]
    assert hobbit_entry["tagged"]["type"] == "Book"


def test_combine_similar_entries_edge_cases(caplog):
    """Test edge cases for the _combine_similar_entries function."""
    # Test with empty list
    assert not _combine_similar_entries([])

    # Test with inconsistent tags
    inconsistent_tags = [
        {
            "title": "FF7",
            "tagged": {
                "canonical_title": "Final Fantasy VII",
                "type": "Game",
                "tags": {"platform": ["PS1"]},
                "confidence": 0.9,
                "source": "igdb",
                "poster_path": "path1.jpg",
            },
            "started_dates": ["2023-01-01"],
            "finished_dates": [],
        },
        {
            "title": "Final Fantasy 7",
            "tagged": {
                "canonical_title": "Final Fantasy VII",
                "type": "Game",
                "tags": {"platform": ["PS5"]},  # Different platform
                "confidence": 0.8,  # Different confidence
                "source": "hint",  # Different source
                "poster_path": "path2.jpg",  # Different poster
            },
            "started_dates": [],
            "finished_dates": ["2023-02-01"],
        },
    ]

    with caplog.at_level(logging.WARNING):
        combined = _combine_similar_entries(inconsistent_tags)

    # Should still combine but log warnings
    assert len(combined) == 1
    assert "Inconsistent tags" in caplog.text
    assert "Inconsistent poster_path" in caplog.text
    assert "Inconsistent confidence" in caplog.text
    assert "Inconsistent source" in caplog.text

    # The first entry's values should be preserved
    ff7_entry = combined[0]
    assert ff7_entry["tagged"]["tags"]["platform"] == ["PS1"]
    assert ff7_entry["tagged"]["confidence"] == 0.9
    assert ff7_entry["tagged"]["source"] == "igdb"
    assert ff7_entry["tagged"]["poster_path"] == "path1.jpg"

    # Dates should be combined
    assert ff7_entry["started_dates"] == ["2023-01-01"]
    assert ff7_entry["finished_dates"] == ["2023-02-01"]

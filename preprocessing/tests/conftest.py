"""Common test fixtures"""

import pytest


@pytest.fixture()
def sample_hints():
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
        "The Hobbit": {
            "canonical_title": "The Hobbit",
            "type": "Book",
            "tags": {
                "genre": ["Fantasy"],
                "mood": ["Epic"],
            },
        },
    }


@pytest.fixture()
def sample_multi_match_hints():
    """Sample multi-match hints data for testing."""
    return {
        "Fargo": [
            {"canonical_title": "Fargo", "type": "Movie", "dates": ["2021-02-03"]},
            {
                "canonical_title": "Fargo",
                "type": "TV Show",
                "dates": ["2023-10-23"],
            },
        ]
    }

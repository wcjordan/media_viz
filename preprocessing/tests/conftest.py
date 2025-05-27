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

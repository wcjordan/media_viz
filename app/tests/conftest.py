"""
Common fixtures for testing the media viz application
"""

import pytest


@pytest.fixture()
def sample_entries():
    """Fixture to provide sample media entries."""
    return [
        {
            "title": "Test Movie",
            "started_dates": ["2021-02-01"],
            "finished_dates": ["2021-02-08"],
            "tagged": {
                "canonical_title": "Test Movie",
                "type": "Movie",
                "tags": {
                    "genre": ["Action"],
                    "platform": ["Theater"],
                    "mood": ["Exciting"],
                },
                "confidence": 0.95,
            },
        },
        {
            "title": "In Progress Game",
            "started_dates": ["2021-07-01"],
            "finished_dates": [],
            "tagged": {
                "canonical_title": "In Progress Game",
                "type": "Game",
                "tags": {"genre": ["RPG"], "platform": ["PC"], "mood": ["Exciting"]},
                "confidence": 0.9,
            },
        },
        {
            "title": "Finished Book",
            "started_dates": [],
            "finished_dates": ["2021-08-15"],
            "tagged": {
                "canonical_title": "Finished Book",
                "type": "Book",
                "tags": {
                    "genre": ["Fiction"],
                    "platform": ["Kindle"],
                    "mood": ["Thoughtful"],
                },
                "confidence": 0.85,
            },
        },
        {
            "title": "Long TV Show",
            "started_dates": ["2021-10-01"],
            "finished_dates": ["2021-10-08"],
            "tagged": {
                "canonical_title": "Long TV Show",
                "type": "TV",
                "tags": {
                    "genre": ["Drama"],
                    "platform": ["Netflix"],
                    "mood": ["Intense"],
                },
                "confidence": 0.95,
            },
        },
    ]

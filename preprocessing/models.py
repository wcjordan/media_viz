"""
Pydantic models for media entries.
"""

from typing import Annotated, List, Optional
from datetime import date
from pydantic import BaseModel, Field


class MediaTags(BaseModel):
    """Tags for a media entry."""

    author: Annotated[Optional[List[str]], Field(default=None)]
    genre: Annotated[Optional[List[str]], Field(default=None)]
    platform: Annotated[Optional[List[str]], Field(default=None)]
    release_year: Optional[int]


class TaggedEntry(BaseModel):
    """Tagged metadata for a media entry."""

    canonical_title: str
    type: str
    tags: Annotated[MediaTags, Field(default_factory=lambda: MediaTags(release_year=0))]
    confidence: float
    source: str
    poster_path: Optional[str] = None


class MediaEntry(BaseModel):
    """
    A media entry representing a book, movie, TV show, or game.
    """

    canonical_title: str
    original_titles: List[str]
    tagged: TaggedEntry
    started_dates: List[Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]] = Field(
        default_factory=list
    )
    finished_dates: List[Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]] = Field(
        default_factory=list
    )

    @property
    def duration_days(self) -> Optional[int]:
        """Calculate the duration in days if both start and finish dates are available."""
        if self.started_dates and self.finished_dates:
            start = date.fromisoformat(min(self.started_dates))
            finish = date.fromisoformat(max(self.finished_dates))
            return (finish - start).days
        return None

    @property
    def status(self) -> str:
        """Determine the status of the media entry."""
        if self.started_dates and self.finished_dates:
            return "completed"
        if self.started_dates:
            return "in_progress"
        if self.finished_dates:
            return "finished_only"
        return "unknown"

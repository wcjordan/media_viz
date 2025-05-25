"""
Pydantic models for media entries.
"""

from typing import Dict, List, Optional, Union
from datetime import date
from pydantic import BaseModel, Field, validator


class MediaTags(BaseModel):
    """Tags for a media entry."""
    genre: Optional[List[str]] = Field(default_factory=list)
    platform: Optional[List[str]] = Field(default_factory=list)
    mood: Optional[List[str]] = Field(default_factory=list)


class TaggedEntry(BaseModel):
    """Tagged metadata for a media entry."""
    canonical_title: str
    type: str
    tags: MediaTags = Field(default_factory=MediaTags)
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
    started_dates: List[str] = Field(default_factory=list)
    finished_dates: List[str] = Field(default_factory=list)
    
    @validator('started_dates', 'finished_dates', each_item=True)
    def validate_date_format(cls, v):
        """Validate that dates are in ISO format (YYYY-MM-DD)."""
        try:
            date.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError(f"Date {v} is not in ISO format (YYYY-MM-DD)")
    
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
        elif self.started_dates:
            return "in_progress"
        elif self.finished_dates:
            return "finished_only"
        return "unknown"

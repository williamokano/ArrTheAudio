"""Media metadata models."""

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class MediaMetadata:
    """Represents metadata about a media file."""

    original_language: Optional[str] = None  # ISO 639-2 language code
    source: Literal["sonarr", "radarr", "tmdb", "heuristic", "none"] = "none"
    media_type: Optional[Literal["tv", "movie"]] = None  # Media type
    title: Optional[str] = None  # Media title
    year: Optional[int] = None  # Release year
    tmdb_id: Optional[int] = None  # TMDB ID
    tvdb_id: Optional[int] = None  # TVDB ID (for TV shows)

    def __str__(self) -> str:
        """Human-readable representation."""
        if self.title:
            year_part = f" ({self.year})" if self.year else ""
            lang_part = f" [Original: {self.original_language}]" if self.original_language else ""
            return f"{self.title}{year_part}{lang_part} (source: {self.source})"
        return f"Unknown media (source: {self.source})"

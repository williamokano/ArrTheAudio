"""Pydantic models for API requests and responses."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# Nested models for Sonarr webhook
class SonarrSeries(BaseModel):
    """Sonarr series information."""

    id: int
    title: str
    tvdbId: Optional[int] = None
    imdbId: Optional[str] = None


class SonarrEpisode(BaseModel):
    """Sonarr episode information."""

    id: int
    seasonNumber: int
    episodeNumber: int


class SonarrEpisodeFile(BaseModel):
    """Sonarr episode file information."""

    id: int
    path: str


class SonarrWebhookPayload(BaseModel):
    """Sonarr webhook payload model."""

    eventType: str = Field(..., alias="eventType")
    series: SonarrSeries
    episodes: Optional[List[SonarrEpisode]] = None
    episodeFile: Optional[SonarrEpisodeFile] = None

    @property
    def event_type(self) -> str:
        """Get event type (snake_case property)."""
        return self.eventType

    @property
    def series_title(self) -> Optional[str]:
        """Get series title."""
        return self.series.title if self.series else None

    @property
    def series_tvdb_id(self) -> Optional[int]:
        """Get TVDB ID."""
        return self.series.tvdbId if self.series else None

    @property
    def episode_file_path(self) -> Optional[str]:
        """Get episode file path."""
        return self.episodeFile.path if self.episodeFile else None

    class Config:
        populate_by_name = True


# Nested models for Radarr webhook
class RadarrMovie(BaseModel):
    """Radarr movie information."""

    id: int
    title: str
    year: Optional[int] = None
    tmdbId: Optional[int] = None
    imdbId: Optional[str] = None


class RadarrMovieFile(BaseModel):
    """Radarr movie file information."""

    id: int
    relativePath: str


class RadarrWebhookPayload(BaseModel):
    """Radarr webhook payload model."""

    eventType: str = Field(..., alias="eventType")
    movie: RadarrMovie
    movieFile: Optional[RadarrMovieFile] = None

    @property
    def event_type(self) -> str:
        """Get event type (snake_case property)."""
        return self.eventType

    @property
    def movie_title(self) -> Optional[str]:
        """Get movie title."""
        return self.movie.title if self.movie else None

    @property
    def movie_tmdb_id(self) -> Optional[int]:
        """Get TMDB ID."""
        return self.movie.tmdbId if self.movie else None

    @property
    def movie_file_path(self) -> Optional[str]:
        """Get movie file path."""
        return self.movieFile.relativePath if self.movieFile else None

    class Config:
        populate_by_name = True


class WebhookResponse(BaseModel):
    """Webhook response model."""

    status: Literal["accepted", "rejected"]
    job_id: Optional[str] = None
    message: Optional[str] = None


class BatchRequest(BaseModel):
    """Batch processing request model."""

    path: str = Field(..., description="Path to scan")
    recursive: bool = Field(True, description="Scan recursively")
    dry_run: bool = Field(False, description="Dry run mode")


class BatchResponse(BaseModel):
    """Batch processing response model."""

    status: Literal["started", "rejected"]
    batch_id: Optional[str] = None
    estimated_files: Optional[int] = None
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response model."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    queue_size: int
    uptime_seconds: float
    checks: dict[str, bool] = Field(default_factory=dict)

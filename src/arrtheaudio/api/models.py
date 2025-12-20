"""Pydantic models for API requests and responses."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# Nested models for Sonarr webhook
class SonarrLanguage(BaseModel):
    """Sonarr language information."""

    id: int
    name: str


class SonarrSeries(BaseModel):
    """Sonarr series information."""

    id: int
    title: str
    tvdbId: Optional[int] = None
    tmdbId: Optional[int] = None
    imdbId: Optional[str] = None
    originalLanguage: Optional[SonarrLanguage] = None


class SonarrEpisode(BaseModel):
    """Sonarr episode information."""

    id: int
    seasonNumber: int
    episodeNumber: int
    title: Optional[str] = None


class SonarrMediaInfo(BaseModel):
    """Sonarr media info."""

    audioLanguages: Optional[List[str]] = None
    subtitles: Optional[List[str]] = None


class SonarrEpisodeFile(BaseModel):
    """Sonarr episode file information."""

    id: int
    path: str
    relativePath: Optional[str] = None
    quality: Optional[str] = None
    languages: Optional[List[SonarrLanguage]] = None
    mediaInfo: Optional[SonarrMediaInfo] = None


class SonarrWebhookPayload(BaseModel):
    """Sonarr webhook payload model."""

    eventType: str = Field(..., alias="eventType")
    series: SonarrSeries
    episodes: Optional[List[SonarrEpisode]] = None
    episodeFiles: Optional[List[SonarrEpisodeFile]] = None  # Note: plural!
    sourcePath: Optional[str] = None
    destinationPath: Optional[str] = None

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
    def series_tmdb_id(self) -> Optional[int]:
        """Get TMDB ID."""
        return self.series.tmdbId if self.series else None

    @property
    def episode_file_path(self) -> Optional[str]:
        """Get episode file path (from first file in array)."""
        if self.episodeFiles and len(self.episodeFiles) > 0:
            return self.episodeFiles[0].path
        return None

    @property
    def original_language(self) -> Optional[str]:
        """Get original language name from series."""
        if self.series and self.series.originalLanguage:
            return self.series.originalLanguage.name
        return None

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
    originalLanguage: Optional[SonarrLanguage] = None  # Radarr v4 provides this


class RadarrMediaInfo(BaseModel):
    """Radarr media info."""

    audioLanguages: Optional[List[str]] = None
    subtitles: Optional[List[str]] = None


class RadarrMovieFile(BaseModel):
    """Radarr movie file information."""

    id: int
    path: str
    relativePath: Optional[str] = None
    quality: Optional[str] = None
    languages: Optional[List[SonarrLanguage]] = None
    mediaInfo: Optional[RadarrMediaInfo] = None


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
        return self.movieFile.path if self.movieFile else None

    @property
    def original_language(self) -> Optional[str]:
        """Get original language name from movie."""
        if self.movie and self.movie.originalLanguage:
            return self.movie.originalLanguage.name
        return None

    class Config:
        populate_by_name = True


class WebhookResponse(BaseModel):
    """Webhook response model (Phase 5: Multiple jobs support)."""

    status: Literal["accepted", "rejected"]
    webhook_id: Optional[str] = None  # Links all jobs from this webhook
    job_ids: List[str] = Field(default_factory=list)  # All created job IDs
    files_queued: int = 0  # Number of files queued
    message: Optional[str] = None


class BatchRequest(BaseModel):
    """Batch processing request model."""

    path: str = Field(..., description="Path to scan")
    recursive: bool = Field(True, description="Scan recursively")
    pattern: str = Field("**/*.{mkv,mp4}", description="File pattern")
    dry_run: bool = Field(False, description="Dry run mode")
    priority: str = Field("normal", description="Job priority (high, normal, low)")


class BatchResponse(BaseModel):
    """Batch processing response model."""

    status: Literal["started", "rejected"]
    batch_id: Optional[str] = None
    total_files: int = 0
    job_ids: List[str] = Field(default_factory=list)
    message: Optional[str] = None


class JobResponse(BaseModel):
    """Job response model."""

    job_id: str
    file_path: str
    status: str
    priority: str
    source: str
    container: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    success: Optional[bool] = None
    error_message: Optional[str] = None
    selected_track_index: Optional[int] = None
    selected_track_language: Optional[str] = None
    webhook_id: Optional[str] = None
    batch_id: Optional[str] = None


class QueueResponse(BaseModel):
    """Queue status response model."""

    total_jobs: int
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int
    workers_active: int
    workers_total: int


class WebhookJobsResponse(BaseModel):
    """Webhook jobs response model."""

    webhook_id: str
    source: str
    total_jobs: int
    jobs: List[JobResponse]
    all_completed: bool
    any_failed: bool


class StatsResponse(BaseModel):
    """Statistics response model."""

    queue_stats: QueueResponse
    worker_stats: dict
    uptime_seconds: Optional[float] = None


class HealthResponse(BaseModel):
    """Health check response model."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    queue_size: int
    uptime_seconds: float
    checks: dict[str, bool] = Field(default_factory=dict)

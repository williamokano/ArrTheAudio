"""Pydantic models for API requests and responses."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class SonarrWebhookPayload(BaseModel):
    """Sonarr webhook payload model."""

    series_title: Optional[str] = Field(None, alias="series.title")
    series_id: Optional[int] = Field(None, alias="series.id")
    series_tvdb_id: Optional[int] = Field(None, alias="series.tvdbId")
    episode_file_path: Optional[str] = Field(None, alias="episodeFile.path")
    episode_file_id: Optional[int] = Field(None, alias="episodeFile.id")
    event_type: Optional[str] = Field(None, alias="eventType")

    class Config:
        populate_by_name = True  # Allow both alias and field name


class RadarrWebhookPayload(BaseModel):
    """Radarr webhook payload model."""

    movie_title: Optional[str] = Field(None, alias="movie.title")
    movie_id: Optional[int] = Field(None, alias="movie.id")
    movie_tmdb_id: Optional[int] = Field(None, alias="movie.tmdbId")
    movie_file_path: Optional[str] = Field(None, alias="movieFile.path")
    movie_file_id: Optional[int] = Field(None, alias="movieFile.id")
    event_type: Optional[str] = Field(None, alias="eventType")

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

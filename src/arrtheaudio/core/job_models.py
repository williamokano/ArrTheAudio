"""Job models for queue system."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


class JobStatus(str, Enum):
    """Job status enum."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    """Job priority enum."""

    HIGH = "high"  # Webhooks
    NORMAL = "normal"  # Manual batches
    LOW = "low"  # Retries


class JobSource(str, Enum):
    """Job source enum."""

    SONARR = "sonarr"
    RADARR = "radarr"
    MANUAL = "manual"
    RETRY = "retry"


class Job(BaseModel):
    """Job model for processing a single file."""

    model_config = ConfigDict(use_enum_values=True)

    job_id: str = Field(default_factory=lambda: f"job_{uuid4().hex[:12]}")
    file_path: str = Field(..., description="Absolute path to file")
    container: str = Field(..., description="Container type (mkv, mp4)")
    status: JobStatus = Field(default=JobStatus.QUEUED)
    priority: JobPriority = Field(default=JobPriority.NORMAL)
    source: JobSource = Field(..., description="Where job originated")

    # Linking fields
    webhook_id: Optional[str] = Field(
        default=None, description="Links jobs from same webhook"
    )
    batch_id: Optional[str] = Field(
        default=None, description="Links jobs from same batch"
    )

    # Processing metadata
    selected_track_index: Optional[int] = Field(
        default=None, description="Audio track index to set as default"
    )
    selected_track_language: Optional[str] = Field(
        default=None, description="Language of selected track"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    # Result tracking
    success: Optional[bool] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    retry_count: int = Field(default=0)

    # TMDB metadata (optional)
    tmdb_id: Optional[int] = Field(default=None)
    original_language: Optional[str] = Field(default=None)
    series_title: Optional[str] = Field(default=None)
    movie_title: Optional[str] = Field(default=None)

    def to_db_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "job_id": self.job_id,
            "file_path": self.file_path,
            "container": self.container,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "priority": (
                self.priority.value if isinstance(self.priority, Enum) else self.priority
            ),
            "source": self.source.value if isinstance(self.source, Enum) else self.source,
            "webhook_id": self.webhook_id,
            "batch_id": self.batch_id,
            "selected_track_index": self.selected_track_index,
            "selected_track_language": self.selected_track_language,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "tmdb_id": self.tmdb_id,
            "original_language": self.original_language,
            "series_title": self.series_title,
            "movie_title": self.movie_title,
        }

    @classmethod
    def from_db_dict(cls, data: dict) -> "Job":
        """Create Job from database dictionary."""
        # Convert ISO format strings back to datetime
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])

        return cls(**data)


class BatchRequest(BaseModel):
    """Request model for batch processing."""

    path: str = Field(..., description="Directory path to scan")
    recursive: bool = Field(default=True, description="Scan subdirectories")
    pattern: str = Field(default="**/*.{mkv,mp4}", description="File pattern")
    dry_run: bool = Field(default=False, description="Preview without processing")
    priority: JobPriority = Field(
        default=JobPriority.NORMAL, description="Job priority"
    )


class BatchResponse(BaseModel):
    """Response model for batch processing."""

    batch_id: str
    status: str
    message: str
    total_files: int
    job_ids: list[str]


class JobResponse(BaseModel):
    """Response model for single job."""

    job_id: str
    file_path: str
    status: JobStatus
    priority: JobPriority
    source: JobSource
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    success: Optional[bool] = None
    error_message: Optional[str] = None
    selected_track_index: Optional[int] = None
    selected_track_language: Optional[str] = None


class QueueResponse(BaseModel):
    """Response model for queue status."""

    total_jobs: int
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int
    workers_active: int
    workers_total: int


class WebhookJobsResponse(BaseModel):
    """Response model for webhook jobs."""

    webhook_id: str
    source: str
    total_jobs: int
    jobs: list[JobResponse]
    all_completed: bool
    any_failed: bool

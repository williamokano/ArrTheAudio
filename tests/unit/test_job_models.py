"""Unit tests for job models."""

from datetime import datetime
from arrtheaudio.core.job_models import (
    Job,
    JobStatus,
    JobPriority,
    JobSource,
    BatchRequest,
)


class TestJobModel:
    """Test Job model."""

    def test_job_creation_with_defaults(self):
        """Test creating a job with default values."""
        job = Job(
            file_path="/media/test.mkv",
            container="mkv",
            source=JobSource.MANUAL,
        )

        assert job.job_id.startswith("job_")
        assert job.file_path == "/media/test.mkv"
        assert job.container == "mkv"
        assert job.status == JobStatus.QUEUED
        assert job.priority == JobPriority.NORMAL
        assert job.source == JobSource.MANUAL
        assert job.webhook_id is None
        assert job.batch_id is None
        assert isinstance(job.created_at, datetime)
        assert job.started_at is None
        assert job.completed_at is None

    def test_job_creation_with_webhook_id(self):
        """Test creating a job linked to a webhook."""
        job = Job(
            file_path="/media/test.mkv",
            container="mkv",
            source=JobSource.SONARR,
            priority=JobPriority.HIGH,
            webhook_id="webhook_123",
            tmdb_id=12345,
            series_title="Test Show",
        )

        assert job.priority == JobPriority.HIGH
        assert job.source == JobSource.SONARR
        assert job.webhook_id == "webhook_123"
        assert job.tmdb_id == 12345
        assert job.series_title == "Test Show"

    def test_job_to_db_dict(self):
        """Test converting job to database dictionary."""
        job = Job(
            file_path="/media/test.mkv",
            container="mkv",
            source=JobSource.MANUAL,
            selected_track_index=1,
            selected_track_language="eng",
        )

        db_dict = job.to_db_dict()

        assert db_dict["job_id"] == job.job_id
        assert db_dict["file_path"] == "/media/test.mkv"
        assert db_dict["container"] == "mkv"
        assert db_dict["status"] == "queued"
        assert db_dict["priority"] == "normal"
        assert db_dict["source"] == "manual"
        assert db_dict["selected_track_index"] == 1
        assert db_dict["selected_track_language"] == "eng"
        assert isinstance(db_dict["created_at"], str)

    def test_job_from_db_dict(self):
        """Test creating job from database dictionary."""
        db_dict = {
            "job_id": "job_test123",
            "file_path": "/media/test.mkv",
            "container": "mkv",
            "status": "completed",
            "priority": "high",
            "source": "sonarr",
            "webhook_id": "webhook_abc",
            "batch_id": None,
            "selected_track_index": 1,
            "selected_track_language": "eng",
            "created_at": "2024-01-01T12:00:00",
            "started_at": "2024-01-01T12:00:01",
            "completed_at": "2024-01-01T12:00:02",
            "success": True,
            "error_message": None,
            "retry_count": 0,
            "tmdb_id": 12345,
            "original_language": "en",
            "series_title": "Test Show",
            "movie_title": None,
        }

        job = Job.from_db_dict(db_dict)

        assert job.job_id == "job_test123"
        assert job.file_path == "/media/test.mkv"
        assert job.status == JobStatus.COMPLETED
        assert job.priority == JobPriority.HIGH
        assert job.source == JobSource.SONARR
        assert job.webhook_id == "webhook_abc"
        assert isinstance(job.created_at, datetime)
        assert isinstance(job.started_at, datetime)
        assert isinstance(job.completed_at, datetime)
        assert job.success is True

    def test_job_status_enum(self):
        """Test JobStatus enum values."""
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"

    def test_job_priority_enum(self):
        """Test JobPriority enum values."""
        assert JobPriority.HIGH.value == "high"
        assert JobPriority.NORMAL.value == "normal"
        assert JobPriority.LOW.value == "low"

    def test_job_source_enum(self):
        """Test JobSource enum values."""
        assert JobSource.SONARR.value == "sonarr"
        assert JobSource.RADARR.value == "radarr"
        assert JobSource.MANUAL.value == "manual"
        assert JobSource.RETRY.value == "retry"


class TestBatchRequest:
    """Test BatchRequest model."""

    def test_batch_request_defaults(self):
        """Test BatchRequest with default values."""
        request = BatchRequest(path="/media/tv")

        assert request.path == "/media/tv"
        assert request.recursive is True
        assert request.pattern == "**/*.{mkv,mp4}"
        assert request.dry_run is False
        assert request.priority == JobPriority.NORMAL

    def test_batch_request_custom_values(self):
        """Test BatchRequest with custom values."""
        request = BatchRequest(
            path="/media/anime",
            recursive=False,
            pattern="*.mkv",
            dry_run=True,
            priority=JobPriority.HIGH,
        )

        assert request.path == "/media/anime"
        assert request.recursive is False
        assert request.pattern == "*.mkv"
        assert request.dry_run is True
        assert request.priority == JobPriority.HIGH

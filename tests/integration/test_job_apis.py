"""Integration tests for Phase 5 job management APIs."""

from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from arrtheaudio.api.app import create_app
from arrtheaudio.config import Config
from arrtheaudio.core.queue_manager import JobQueueManager
from arrtheaudio.core.worker_pool import WorkerPool
from arrtheaudio.core.pipeline import ProcessingPipeline
from arrtheaudio.core.detector import ContainerType


@pytest.fixture
def test_config(tmp_path):
    """Create test configuration."""
    return Config(language_priority=["eng"])


@pytest.fixture
def test_client(test_config, tmp_path):
    """Create test client with job queue initialized."""
    from arrtheaudio import api

    app = create_app(test_config)

    # Initialize queue manager
    db_path = tmp_path / "test_jobs.db"
    queue_manager = JobQueueManager(test_config, db_path)

    # Initialize worker pool (but don't start)
    pipeline = ProcessingPipeline(test_config)
    worker_pool = WorkerPool(test_config, queue_manager, pipeline)

    # Set app state
    app.state.arrtheaudio.queue_manager = queue_manager
    app.state.arrtheaudio.worker_pool = worker_pool

    # Set global state for dependency injection (needed for job_routes.py dependencies)
    api.app._app_state = {
        "queue_manager": queue_manager,
        "worker_pool": worker_pool,
        "config": test_config,
    }

    return TestClient(app)


@pytest.fixture
def test_media_dir(tmp_path):
    """Create test media directory with files."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()

    # Create test files
    for i in range(3):
        (media_dir / f"test{i}.mkv").touch()

    return media_dir


class TestBatchAPI:
    """Test batch processing API."""

    def test_batch_start_success(self, test_client, test_media_dir):
        """Test starting a batch job."""
        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            response = test_client.post(
                "/api/v1/batch",
                json={
                    "path": str(test_media_dir),
                    "recursive": False,
                    "pattern": "*.mkv",
                    "dry_run": False,
                    "priority": "normal",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "batch_id" in data
        assert data["batch_id"].startswith("batch_")
        assert data["total_files"] == 3
        assert len(data["job_ids"]) == 3

    def test_batch_dry_run(self, test_client, test_media_dir):
        """Test batch dry run mode."""
        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            response = test_client.post(
                "/api/v1/batch",
                json={
                    "path": str(test_media_dir),
                    "recursive": False,
                    "pattern": "*.mkv",
                    "dry_run": True,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "dry run" in data["message"].lower()
        assert data["total_files"] == 0  # Dry run doesn't create jobs

    def test_batch_invalid_path(self, test_client):
        """Test batch with nonexistent path."""
        response = test_client.post(
            "/api/v1/batch",
            json={
                "path": "/nonexistent/path",
                "recursive": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert "no files found" in data["message"].lower()

    def test_batch_invalid_priority(self, test_client, test_media_dir):
        """Test batch with invalid priority."""
        response = test_client.post(
            "/api/v1/batch",
            json={
                "path": str(test_media_dir),
                "priority": "invalid_priority",
            },
        )

        assert response.status_code == 400
        assert "invalid priority" in response.json()["detail"].lower()


class TestQueueAPI:
    """Test queue status API."""

    def test_get_queue_status_empty(self, test_client):
        """Test getting queue status when empty."""
        response = test_client.get("/api/v1/queue")

        assert response.status_code == 200
        data = response.json()
        assert data["total_jobs"] == 0
        assert data["queued"] == 0
        assert data["running"] == 0
        assert data["completed"] == 0
        assert data["failed"] == 0
        assert data["cancelled"] == 0
        assert "workers_active" in data
        assert "workers_total" in data

    def test_get_queue_status_with_jobs(self, test_client, test_media_dir):
        """Test getting queue status with jobs."""
        # Submit batch to create jobs
        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            test_client.post(
                "/api/v1/batch",
                json={
                    "path": str(test_media_dir),
                    "pattern": "*.mkv",
                },
            )

        response = test_client.get("/api/v1/queue")

        assert response.status_code == 200
        data = response.json()
        assert data["total_jobs"] == 3
        assert data["queued"] == 3


class TestJobAPI:
    """Test job management API."""

    def test_get_job_success(self, test_client, test_media_dir):
        """Test getting job details."""
        # Create a job first
        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            batch_response = test_client.post(
                "/api/v1/batch",
                json={
                    "path": str(test_media_dir),
                    "pattern": "*.mkv",
                },
            )

        job_id = batch_response.json()["job_ids"][0]

        # Get job details
        response = test_client.get(f"/api/v1/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "queued"
        assert data["priority"] == "normal"
        assert data["source"] == "manual"
        assert data["container"] == "mkv"
        assert "created_at" in data

    def test_get_job_not_found(self, test_client):
        """Test getting nonexistent job."""
        response = test_client.get("/api/v1/jobs/nonexistent_job")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_cancel_job_success(self, test_client, test_media_dir):
        """Test cancelling a queued job."""
        # Create a job
        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            batch_response = test_client.post(
                "/api/v1/batch",
                json={
                    "path": str(test_media_dir),
                    "pattern": "*.mkv",
                },
            )

        job_id = batch_response.json()["job_ids"][0]

        # Cancel job
        response = test_client.delete(f"/api/v1/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "cancelled" in data["message"].lower()

        # Verify job was cancelled
        job_response = test_client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.json()["status"] == "cancelled"

    def test_cancel_job_not_found(self, test_client):
        """Test cancelling nonexistent job."""
        response = test_client.delete("/api/v1/jobs/nonexistent_job")

        assert response.status_code == 404


class TestWebhookJobsAPI:
    """Test webhook jobs API."""

    def test_get_webhook_jobs_success(self, test_client, test_media_dir):
        """Test getting all jobs from a webhook."""
        # Create jobs with webhook ID (simulating webhook handler)
        from arrtheaudio.core.job_models import JobPriority, JobSource

        queue_manager = test_client.app.state.arrtheaudio.queue_manager
        webhook_id = "webhook_test123"

        # Manually create jobs with webhook_id
        import asyncio

        async def create_jobs():
            jobs = []
            with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
                for file in test_media_dir.glob("*.mkv"):
                    job = await queue_manager.submit_job(
                        file_path=file,
                        priority=JobPriority.HIGH,
                        source=JobSource.SONARR,
                        webhook_id=webhook_id,
                    )
                    jobs.append(job)
            return jobs

        asyncio.run(create_jobs())

        # Get webhook jobs
        response = test_client.get(f"/api/v1/webhook/{webhook_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["webhook_id"] == webhook_id
        assert data["source"] == "sonarr"
        assert data["total_jobs"] == 3
        assert len(data["jobs"]) == 3
        assert data["all_completed"] is False
        assert data["any_failed"] is False

    def test_get_webhook_jobs_not_found(self, test_client):
        """Test getting jobs for nonexistent webhook."""
        response = test_client.get("/api/v1/webhook/nonexistent_webhook")

        assert response.status_code == 404


class TestBatchJobsAPI:
    """Test batch jobs API."""

    def test_get_batch_jobs_success(self, test_client, test_media_dir):
        """Test getting all jobs from a batch."""
        # Create batch
        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            batch_response = test_client.post(
                "/api/v1/batch",
                json={
                    "path": str(test_media_dir),
                    "pattern": "*.mkv",
                },
            )

        batch_id = batch_response.json()["batch_id"]

        # Get batch jobs
        response = test_client.get(f"/api/v1/batch/{batch_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["webhook_id"] == batch_id  # Reuses webhook_id field
        assert data["source"] == "manual"
        assert data["total_jobs"] == 3
        assert len(data["jobs"]) == 3

    def test_get_batch_jobs_not_found(self, test_client):
        """Test getting jobs for nonexistent batch."""
        response = test_client.get("/api/v1/batch/nonexistent_batch")

        assert response.status_code == 404


class TestStatsAPI:
    """Test statistics API."""

    def test_get_stats_empty(self, test_client):
        """Test getting stats with empty queue."""
        response = test_client.get("/api/v1/stats")

        assert response.status_code == 200
        data = response.json()
        assert "queue_stats" in data
        assert "worker_stats" in data
        assert data["queue_stats"]["total_jobs"] == 0
        assert data["worker_stats"]["total_workers"] >= 0

    def test_get_stats_with_jobs(self, test_client, test_media_dir):
        """Test getting stats with jobs in queue."""
        # Create jobs
        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            test_client.post(
                "/api/v1/batch",
                json={
                    "path": str(test_media_dir),
                    "pattern": "*.mkv",
                },
            )

        response = test_client.get("/api/v1/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["queue_stats"]["total_jobs"] == 3
        assert data["queue_stats"]["queued"] == 3
        assert "worker_stats" in data
        assert data["worker_stats"]["total_workers"] >= 0

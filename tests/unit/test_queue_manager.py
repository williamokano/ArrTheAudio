"""Unit tests for queue manager."""

from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from arrtheaudio.config import Config
from arrtheaudio.core.queue_manager import JobQueueManager
from arrtheaudio.core.job_models import JobPriority, JobSource, JobStatus, BatchRequest
from arrtheaudio.core.detector import ContainerType


@pytest.fixture
def config():
    """Create test configuration."""
    return Config(language_priority=["eng"])


@pytest.fixture
def queue_manager(tmp_path, config):
    """Create queue manager with test database."""
    db_path = tmp_path / "test_queue.db"
    return JobQueueManager(config, db_path)


@pytest.fixture
def test_file(tmp_path):
    """Create a test MKV file."""
    file_path = tmp_path / "test.mkv"
    file_path.touch()
    return file_path


class TestJobQueueManager:
    """Test JobQueueManager class."""

    @pytest.mark.asyncio
    async def test_submit_job_mkv(self, queue_manager, test_file):
        """Test submitting an MKV job."""
        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MKV):
            job = await queue_manager.submit_job(
                file_path=test_file,
                priority=JobPriority.NORMAL,
                source=JobSource.MANUAL,
            )

        assert job is not None
        assert job.file_path == str(test_file.resolve())
        assert job.container == "mkv"
        assert job.priority == JobPriority.NORMAL
        assert job.source == JobSource.MANUAL
        assert job.status == JobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_submit_job_mp4(self, queue_manager, tmp_path):
        """Test submitting an MP4 job."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MP4):
            job = await queue_manager.submit_job(
                file_path=test_file,
                priority=JobPriority.HIGH,
                source=JobSource.SONARR,
                webhook_id="webhook_123",
                tmdb_id=12345,
                series_title="Test Show",
            )

        assert job is not None
        assert job.container == "mp4"
        assert job.priority == JobPriority.HIGH
        assert job.webhook_id == "webhook_123"
        assert job.tmdb_id == 12345
        assert job.series_title == "Test Show"

    @pytest.mark.asyncio
    async def test_submit_job_unsupported_container(self, queue_manager, test_file):
        """Test submitting job with unsupported container."""
        with patch.object(
            queue_manager.detector, "detect", return_value=ContainerType.UNSUPPORTED
        ):
            job = await queue_manager.submit_job(
                file_path=test_file,
                source=JobSource.MANUAL,
            )

        assert job is None

    @pytest.mark.asyncio
    async def test_submit_job_mkv_disabled(self, config, tmp_path, test_file):
        """Test submitting MKV job when MKV is disabled."""
        config.containers.mkv = False
        queue_manager = JobQueueManager(config, tmp_path / "test.db")

        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MKV):
            job = await queue_manager.submit_job(
                file_path=test_file,
                source=JobSource.MANUAL,
            )

        assert job is None

    @pytest.mark.asyncio
    async def test_submit_batch_with_files(self, queue_manager, tmp_path):
        """Test submitting a batch with multiple files."""
        # Create test files
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        file1 = media_dir / "test1.mkv"
        file2 = media_dir / "test2.mkv"
        file1.touch()
        file2.touch()

        request = BatchRequest(
            path=str(media_dir),
            recursive=False,
            pattern="*.mkv",
            dry_run=False,
        )

        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MKV):
            batch_id, jobs = await queue_manager.submit_batch(request)

        assert batch_id.startswith("batch_")
        assert len(jobs) == 2
        assert all(j.batch_id == batch_id for j in jobs)
        assert all(j.source == JobSource.MANUAL for j in jobs)

    @pytest.mark.asyncio
    async def test_submit_batch_dry_run(self, queue_manager, tmp_path):
        """Test submitting a batch in dry run mode."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        file1 = media_dir / "test1.mkv"
        file1.touch()

        request = BatchRequest(
            path=str(media_dir),
            recursive=False,
            pattern="*.mkv",
            dry_run=True,
        )

        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MKV):
            batch_id, jobs = await queue_manager.submit_batch(request)

        assert batch_id.startswith("batch_")
        assert len(jobs) == 0  # Dry run doesn't create jobs

    @pytest.mark.asyncio
    async def test_submit_batch_no_files(self, queue_manager, tmp_path):
        """Test submitting a batch with no matching files."""
        media_dir = tmp_path / "empty"
        media_dir.mkdir()

        request = BatchRequest(
            path=str(media_dir),
            pattern="*.mkv",
        )

        batch_id, jobs = await queue_manager.submit_batch(request)

        assert batch_id.startswith("batch_")
        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_submit_batch_nonexistent_path(self, queue_manager):
        """Test submitting a batch with nonexistent path."""
        request = BatchRequest(path="/nonexistent/path")

        batch_id, jobs = await queue_manager.submit_batch(request)

        assert batch_id.startswith("batch_")
        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_get_job(self, queue_manager, test_file):
        """Test getting a job by ID."""
        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MKV):
            submitted_job = await queue_manager.submit_job(
                file_path=test_file,
                source=JobSource.MANUAL,
            )

        retrieved_job = await queue_manager.get_job(submitted_job.job_id)

        assert retrieved_job is not None
        assert retrieved_job.job_id == submitted_job.job_id
        assert retrieved_job.file_path == submitted_job.file_path

    @pytest.mark.asyncio
    async def test_get_jobs_by_webhook(self, queue_manager, tmp_path):
        """Test getting jobs by webhook ID."""
        webhook_id = "webhook_test"
        file1 = tmp_path / "test1.mkv"
        file2 = tmp_path / "test2.mkv"
        file1.touch()
        file2.touch()

        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MKV):
            job1 = await queue_manager.submit_job(
                file_path=file1,
                source=JobSource.SONARR,
                webhook_id=webhook_id,
            )
            job2 = await queue_manager.submit_job(
                file_path=file2,
                source=JobSource.SONARR,
                webhook_id=webhook_id,
            )

        webhook_jobs = await queue_manager.get_jobs_by_webhook(webhook_id)

        assert len(webhook_jobs) == 2
        assert all(j.webhook_id == webhook_id for j in webhook_jobs)

    @pytest.mark.asyncio
    async def test_get_jobs_by_batch(self, queue_manager, tmp_path):
        """Test getting jobs by batch ID."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        file1 = media_dir / "test1.mkv"
        file2 = media_dir / "test2.mkv"
        file1.touch()
        file2.touch()

        request = BatchRequest(path=str(media_dir), pattern="*.mkv")

        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MKV):
            batch_id, jobs = await queue_manager.submit_batch(request)

        batch_jobs = await queue_manager.get_jobs_by_batch(batch_id)

        assert len(batch_jobs) == 2
        assert all(j.batch_id == batch_id for j in batch_jobs)

    @pytest.mark.asyncio
    async def test_update_job_status(self, queue_manager, test_file):
        """Test updating job status."""
        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MKV):
            job = await queue_manager.submit_job(
                file_path=test_file,
                source=JobSource.MANUAL,
            )

        # Update to running
        result = await queue_manager.update_job_status(
            job.job_id,
            JobStatus.RUNNING,
            selected_track_index=1,
            selected_track_language="eng",
        )

        assert result is True

        # Verify update
        updated_job = await queue_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.started_at is not None
        assert updated_job.selected_track_index == 1
        assert updated_job.selected_track_language == "eng"

    @pytest.mark.asyncio
    async def test_update_job_status_completed(self, queue_manager, test_file):
        """Test updating job to completed status."""
        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MKV):
            job = await queue_manager.submit_job(
                file_path=test_file,
                source=JobSource.MANUAL,
            )

        # Update to completed
        result = await queue_manager.update_job_status(
            job.job_id,
            JobStatus.COMPLETED,
            success=True,
        )

        assert result is True

        # Verify update
        updated_job = await queue_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.completed_at is not None
        assert updated_job.success is True

    @pytest.mark.asyncio
    async def test_cancel_job(self, queue_manager, test_file):
        """Test cancelling a job."""
        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MKV):
            job = await queue_manager.submit_job(
                file_path=test_file,
                source=JobSource.MANUAL,
            )

        result = await queue_manager.cancel_job(job.job_id)

        assert result is True

        # Verify cancellation
        cancelled_job = await queue_manager.get_job(job.job_id)
        assert cancelled_job.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_get_queue_stats(self, queue_manager, tmp_path):
        """Test getting queue statistics."""
        # Create jobs with different statuses
        files = [tmp_path / f"test{i}.mkv" for i in range(3)]
        for f in files:
            f.touch()

        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MKV):
            job1 = await queue_manager.submit_job(file_path=files[0], source=JobSource.MANUAL)
            job2 = await queue_manager.submit_job(file_path=files[1], source=JobSource.MANUAL)
            job3 = await queue_manager.submit_job(file_path=files[2], source=JobSource.MANUAL)

        # Update job statuses
        await queue_manager.update_job_status(job2.job_id, JobStatus.RUNNING)
        await queue_manager.update_job_status(job3.job_id, JobStatus.COMPLETED, success=True)

        stats = await queue_manager.get_queue_stats()

        assert stats["total"] == 3
        assert stats["queued"] == 1
        assert stats["running"] == 1
        assert stats["completed"] == 1

    @pytest.mark.asyncio
    async def test_get_next_job(self, queue_manager, tmp_path):
        """Test getting next job from queue."""
        file1 = tmp_path / "low.mkv"
        file2 = tmp_path / "high.mkv"
        file1.touch()
        file2.touch()

        with patch.object(queue_manager.detector, "detect", return_value=ContainerType.MKV):
            # Submit low priority job first
            await queue_manager.submit_job(
                file_path=file1,
                source=JobSource.MANUAL,
                priority=JobPriority.LOW,
            )
            # Submit high priority job second
            await queue_manager.submit_job(
                file_path=file2,
                source=JobSource.SONARR,
                priority=JobPriority.HIGH,
            )

        # Get next job - should be high priority
        next_job = await queue_manager.get_next_job()

        assert next_job is not None
        assert next_job.priority == JobPriority.HIGH
        assert next_job.file_path == str(file2.resolve())

    def test_count_running_mp4_jobs(self, queue_manager):
        """Test counting running MP4 jobs."""
        # This tests the direct database call
        count = queue_manager.count_running_mp4_jobs()
        assert count == 0  # Empty database

    @pytest.mark.asyncio
    async def test_cleanup_old_jobs(self, queue_manager):
        """Test cleanup of old jobs."""
        deleted = await queue_manager.cleanup_old_jobs(days=30)
        assert deleted >= 0  # Doesn't error

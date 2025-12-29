"""Job queue manager."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from arrtheaudio.config import Config
from arrtheaudio.core.database import JobDatabase
from arrtheaudio.core.job_models import (
    Job,
    JobPriority,
    JobSource,
    JobStatus,
    BatchRequest,
)
from arrtheaudio.core.detector import ContainerDetector
from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class JobQueueManager:
    """Manages job queue and database operations."""

    def __init__(self, config: Config, db_path: Path):
        """Initialize queue manager.

        Args:
            config: Application configuration
            db_path: Path to SQLite database
        """
        self.config = config
        self.db = JobDatabase(db_path)
        self.detector = ContainerDetector()
        self._lock = asyncio.Lock()

    async def submit_job(
        self,
        file_path: Path,
        priority: JobPriority = JobPriority.NORMAL,
        source: JobSource = JobSource.MANUAL,
        webhook_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        tmdb_id: Optional[int] = None,
        original_language: Optional[str] = None,
        series_title: Optional[str] = None,
        movie_title: Optional[str] = None,
    ) -> Optional[Job]:
        """Submit a single file for processing.

        Args:
            file_path: Path to file
            priority: Job priority
            source: Job source
            webhook_id: Optional webhook ID to link jobs
            batch_id: Optional batch ID to link jobs
            tmdb_id: Optional TMDB ID for metadata
            original_language: Optional original language
            series_title: Optional series title
            movie_title: Optional movie title

        Returns:
            Created Job or None if failed
        """
        try:
            # Detect container type
            container = self.detector.detect(file_path)
            if container.value == "unsupported":
                logger.warning(
                    "Unsupported container type, skipping", file=str(file_path)
                )
                return None

            # Check if enabled in config
            if container.value == "mkv" and not self.config.containers.mkv:
                logger.debug("MKV processing disabled", file=str(file_path))
                return None
            if container.value == "mp4" and not self.config.containers.mp4:
                logger.debug("MP4 processing disabled", file=str(file_path))
                return None

            # Create job
            job = Job(
                file_path=str(file_path.resolve()),
                container=container.value,
                priority=priority,
                source=source,
                webhook_id=webhook_id,
                batch_id=batch_id,
                tmdb_id=tmdb_id,
                original_language=original_language,
                series_title=series_title,
                movie_title=movie_title,
            )

            # Add to database
            async with self._lock:
                if self.db.add_job(job):
                    logger.info(
                        "Job submitted",
                        job_id=job.job_id,
                        file=str(file_path),
                        priority=priority if isinstance(priority, str) else priority.value,
                        source=source if isinstance(source, str) else source.value,
                    )
                    return job
                else:
                    logger.error("Failed to add job to database", file=str(file_path))
                    return None

        except Exception as e:
            logger.error(
                "Failed to submit job", file=str(file_path), error=str(e), exc_info=True
            )
            return None

    async def submit_batch(self, request: BatchRequest) -> tuple[str, List[Job]]:
        """Submit batch of files for processing.

        Args:
            request: Batch request with path and options

        Returns:
            Tuple of (batch_id, list of created jobs)
        """
        batch_id = f"batch_{uuid4().hex[:12]}"
        jobs = []

        try:
            # Scan directory for files
            path = Path(request.path)
            if not path.exists():
                logger.error("Batch path does not exist", path=str(path))
                return batch_id, []

            logger.info(
                "Starting batch scan",
                batch_id=batch_id,
                path=str(path),
                recursive=request.recursive,
            )

            # Find files matching pattern
            files = self._find_files(path, request.pattern, request.recursive)

            if not files:
                logger.warning("No files found in batch", batch_id=batch_id)
                return batch_id, []

            logger.info("Found files for batch", batch_id=batch_id, count=len(files))

            # Create jobs for each file
            for file_path in files:
                if request.dry_run:
                    # Just log what would be processed
                    container = self.detector.detect(file_path)
                    logger.info(
                        "Would process file (dry run)",
                        file=str(file_path),
                        container=container.value,
                    )
                    continue

                job = await self.submit_job(
                    file_path=file_path,
                    priority=request.priority,
                    source=JobSource.MANUAL,
                    batch_id=batch_id,
                )

                if job:
                    jobs.append(job)

            logger.info(
                "Batch submission complete",
                batch_id=batch_id,
                total_files=len(files),
                jobs_created=len(jobs),
            )

            return batch_id, jobs

        except Exception as e:
            logger.error(
                "Batch submission failed",
                batch_id=batch_id,
                error=str(e),
                exc_info=True,
            )
            return batch_id, jobs

    def _find_files(
        self, path: Path, pattern: str, recursive: bool = True
    ) -> List[Path]:
        """Find files matching pattern.

        Args:
            path: Directory to scan
            pattern: Glob pattern
            recursive: Scan subdirectories

        Returns:
            List of file paths
        """
        files = []

        try:
            if recursive:
                # Use ** for recursive glob
                if not pattern.startswith("**/"):
                    pattern = f"**/{pattern}"
                files = list(path.glob(pattern))
            else:
                # Non-recursive glob
                files = list(path.glob(pattern))

            # Filter to only files (not directories)
            files = [f for f in files if f.is_file()]

            return files

        except Exception as e:
            logger.error("Error finding files", path=str(path), error=str(e))
            return []

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job if found
        """
        return self.db.get_job(job_id)

    async def get_jobs_by_webhook(self, webhook_id: str) -> List[Job]:
        """Get all jobs from webhook.

        Args:
            webhook_id: Webhook ID

        Returns:
            List of jobs
        """
        return self.db.get_jobs_by_webhook(webhook_id)

    async def get_jobs_by_batch(self, batch_id: str) -> List[Job]:
        """Get all jobs from batch.

        Args:
            batch_id: Batch ID

        Returns:
            List of jobs
        """
        return self.db.get_jobs_by_batch(batch_id)

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None,
        success: Optional[bool] = None,
        selected_track_index: Optional[int] = None,
        selected_track_language: Optional[str] = None,
    ) -> bool:
        """Update job status.

        Args:
            job_id: Job ID
            status: New status
            error_message: Optional error message
            success: Optional success flag
            selected_track_index: Optional selected track index
            selected_track_language: Optional selected track language

        Returns:
            True if successful
        """
        async with self._lock:
            job = self.db.get_job(job_id)
            if not job:
                logger.error("Job not found for status update", job_id=job_id)
                return False

            # Update fields
            job.status = status

            if status == JobStatus.RUNNING:
                job.started_at = datetime.utcnow()
            elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                job.completed_at = datetime.utcnow()

            if error_message is not None:
                job.error_message = error_message
            if success is not None:
                job.success = success
            if selected_track_index is not None:
                job.selected_track_index = selected_track_index
            if selected_track_language is not None:
                job.selected_track_language = selected_track_language

            return self.db.update_job(job)

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.

        Args:
            job_id: Job ID

        Returns:
            True if successful
        """
        return await self.update_job_status(job_id, JobStatus.CANCELLED)

    async def get_queue_stats(self) -> dict:
        """Get queue statistics.

        Returns:
            Statistics dictionary
        """
        return self.db.get_queue_stats()

    async def get_next_job(self) -> Optional[Job]:
        """Get next job from queue.

        Returns:
            Next job to process
        """
        async with self._lock:
            return self.db.get_next_job()

    def count_running_mp4_jobs(self) -> int:
        """Count running MP4 jobs.

        Returns:
            Number of running MP4 jobs
        """
        return self.db.count_running_by_container("mp4")

    async def cleanup_old_jobs(self, days: int = 30) -> int:
        """Cleanup old jobs.

        Args:
            days: Keep jobs from last N days

        Returns:
            Number of jobs deleted
        """
        return self.db.cleanup_old_jobs(days)

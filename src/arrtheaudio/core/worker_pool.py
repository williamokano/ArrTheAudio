"""Worker pool for concurrent job processing."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from arrtheaudio.config import Config
from arrtheaudio.core.job_models import Job, JobStatus, JobPriority, JobSource
from arrtheaudio.core.queue_manager import JobQueueManager
from arrtheaudio.core.pipeline import ProcessingPipeline
from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class Worker:
    """Individual worker for processing jobs."""

    def __init__(
        self,
        worker_id: int,
        config: Config,
        queue_manager: JobQueueManager,
        pipeline: ProcessingPipeline,
    ):
        """Initialize worker.

        Args:
            worker_id: Worker identifier
            config: Application configuration
            queue_manager: Job queue manager
            pipeline: Processing pipeline
        """
        self.worker_id = worker_id
        self.config = config
        self.queue_manager = queue_manager
        self.pipeline = pipeline
        self.current_job: Optional[Job] = None
        self._running = False

    async def start(self):
        """Start worker loop."""
        self._running = True
        logger.info("Worker started", worker_id=self.worker_id)

        while self._running:
            try:
                # Get next job from queue
                job = await self.queue_manager.get_next_job()

                if not job:
                    # No jobs available, wait a bit
                    await asyncio.sleep(1)
                    continue

                # Check if this is an MP4 job and we're at the limit
                if job.container == "mp4":
                    mp4_count = self.queue_manager.count_running_mp4_jobs()
                    max_mp4 = self.config.processing.max_mp4_concurrent

                    if mp4_count >= max_mp4:
                        # MP4 limit reached, wait
                        logger.debug(
                            "MP4 concurrency limit reached, waiting",
                            worker_id=self.worker_id,
                            running=mp4_count,
                            max=max_mp4,
                        )
                        await asyncio.sleep(2)
                        continue

                # Process the job
                await self._process_job(job)

            except asyncio.CancelledError:
                logger.info("Worker cancelled", worker_id=self.worker_id)
                break
            except Exception as e:
                logger.error(
                    "Worker error",
                    worker_id=self.worker_id,
                    error=str(e),
                    exc_info=True,
                )
                await asyncio.sleep(1)

        logger.info("Worker stopped", worker_id=self.worker_id)

    async def _process_job(self, job: Job):
        """Process a single job.

        Args:
            job: Job to process
        """
        self.current_job = job

        try:
            # Mark job as running
            await self.queue_manager.update_job_status(job.job_id, JobStatus.RUNNING)

            logger.info(
                "Processing job",
                worker_id=self.worker_id,
                job_id=job.job_id,
                file=job.file_path,
                container=job.container,
            )

            # Process file with pipeline
            file_path = Path(job.file_path)

            # Run pipeline processing (synchronous, but in executor)
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._run_pipeline, file_path, job
            )

            # Update job based on result
            if result.get("success"):
                await self.queue_manager.update_job_status(
                    job.job_id,
                    JobStatus.COMPLETED,
                    success=True,
                    selected_track_index=result.get("selected_track_index"),
                    selected_track_language=result.get("selected_track_language"),
                )
                logger.info(
                    "Job completed successfully",
                    worker_id=self.worker_id,
                    job_id=job.job_id,
                )
            else:
                error_msg = result.get("error", "Unknown error")
                await self.queue_manager.update_job_status(
                    job.job_id, JobStatus.FAILED, success=False, error_message=error_msg
                )
                logger.error(
                    "Job failed",
                    worker_id=self.worker_id,
                    job_id=job.job_id,
                    error=error_msg,
                )

        except Exception as e:
            # Job processing failed
            error_msg = str(e)
            await self.queue_manager.update_job_status(
                job.job_id, JobStatus.FAILED, success=False, error_message=error_msg
            )
            logger.error(
                "Job processing error",
                worker_id=self.worker_id,
                job_id=job.job_id,
                error=error_msg,
                exc_info=True,
            )

        finally:
            self.current_job = None

    def _run_pipeline(self, file_path: Path, job: Job) -> dict:
        """Run processing pipeline (synchronous).

        Args:
            file_path: Path to file
            job: Job being processed

        Returns:
            Result dictionary
        """
        try:
            # Process file with pipeline
            result = self.pipeline.process(
                file_path=file_path,
                tmdb_id=job.tmdb_id,
                original_language=job.original_language,
            )

            if result.status == "success":
                return {
                    "success": True,
                    "selected_track_index": result.selected_track.index
                    if result.selected_track
                    else None,
                    "selected_track_language": result.selected_track.language
                    if result.selected_track
                    else None,
                }
            else:
                return {"success": False, "error": result.message}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def stop(self):
        """Stop worker."""
        self._running = False

    @property
    def is_busy(self) -> bool:
        """Check if worker is currently processing a job."""
        return self.current_job is not None


class WorkerPool:
    """Pool of workers for concurrent job processing."""

    def __init__(
        self,
        config: Config,
        queue_manager: JobQueueManager,
        pipeline: ProcessingPipeline,
    ):
        """Initialize worker pool.

        Args:
            config: Application configuration
            queue_manager: Job queue manager
            pipeline: Processing pipeline
        """
        self.config = config
        self.queue_manager = queue_manager
        self.pipeline = pipeline
        self.workers: list[Worker] = []
        self.worker_tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self):
        """Start worker pool."""
        if self._running:
            logger.warning("Worker pool already running")
            return

        worker_count = self.config.processing.worker_count
        logger.info("Starting worker pool", worker_count=worker_count)

        # Create workers
        for i in range(worker_count):
            worker = Worker(
                worker_id=i,
                config=self.config,
                queue_manager=self.queue_manager,
                pipeline=self.pipeline,
            )
            self.workers.append(worker)

            # Start worker task
            task = asyncio.create_task(worker.start())
            self.worker_tasks.append(task)

        self._running = True
        logger.info("Worker pool started", worker_count=worker_count)

    async def stop(self):
        """Stop worker pool."""
        if not self._running:
            return

        logger.info("Stopping worker pool", worker_count=len(self.workers))

        # Stop all workers
        for worker in self.workers:
            await worker.stop()

        # Cancel all worker tasks
        for task in self.worker_tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)

        self.workers.clear()
        self.worker_tasks.clear()
        self._running = False

        logger.info("Worker pool stopped")

    def get_active_workers_count(self) -> int:
        """Get number of active workers.

        Returns:
            Number of busy workers
        """
        return sum(1 for worker in self.workers if worker.is_busy)

    def get_worker_count(self) -> int:
        """Get total number of workers.

        Returns:
            Total workers
        """
        return len(self.workers)

    @property
    def is_running(self) -> bool:
        """Check if worker pool is running."""
        return self._running

"""API routes for job queue management (Phase 5)."""

from typing import List
from fastapi import APIRouter, HTTPException, Depends

from arrtheaudio.api.models import (
    BatchRequest,
    BatchResponse,
    JobResponse,
    QueueResponse,
    WebhookJobsResponse,
    StatsResponse,
)
from arrtheaudio.core.job_models import JobPriority
from arrtheaudio.core.queue_manager import JobQueueManager
from arrtheaudio.core.worker_pool import WorkerPool
from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["jobs"])


def get_queue_manager() -> JobQueueManager:
    """Dependency to get queue manager from app state."""
    # This will be injected by the app
    from arrtheaudio.api.app import get_app_state

    state = get_app_state()
    return state["queue_manager"]


def get_worker_pool() -> WorkerPool:
    """Dependency to get worker pool from app state."""
    from arrtheaudio.api.app import get_app_state

    state = get_app_state()
    return state["worker_pool"]


@router.post("/batch", response_model=BatchResponse)
async def start_batch(
    request: BatchRequest,
    queue_manager: JobQueueManager = Depends(get_queue_manager),
):
    """Start batch processing of directory.

    Creates jobs for all matching files in the specified directory.
    Each file becomes one job in the queue.

    Args:
        request: Batch request with path and options
        queue_manager: Job queue manager

    Returns:
        Batch response with batch_id and job_ids
    """
    try:
        logger.info(
            "Batch request received",
            path=request.path,
            recursive=request.recursive,
            pattern=request.pattern,
            dry_run=request.dry_run,
        )

        # Convert priority string to enum
        try:
            priority = JobPriority(request.priority)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority: {request.priority}. Must be: high, normal, low",
            )

        # Submit batch
        batch_id, jobs = await queue_manager.submit_batch(request)

        if not jobs and not request.dry_run:
            return BatchResponse(
                status="rejected",
                message="No files found matching criteria",
            )

        logger.info(
            "Batch submitted",
            batch_id=batch_id,
            total_files=len(jobs),
            dry_run=request.dry_run,
        )

        return BatchResponse(
            status="started",
            batch_id=batch_id,
            total_files=len(jobs),
            job_ids=[job.job_id for job in jobs],
            message=f"Batch started with {len(jobs)} files"
            if not request.dry_run
            else f"Dry run: would process {len(jobs)} files",
        )

    except Exception as e:
        logger.error("Batch request failed", error=str(e), exc_info=True)
        return BatchResponse(
            status="rejected",
            message=f"Batch failed: {str(e)}",
        )


@router.get("/queue", response_model=QueueResponse)
async def get_queue_status(
    queue_manager: JobQueueManager = Depends(get_queue_manager),
    worker_pool: WorkerPool = Depends(get_worker_pool),
):
    """Get current queue status.

    Returns counts of jobs by status and worker information.

    Returns:
        Queue status with job counts and worker stats
    """
    try:
        stats = await queue_manager.get_queue_stats()

        return QueueResponse(
            total_jobs=stats.get("total", 0),
            queued=stats.get("queued", 0),
            running=stats.get("running", 0),
            completed=stats.get("completed", 0),
            failed=stats.get("failed", 0),
            cancelled=stats.get("cancelled", 0),
            workers_active=worker_pool.get_active_workers_count(),
            workers_total=worker_pool.get_worker_count(),
        )

    except Exception as e:
        logger.error("Failed to get queue status", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get queue status")


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    queue_manager: JobQueueManager = Depends(get_queue_manager),
):
    """Get job details by ID.

    Args:
        job_id: Job ID
        queue_manager: Job queue manager

    Returns:
        Job details

    Raises:
        HTTPException: If job not found
    """
    try:
        job = await queue_manager.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return JobResponse(
            job_id=job.job_id,
            file_path=job.file_path,
            status=job.status.value,
            priority=job.priority.value,
            source=job.source.value,
            container=job.container,
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            success=job.success,
            error_message=job.error_message,
            selected_track_index=job.selected_track_index,
            selected_track_language=job.selected_track_language,
            webhook_id=job.webhook_id,
            batch_id=job.batch_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job", job_id=job_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get job")


@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: str,
    queue_manager: JobQueueManager = Depends(get_queue_manager),
):
    """Cancel a queued job.

    Can only cancel jobs that are in 'queued' status.
    Running jobs cannot be cancelled.

    Args:
        job_id: Job ID
        queue_manager: Job queue manager

    Returns:
        Success message

    Raises:
        HTTPException: If job not found or cannot be cancelled
    """
    try:
        job = await queue_manager.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        if job.status.value not in ("queued",):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job in status: {job.status.value}",
            )

        success = await queue_manager.cancel_job(job_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to cancel job")

        logger.info("Job cancelled", job_id=job_id)
        return {"status": "success", "message": f"Job {job_id} cancelled"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel job", job_id=job_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cancel job")


@router.get("/webhook/{webhook_id}", response_model=WebhookJobsResponse)
async def get_webhook_jobs(
    webhook_id: str,
    queue_manager: JobQueueManager = Depends(get_queue_manager),
):
    """Get all jobs from a webhook.

    Returns all jobs created from the same webhook request.
    Useful for tracking multi-file webhook progress.

    Args:
        webhook_id: Webhook ID
        queue_manager: Job queue manager

    Returns:
        Webhook jobs with status summary

    Raises:
        HTTPException: If no jobs found for webhook
    """
    try:
        jobs = await queue_manager.get_jobs_by_webhook(webhook_id)

        if not jobs:
            raise HTTPException(
                status_code=404, detail=f"No jobs found for webhook {webhook_id}"
            )

        # Convert to response model
        job_responses = [
            JobResponse(
                job_id=job.job_id,
                file_path=job.file_path,
                status=job.status.value,
                priority=job.priority.value,
                source=job.source.value,
                container=job.container,
                created_at=job.created_at.isoformat(),
                started_at=job.started_at.isoformat() if job.started_at else None,
                completed_at=job.completed_at.isoformat()
                if job.completed_at
                else None,
                success=job.success,
                error_message=job.error_message,
                selected_track_index=job.selected_track_index,
                selected_track_language=job.selected_track_language,
                webhook_id=job.webhook_id,
                batch_id=job.batch_id,
            )
            for job in jobs
        ]

        # Calculate summary
        all_completed = all(
            j.status.value in ("completed", "failed", "cancelled") for j in jobs
        )
        any_failed = any(j.status.value == "failed" for j in jobs)

        return WebhookJobsResponse(
            webhook_id=webhook_id,
            source=jobs[0].source.value,
            total_jobs=len(jobs),
            jobs=job_responses,
            all_completed=all_completed,
            any_failed=any_failed,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get webhook jobs",
            webhook_id=webhook_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to get webhook jobs")


@router.get("/batch/{batch_id}", response_model=WebhookJobsResponse)
async def get_batch_jobs(
    batch_id: str,
    queue_manager: JobQueueManager = Depends(get_queue_manager),
):
    """Get all jobs from a batch.

    Returns all jobs created from the same batch request.
    Useful for tracking batch processing progress.

    Args:
        batch_id: Batch ID
        queue_manager: Job queue manager

    Returns:
        Batch jobs with status summary

    Raises:
        HTTPException: If no jobs found for batch
    """
    try:
        jobs = await queue_manager.get_jobs_by_batch(batch_id)

        if not jobs:
            raise HTTPException(
                status_code=404, detail=f"No jobs found for batch {batch_id}"
            )

        # Convert to response model (reuse WebhookJobsResponse structure)
        job_responses = [
            JobResponse(
                job_id=job.job_id,
                file_path=job.file_path,
                status=job.status.value,
                priority=job.priority.value,
                source=job.source.value,
                container=job.container,
                created_at=job.created_at.isoformat(),
                started_at=job.started_at.isoformat() if job.started_at else None,
                completed_at=job.completed_at.isoformat()
                if job.completed_at
                else None,
                success=job.success,
                error_message=job.error_message,
                selected_track_index=job.selected_track_index,
                selected_track_language=job.selected_track_language,
                webhook_id=job.webhook_id,
                batch_id=job.batch_id,
            )
            for job in jobs
        ]

        # Calculate summary
        all_completed = all(
            j.status.value in ("completed", "failed", "cancelled") for j in jobs
        )
        any_failed = any(j.status.value == "failed" for j in jobs)

        return WebhookJobsResponse(
            webhook_id=batch_id,  # Reuse field name
            source="manual",
            total_jobs=len(jobs),
            jobs=job_responses,
            all_completed=all_completed,
            any_failed=any_failed,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get batch jobs", batch_id=batch_id, error=str(e), exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to get batch jobs")


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    queue_manager: JobQueueManager = Depends(get_queue_manager),
    worker_pool: WorkerPool = Depends(get_worker_pool),
):
    """Get overall system statistics.

    Returns queue stats, worker stats, and system health.

    Returns:
        System statistics
    """
    try:
        stats = await queue_manager.get_queue_stats()

        queue_response = QueueResponse(
            total_jobs=stats.get("total", 0),
            queued=stats.get("queued", 0),
            running=stats.get("running", 0),
            completed=stats.get("completed", 0),
            failed=stats.get("failed", 0),
            cancelled=stats.get("cancelled", 0),
            workers_active=worker_pool.get_active_workers_count(),
            workers_total=worker_pool.get_worker_count(),
        )

        worker_stats = {
            "total_workers": worker_pool.get_worker_count(),
            "active_workers": worker_pool.get_active_workers_count(),
            "idle_workers": worker_pool.get_worker_count()
            - worker_pool.get_active_workers_count(),
            "pool_running": worker_pool.is_running,
        }

        return StatsResponse(
            queue_stats=queue_response,
            worker_stats=worker_stats,
        )

    except Exception as e:
        logger.error("Failed to get stats", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get stats")

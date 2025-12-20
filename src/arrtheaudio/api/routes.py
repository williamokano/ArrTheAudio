"""API routes for webhooks and batch processing."""

import hmac
import hashlib
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from arrtheaudio import __version__
from arrtheaudio.api.models import (
    SonarrWebhookPayload,
    RadarrWebhookPayload,
    WebhookResponse,
    BatchRequest,
    BatchResponse,
    HealthResponse,
)
from arrtheaudio.core.pipeline import ProcessingPipeline
from arrtheaudio.core.scanner import FileScanner
from arrtheaudio.metadata.cache import TMDBCache
from arrtheaudio.metadata.tmdb import TMDBClient
from arrtheaudio.metadata.resolver import MetadataResolver
from arrtheaudio.utils.logger import get_logger
from arrtheaudio.utils.path_mapper import PathMapper

logger = get_logger(__name__)
router = APIRouter()


def verify_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify webhook HMAC signature.

    Args:
        body: Request body bytes
        signature: Signature from header
        secret: Shared secret

    Returns:
        True if signature is valid
    """
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def process_file_task(file_path: Path, config, job_id: str, arr_metadata: dict = None):
    """Background task to process a file.

    Args:
        file_path: Path to the file
        config: Application configuration
        job_id: Job identifier
        arr_metadata: Optional Arr metadata from webhook
    """
    logger.info("Starting background processing", file=str(file_path), job_id=job_id)

    try:
        # Initialize TMDB client and resolver if enabled
        resolver = None
        if config.tmdb.enabled and config.tmdb.api_key:
            cache = TMDBCache(Path(config.tmdb.cache_path), config.tmdb.cache_ttl_days)
            tmdb_client = TMDBClient(config.tmdb.api_key, cache)
            resolver = MetadataResolver(tmdb_client, config)
        else:
            resolver = MetadataResolver(None, config)

        # Resolve metadata
        metadata = await resolver.resolve(file_path, arr_metadata)

        # Process file with metadata
        pipeline = ProcessingPipeline(config)
        result = await pipeline.process(file_path, metadata)

        logger.info(
            "Background processing complete",
            file=str(file_path),
            job_id=job_id,
            status=result.status,
        )

        # Close TMDB client if it was created
        if config.tmdb.enabled and config.tmdb.api_key:
            await tmdb_client.close()

    except Exception as e:
        logger.exception("Background processing failed", file=str(file_path), job_id=job_id)


@router.post("/webhook/sonarr", response_model=WebhookResponse)
async def sonarr_webhook(
    request: Request,
    payload: SonarrWebhookPayload,
):
    """Handle Sonarr webhook (Phase 5: Multi-file support).

    FIXES CRITICAL BUG: Now processes ALL files from episodeFiles array,
    not just the first one. Creates one job per file.

    Args:
        request: FastAPI request
        payload: Sonarr webhook payload

    Returns:
        Webhook response with multiple job IDs
    """
    app_state = request.app.state.arrtheaudio
    config = app_state.config
    queue_manager = app_state.queue_manager

    # Count files in payload
    file_count = len(payload.episodeFiles) if payload.episodeFiles else 0

    logger.info(
        "Sonarr webhook received and validated",
        series_title=payload.series_title,
        series_id=payload.series.id,
        event_type=payload.event_type,
        tvdb_id=payload.series_tvdb_id,
        tmdb_id=payload.series_tmdb_id,
        file_count=file_count,  # Log actual count
        original_language=payload.original_language,
    )

    # Verify webhook signature if configured
    if config.api.webhook_secret:
        signature = request.headers.get("X-Webhook-Signature")
        if not signature:
            logger.warning("Missing webhook signature")
            raise HTTPException(status_code=401, detail="Missing signature")

        body = await request.body()
        if not verify_webhook_signature(body, signature, config.api.webhook_secret):
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Check if files exist
    if not payload.episodeFiles or len(payload.episodeFiles) == 0:
        logger.warning("No episode files in webhook payload")
        return WebhookResponse(
            status="rejected",
            message="No episode files in payload",
        )

    # Generate webhook ID to link all jobs
    webhook_id = f"webhook_{uuid.uuid4().hex[:12]}"
    job_ids = []
    path_mapper = PathMapper(config.path_mappings)

    # Process ALL files (fixes critical bug!)
    for episode_file in payload.episodeFiles:
        file_path = episode_file.path

        logger.debug(
            "Processing file from webhook",
            webhook_id=webhook_id,
            file=file_path,
        )

        # Map path from Arr to local filesystem
        local_path = path_mapper.map_path(file_path)

        # Validate file exists
        if not local_path.exists():
            logger.error(
                "File not found after path mapping",
                file=file_path,
                local_path=str(local_path),
            )
            continue  # Skip this file, continue with others

        # Submit job to queue
        from arrtheaudio.core.job_models import JobPriority, JobSource

        job = await queue_manager.submit_job(
            file_path=local_path,
            priority=JobPriority.HIGH,  # Webhooks are high priority
            source=JobSource.SONARR,
            webhook_id=webhook_id,
            tmdb_id=payload.series_tmdb_id,
            original_language=payload.original_language,
            series_title=payload.series_title,
        )

        if job:
            job_ids.append(job.job_id)
            logger.info(
                "Job created for file",
                webhook_id=webhook_id,
                job_id=job.job_id,
                file=str(local_path),
            )

    # Check if any jobs were created
    if not job_ids:
        logger.error(
            "No jobs created from webhook",
            webhook_id=webhook_id,
            file_count=file_count,
        )
        return WebhookResponse(
            status="rejected",
            message="Failed to create jobs for any files",
        )

    logger.info(
        "Webhook processed successfully",
        webhook_id=webhook_id,
        files_queued=len(job_ids),
        total_files=file_count,
    )

    return WebhookResponse(
        status="accepted",
        webhook_id=webhook_id,
        job_ids=job_ids,
        files_queued=len(job_ids),
        message=f"Queued {len(job_ids)} file(s) for processing",
    )


@router.post("/webhook/radarr", response_model=WebhookResponse)
async def radarr_webhook(
    request: Request,
    payload: RadarrWebhookPayload,
):
    """Handle Radarr webhook (Phase 5: Job queue support).

    Args:
        request: FastAPI request
        payload: Radarr webhook payload

    Returns:
        Webhook response with job ID
    """
    app_state = request.app.state.arrtheaudio
    config = app_state.config
    queue_manager = app_state.queue_manager

    logger.info(
        "Radarr webhook received and validated",
        movie_title=payload.movie_title,
        movie_id=payload.movie.id,
        file_path=payload.movie_file_path,
        event_type=payload.event_type,
        tmdb_id=payload.movie_tmdb_id,
        year=payload.movie.year if hasattr(payload.movie, "year") else None,
        original_language=payload.original_language,
    )

    # Verify webhook signature if configured
    if config.api.webhook_secret:
        signature = request.headers.get("X-Webhook-Signature")
        if not signature:
            logger.warning("Missing webhook signature")
            raise HTTPException(status_code=401, detail="Missing signature")

        body = await request.body()
        if not verify_webhook_signature(body, signature, config.api.webhook_secret):
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Extract file path
    if not payload.movie_file_path:
        logger.warning("Missing movie file path in webhook")
        return WebhookResponse(
            status="rejected",
            message="Missing movie_file_path in payload",
        )

    # Map path from Arr to local filesystem
    path_mapper = PathMapper(config.path_mappings)
    local_path = path_mapper.map_path(payload.movie_file_path)

    # Validate file exists
    if not local_path.exists():
        logger.error("File not found after path mapping", local_path=str(local_path))
        return WebhookResponse(
            status="rejected",
            message=f"File not found: {local_path}",
        )

    # Generate webhook ID (for consistency with Sonarr)
    webhook_id = f"webhook_{uuid.uuid4().hex[:12]}"

    # Submit job to queue
    from arrtheaudio.core.job_models import JobPriority, JobSource

    job = await queue_manager.submit_job(
        file_path=local_path,
        priority=JobPriority.HIGH,  # Webhooks are high priority
        source=JobSource.RADARR,
        webhook_id=webhook_id,
        tmdb_id=payload.movie_tmdb_id,
        original_language=payload.original_language,
        movie_title=payload.movie_title,
    )

    if not job:
        logger.error("Failed to create job from webhook", file=str(local_path))
        return WebhookResponse(
            status="rejected",
            message="Failed to create job",
        )

    logger.info(
        "Job created for movie file",
        webhook_id=webhook_id,
        job_id=job.job_id,
        file=str(local_path),
    )

    return WebhookResponse(
        status="accepted",
        webhook_id=webhook_id,
        job_ids=[job.job_id],
        files_queued=1,
        message="File queued for processing",
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint (Phase 5: Job queue status).

    Args:
        request: FastAPI request

    Returns:
        Health status
    """
    app_state = request.app.state.arrtheaudio

    # Calculate uptime
    uptime = time.time() - app_state.start_time

    # Check tool availability
    import subprocess

    checks = {}

    try:
        subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            timeout=5,
            check=True,
        )
        checks["ffprobe"] = True
    except Exception:
        checks["ffprobe"] = False

    try:
        subprocess.run(
            ["mkvpropedit", "--version"],
            capture_output=True,
            timeout=5,
            check=True,
        )
        checks["mkvpropedit"] = True
    except Exception:
        checks["mkvpropedit"] = False

    checks["api"] = True

    # Check job queue system (Phase 5)
    queue_size = 0
    if app_state.queue_manager:
        try:
            stats = await app_state.queue_manager.get_queue_stats()
            queue_size = stats.get("queued", 0) + stats.get("running", 0)
            checks["job_queue"] = True
            checks["worker_pool"] = app_state.worker_pool.is_running if app_state.worker_pool else False
        except Exception:
            checks["job_queue"] = False
            checks["worker_pool"] = False
    else:
        checks["job_queue"] = False
        checks["worker_pool"] = False

    # Determine overall status
    required_checks = ["api", "ffprobe"]  # mkvpropedit optional if only using MP4
    if all(checks.get(k, False) for k in required_checks) and checks.get("job_queue", False):
        status = "healthy"
    elif checks["api"]:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        version=__version__,
        queue_size=queue_size,
        uptime_seconds=uptime,
        checks=checks,
    )


@router.post("/webhook/test")
async def test_webhook(request: Request):
    """Test webhook endpoint - accepts any payload and logs it.

    Useful for debugging webhook delivery and logging.

    Args:
        request: FastAPI request

    Returns:
        Echo of received data
    """
    body = await request.body()

    try:
        import json
        payload = json.loads(body.decode())
    except Exception:
        payload = body.decode() if body else None

    logger.info(
        "Test webhook received",
        content_type=request.headers.get("content-type"),
        payload=payload,
    )

    return {
        "status": "success",
        "message": "Test webhook received and logged",
        "received": payload,
    }


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "ArrTheAudio",
        "version": __version__,
        "description": "Automatic audio track fixer for Arr stack",
        "endpoints": {
            "health": "/health",
            "sonarr_webhook": "/webhook/sonarr",
            "radarr_webhook": "/webhook/radarr",
            "test_webhook": "/webhook/test",
            "docs": "/docs",
        },
    }

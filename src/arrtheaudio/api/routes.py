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


async def process_file_task(file_path: Path, config, job_id: str):
    """Background task to process a file.

    Args:
        file_path: Path to the file
        config: Application configuration
        job_id: Job identifier
    """
    logger.info("Starting background processing", file=str(file_path), job_id=job_id)

    try:
        pipeline = ProcessingPipeline(config)
        result = pipeline.process(file_path)

        logger.info(
            "Background processing complete",
            file=str(file_path),
            job_id=job_id,
            status=result.status,
        )

    except Exception as e:
        logger.exception("Background processing failed", file=str(file_path), job_id=job_id)


@router.post("/webhook/sonarr", response_model=WebhookResponse)
async def sonarr_webhook(
    request: Request,
    payload: SonarrWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """Handle Sonarr webhook.

    Args:
        request: FastAPI request
        payload: Sonarr webhook payload
        background_tasks: Background tasks

    Returns:
        Webhook response
    """
    app_state = request.app.state.arrtheaudio
    config = app_state.config

    logger.info(
        "Sonarr webhook received",
        series_title=payload.series_title,
        file_path=payload.episode_file_path,
        event_type=payload.event_type,
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
    if not payload.episode_file_path:
        logger.warning("Missing episode file path in webhook")
        return WebhookResponse(
            status="rejected", message="Missing episode_file_path in payload"
        )

    # Map path from Arr to local filesystem
    path_mapper = PathMapper(config.path_mappings)
    local_path = path_mapper.map_path(payload.episode_file_path)

    # Validate file exists
    if not local_path.exists():
        logger.error("File not found after path mapping", local_path=str(local_path))
        return WebhookResponse(
            status="rejected", message=f"File not found: {local_path}"
        )

    # Generate job ID and queue for processing
    job_id = str(uuid.uuid4())

    # Add to background tasks
    background_tasks.add_task(process_file_task, local_path, config, job_id)

    logger.info("File queued for processing", file=str(local_path), job_id=job_id)

    return WebhookResponse(
        status="accepted",
        job_id=job_id,
        message="File queued for processing",
    )


@router.post("/webhook/radarr", response_model=WebhookResponse)
async def radarr_webhook(
    request: Request,
    payload: RadarrWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """Handle Radarr webhook.

    Args:
        request: FastAPI request
        payload: Radarr webhook payload
        background_tasks: Background tasks

    Returns:
        Webhook response
    """
    app_state = request.app.state.arrtheaudio
    config = app_state.config

    logger.info(
        "Radarr webhook received",
        movie_title=payload.movie_title,
        file_path=payload.movie_file_path,
        event_type=payload.event_type,
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
            status="rejected", message="Missing movie_file_path in payload"
        )

    # Map path from Arr to local filesystem
    path_mapper = PathMapper(config.path_mappings)
    local_path = path_mapper.map_path(payload.movie_file_path)

    # Validate file exists
    if not local_path.exists():
        logger.error("File not found after path mapping", local_path=str(local_path))
        return WebhookResponse(
            status="rejected", message=f"File not found: {local_path}"
        )

    # Generate job ID and queue for processing
    job_id = str(uuid.uuid4())

    # Add to background tasks
    background_tasks.add_task(process_file_task, local_path, config, job_id)

    logger.info("File queued for processing", file=str(local_path), job_id=job_id)

    return WebhookResponse(
        status="accepted",
        job_id=job_id,
        message="File queued for processing",
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint.

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

    # Determine overall status
    if all(checks.values()):
        status = "healthy"
    elif checks["api"]:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        version=__version__,
        queue_size=0,  # TODO: Implement queue tracking
        uptime_seconds=uptime,
        checks=checks,
    )


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
            "docs": "/docs",
        },
    }

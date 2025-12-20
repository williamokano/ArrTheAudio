"""FastAPI application for ArrTheAudio daemon (Phase 5: Job Queue)."""

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from arrtheaudio import __version__
from arrtheaudio.api import routes, job_routes
from arrtheaudio.api.middleware import RequestLoggingMiddleware
from arrtheaudio.config import Config
from arrtheaudio.core.queue_manager import JobQueueManager
from arrtheaudio.core.worker_pool import WorkerPool
from arrtheaudio.core.pipeline import ProcessingPipeline
from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)

# Global app state for dependency injection
_app_state = None


def get_app_state():
    """Get global app state for dependency injection."""
    return _app_state


class AppState:
    """Application state container (Phase 5: Job Queue)."""

    def __init__(self, config: Config):
        self.config = config
        self.start_time = time.time()
        self.queue_manager = None  # Will be initialized in lifespan
        self.worker_pool = None  # Will be initialized in lifespan


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager (Phase 5: Job Queue)."""
    global _app_state

    logger.info("Starting ArrTheAudio daemon", version=__version__)

    app_state = app.state.arrtheaudio
    config = app_state.config

    # Initialize job queue database
    db_path = Path("/config/jobs.db")  # TODO: Make configurable
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing job queue system", db_path=str(db_path))

    # Create queue manager
    queue_manager = JobQueueManager(config, db_path)
    app_state.queue_manager = queue_manager

    # Create processing pipeline
    pipeline = ProcessingPipeline(config)

    # Create and start worker pool
    worker_pool = WorkerPool(config, queue_manager, pipeline)
    app_state.worker_pool = worker_pool

    # Set global state for dependencies
    _app_state = {
        "queue_manager": queue_manager,
        "worker_pool": worker_pool,
        "config": config,
    }

    # Start workers
    await worker_pool.start()

    logger.info(
        "Job queue system started",
        worker_count=config.processing.worker_count,
        max_mp4_concurrent=config.processing.max_mp4_concurrent,
    )

    # Startup complete
    yield

    # Shutdown logic
    logger.info("Shutting down ArrTheAudio daemon")

    # Stop worker pool
    if app_state.worker_pool:
        await app_state.worker_pool.stop()
        logger.info("Worker pool stopped")

    logger.info("Shutdown complete")


def create_app(config: Config) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        config: Application configuration

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="ArrTheAudio",
        description="Automatic audio track fixer for Arr stack",
        version=__version__,
        lifespan=lifespan,
    )

    # Add request logging middleware (BEFORE other middleware)
    app.add_middleware(RequestLoggingMiddleware)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure as needed
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store config in app state
    app.state.arrtheaudio = AppState(config)

    # Register exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors with detailed logging."""
        logger.error(
            "Webhook payload validation failed",
            path=request.url.path,
            method=request.method,
            errors=exc.errors(),
            body_preview=str(exc.body)[:500] if hasattr(exc, "body") else None,
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "status": "error",
                "message": "Invalid webhook payload",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch all unhandled exceptions."""
        logger.error(
            "Unhandled exception in webhook handler",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            error_type=type(exc).__name__,
            exc_info=True,  # Include traceback
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error",
            },
        )

    # Include routers
    app.include_router(routes.router)
    app.include_router(job_routes.router)  # Phase 5: Job management APIs

    logger.info(
        "FastAPI application created",
        version=__version__,
        api_port=config.api.port,
        webhook_auth=config.api.webhook_secret is not None,
        job_queue_enabled=True,
    )

    return app

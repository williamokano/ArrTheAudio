"""FastAPI application for ArrTheAudio daemon."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from arrtheaudio import __version__
from arrtheaudio.api import routes
from arrtheaudio.api.middleware import RequestLoggingMiddleware
from arrtheaudio.config import Config
from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class AppState:
    """Application state container."""

    def __init__(self, config: Config):
        self.config = config
        self.start_time = time.time()
        self.processing_queue = None  # Will be initialized by daemon
        self.worker_pool = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting ArrTheAudio daemon", version=__version__)

    # Startup logic
    yield

    # Shutdown logic
    logger.info("Shutting down ArrTheAudio daemon")


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

    logger.info(
        "FastAPI application created",
        version=__version__,
        api_port=config.api.port,
        webhook_auth=config.api.webhook_secret is not None,
    )

    return app

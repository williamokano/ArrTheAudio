"""FastAPI application for ArrTheAudio daemon."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from arrtheaudio import __version__
from arrtheaudio.api import routes
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

    # Include routers
    app.include_router(routes.router)

    logger.info(
        "FastAPI application created",
        version=__version__,
        api_port=config.api.port,
        webhook_auth=config.api.webhook_secret is not None,
    )

    return app

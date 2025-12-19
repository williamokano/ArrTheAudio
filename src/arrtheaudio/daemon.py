"""Daemon orchestrator for ArrTheAudio."""

import signal
import sys

import uvicorn

from arrtheaudio.api.app import create_app
from arrtheaudio.config import Config
from arrtheaudio.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


class DaemonOrchestrator:
    """Orchestrates the daemon lifecycle."""

    def __init__(self, config: Config):
        """Initialize daemon orchestrator.

        Args:
            config: Application configuration
        """
        self.config = config
        self.app = create_app(config)
        self.should_exit = False

    def handle_signal(self, signum, frame):
        """Handle shutdown signals.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info("Received shutdown signal", signal=signum)
        self.should_exit = True

    def run(self):
        """Run the daemon.

        This starts the FastAPI server using uvicorn.
        """
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        logger.info(
            "Starting daemon",
            host=self.config.api.host,
            port=self.config.api.port,
            workers=self.config.api.workers,
        )

        # Run uvicorn server
        try:
            uvicorn.run(
                self.app,
                host=self.config.api.host,
                port=self.config.api.port,
                log_level="info",  # Set log level for uvicorn
                access_log=False,  # Disabled - using custom middleware for webhook logging
            )
        except KeyboardInterrupt:
            logger.info("Daemon interrupted by user")
        except Exception as e:
            logger.exception("Daemon error", error=str(e))
            sys.exit(1)
        finally:
            logger.info("Daemon stopped")


def start_daemon(config: Config):
    """Start the daemon.

    Args:
        config: Application configuration
    """
    # Setup logging
    setup_logging(config.logging)

    # Create and run daemon
    daemon = DaemonOrchestrator(config)
    daemon.run()

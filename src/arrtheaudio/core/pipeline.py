"""Processing pipeline orchestrator."""

import time
from pathlib import Path
from typing import Optional

from arrtheaudio.config import Config
from arrtheaudio.core.analyzer import AudioAnalyzer
from arrtheaudio.core.detector import ContainerDetector
from arrtheaudio.core.executor import get_executor
from arrtheaudio.core.selector import TrackSelector
from arrtheaudio.models.file import ContainerType, ProcessResult
from arrtheaudio.models.metadata import MediaMetadata
from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class ProcessingPipeline:
    """Orchestrates the complete audio track processing pipeline."""

    def __init__(self, config: Config):
        """Initialize the pipeline with configuration.

        Args:
            config: Application configuration
        """
        self.config = config
        self.detector = ContainerDetector()
        self.analyzer = AudioAnalyzer()
        self.selector = TrackSelector(config)

    async def process(
        self, file_path: Path, metadata: Optional[MediaMetadata] = None
    ) -> ProcessResult:
        """Process a single file through the complete pipeline.

        Pipeline steps:
        1. Validation (file exists, readable)
        2. Container detection (MKV/MP4/unsupported)
        3. Audio analysis (extract tracks)
        4. Track selection (based on metadata + priority)
        5. Skip check (if already correct)
        6. Execution (modify metadata)
        7. Logging

        Args:
            file_path: Path to the file to process
            metadata: Optional media metadata (from Arr/TMDB/heuristics)

        Returns:
            ProcessResult with status and details
        """
        start_time = time.time()

        logger.info("Processing file", file=str(file_path))

        # Step 1: Validation
        if not file_path.exists():
            logger.error("File not found", file=str(file_path))
            return ProcessResult(
                status="error", file_path=file_path, error="File not found"
            )

        if not file_path.is_file():
            logger.error("Not a regular file", file=str(file_path))
            return ProcessResult(
                status="error", file_path=file_path, error="Not a regular file"
            )

        try:
            # Step 2: Container detection
            container_type = self.detector.detect(file_path)

            if container_type == ContainerType.UNSUPPORTED:
                logger.info(
                    "Skipping unsupported container",
                    file=str(file_path),
                )
                return ProcessResult(
                    status="skipped",
                    file_path=file_path,
                    reason="unsupported_container",
                )

            # Check if container type is enabled in config
            if container_type == ContainerType.MKV and not self.config.containers.mkv:
                logger.info("MKV support disabled", file=str(file_path))
                return ProcessResult(
                    status="skipped", file_path=file_path, reason="mkv_disabled"
                )

            if container_type == ContainerType.MP4 and not self.config.containers.mp4:
                logger.info("MP4 support disabled", file=str(file_path))
                return ProcessResult(
                    status="skipped", file_path=file_path, reason="mp4_disabled"
                )

            # Step 3: Audio analysis
            tracks = self.analyzer.analyze(file_path)

            if not tracks:
                logger.warning("No audio tracks found", file=str(file_path))
                return ProcessResult(
                    status="skipped", file_path=file_path, reason="no_audio_tracks"
                )

            # Step 4: Track selection
            selected_track = self.selector.select(tracks, file_path, metadata)

            if selected_track is None:
                logger.warning(
                    "No suitable track found",
                    file=str(file_path),
                    available_languages=[t.language for t in tracks],
                )
                return ProcessResult(
                    status="skipped", file_path=file_path, reason="no_matching_track"
                )

            # Step 5: Skip check (if already correct)
            if selected_track.is_default and self.config.execution.skip_if_correct:
                logger.info(
                    "Track already correct",
                    file=str(file_path),
                    track_index=selected_track.index,
                    language=selected_track.language,
                )
                return ProcessResult(
                    status="skipped",
                    file_path=file_path,
                    selected_track=selected_track,
                    reason="already_correct",
                )

            # Step 6: Execution
            if self.config.execution.dry_run:
                logger.info(
                    "DRY RUN: Would set track as default",
                    file=str(file_path),
                    track_index=selected_track.index,
                    language=selected_track.language,
                )
                return ProcessResult(
                    status="dry_run",
                    file_path=file_path,
                    selected_track=selected_track,
                    changed=False,
                )

            # Get executor and execute
            executor = get_executor(container_type.value)
            success = executor.set_default_audio(file_path, selected_track.index)

            duration_ms = int((time.time() - start_time) * 1000)

            if success:
                logger.info(
                    "File processed successfully",
                    file=str(file_path),
                    track_index=selected_track.index,
                    language=selected_track.language,
                    container=container_type.value,
                    duration_ms=duration_ms,
                )
                return ProcessResult(
                    status="success",
                    file_path=file_path,
                    selected_track=selected_track,
                    changed=True,
                )
            else:
                logger.error(
                    "Execution failed",
                    file=str(file_path),
                    track_index=selected_track.index,
                )
                return ProcessResult(
                    status="failed",
                    file_path=file_path,
                    selected_track=selected_track,
                    reason="execution_failed",
                )

        except Exception as e:
            logger.exception("Pipeline error", file=str(file_path), error=str(e))
            return ProcessResult(
                status="error", file_path=file_path, error=str(e)
            )

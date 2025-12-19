"""Executors for modifying audio track metadata."""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class AudioTrackExecutor(ABC):
    """Abstract base class for audio track executors."""

    @abstractmethod
    def set_default_audio(self, file_path: Path, track_index: int) -> bool:
        """Set the default audio track.

        Args:
            file_path: Path to the video file
            track_index: Index of the track to set as default (0-based)

        Returns:
            True if successful, False otherwise
        """
        pass


class MKVExecutor(AudioTrackExecutor):
    """Executor for MKV files using mkvpropedit."""

    def _get_audio_track_count(self, file_path: Path) -> int:
        """Get the number of audio tracks in the file.

        Args:
            file_path: Path to the MKV file

        Returns:
            Number of audio tracks
        """
        try:
            import json

            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-select_streams",
                "a",
                str(file_path),
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=30
            )

            data = json.loads(result.stdout)
            return len(data.get("streams", []))
        except Exception as e:
            logger.warning(
                "Failed to get track count, using default of 10",
                file=str(file_path),
                error=str(e),
            )
            return 10  # Fallback to reasonable default

    def set_default_audio(self, file_path: Path, track_index: int) -> bool:
        """Set default audio track in MKV file using mkvpropedit.

        This performs an in-place modification of the MKV file metadata.
        It first unsets all audio tracks as default, then sets the specified track.

        Args:
            file_path: Path to the MKV file
            track_index: Index of the track to set as default (0-based)

        Returns:
            True if successful, False otherwise
        """
        if not file_path.exists():
            logger.error("File not found", file=str(file_path))
            return False

        logger.info(
            "Setting default audio track (MKV)",
            file=str(file_path),
            track_index=track_index,
        )

        try:
            # Get the actual number of audio tracks
            track_count = self._get_audio_track_count(file_path)

            # Build mkvpropedit command
            cmd = ["mkvpropedit", str(file_path)]

            # Unset all audio tracks as default (only for tracks that exist)
            for i in range(track_count):
                cmd.extend(
                    ["--edit", f"track:a{i+1}", "--set", "flag-default=0"]
                )

            # Set the selected track as default (mkvpropedit uses 1-based indexing)
            cmd.extend(
                [
                    "--edit",
                    f"track:a{track_index + 1}",
                    "--set",
                    "flag-default=1",
                ]
            )

            logger.debug("Executing mkvpropedit", file=str(file_path), command=cmd)

            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )

            logger.info(
                "Successfully updated MKV",
                file=str(file_path),
                track_index=track_index,
            )
            return True

        except subprocess.TimeoutExpired:
            logger.error(
                "mkvpropedit timeout",
                file=str(file_path),
                timeout=60,
            )
            return False

        except subprocess.CalledProcessError as e:
            logger.error(
                "mkvpropedit failed",
                file=str(file_path),
                returncode=e.returncode,
                stderr=e.stderr,
            )
            return False

        except Exception as e:
            logger.error(
                "Unexpected error during mkvpropedit",
                file=str(file_path),
                error=str(e),
            )
            return False


class MP4Executor(AudioTrackExecutor):
    """Executor for MP4 files using ffmpeg remux.

    Unlike MKV which supports in-place metadata editing, MP4 requires
    a full remux with ffmpeg to change audio track disposition flags.

    Process:
    1. Check disk space (need ~2x file size)
    2. Create temp output file via ffmpeg remux
    3. Create backup of original
    4. Atomic replace original with temp
    5. Clean up backup on success
    """

    def __init__(self, timeout_seconds: int = 300):
        """Initialize MP4 executor.

        Args:
            timeout_seconds: Maximum time for ffmpeg operation
        """
        self.timeout_seconds = timeout_seconds

        # Check if ffmpeg is available
        import shutil
        self.ffmpeg_path = shutil.which("ffmpeg")
        if not self.ffmpeg_path:
            raise RuntimeError("ffmpeg not found in PATH - required for MP4 support")

    def _get_audio_track_count(self, file_path: Path) -> int:
        """Get the number of audio tracks in the file.

        Args:
            file_path: Path to the MP4 file

        Returns:
            Number of audio tracks
        """
        try:
            import json

            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-select_streams",
                "a",
                str(file_path),
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=30
            )

            data = json.loads(result.stdout)
            return len(data.get("streams", []))
        except Exception as e:
            logger.warning(
                "Failed to get audio track count",
                file=str(file_path),
                error=str(e),
            )
            return 0

    def _check_disk_space(self, file_path: Path) -> bool:
        """Check if sufficient disk space for remuxing.

        Need at least 2x file size (original + temp).

        Args:
            file_path: Path to the MP4 file

        Returns:
            True if sufficient space, False otherwise
        """
        import shutil

        file_size = file_path.stat().st_size
        required_space = file_size * 2

        stat = shutil.disk_usage(file_path.parent)
        available_space = stat.free

        if available_space < required_space:
            logger.error(
                "Insufficient disk space for MP4 processing",
                file=str(file_path),
                required_mb=round(required_space / 1024 / 1024, 2),
                available_mb=round(available_space / 1024 / 1024, 2),
            )
            return False

        logger.debug(
            "Disk space check passed",
            file=str(file_path),
            required_mb=round(required_space / 1024 / 1024, 2),
            available_mb=round(available_space / 1024 / 1024, 2),
        )
        return True

    def _build_ffmpeg_command(
        self, input_file: Path, output_file: Path, default_track_index: int, track_count: int
    ) -> list[str]:
        """Build ffmpeg command for remuxing with audio disposition.

        Args:
            input_file: Source MP4 file
            output_file: Destination file
            default_track_index: Audio track to mark as default (0-based)
            track_count: Total number of audio tracks

        Returns:
            Command list for subprocess
        """
        cmd = [
            self.ffmpeg_path,
            "-i", str(input_file),
            "-map", "0",  # Map all streams
            "-c", "copy",  # Copy codecs (no re-encode)
        ]

        # Set disposition for each audio track
        for i in range(track_count):
            disposition = "default" if i == default_track_index else "0"
            cmd.extend([f"-disposition:a:{i}", disposition])

        # Output options
        cmd.extend([
            "-movflags", "+faststart",  # Optimize for streaming
            "-y",  # Overwrite output
            str(output_file)
        ])

        return cmd

    def _cleanup_files(self, files: list[Path]) -> None:
        """Remove temporary/backup files.

        Args:
            files: List of file paths to remove
        """
        for file in files:
            try:
                if file.exists():
                    file.unlink()
                    logger.debug("Cleaned up file", file=str(file))
            except Exception as e:
                logger.warning("Failed to cleanup file", file=str(file), error=str(e))

    def set_default_audio(self, file_path: Path, track_index: int) -> bool:
        """Set default audio track in MP4 file using ffmpeg remux.

        This performs a full remux of the MP4 file with new audio dispositions.
        Uses atomic operations to prevent file corruption.

        Args:
            file_path: Path to the MP4 file
            track_index: Index of the track to set as default (0-based)

        Returns:
            True if successful, False otherwise
        """
        if not file_path.exists():
            logger.error("File not found", file=str(file_path))
            return False

        logger.info(
            "Setting default audio track (MP4 remux)",
            file=str(file_path),
            track_index=track_index,
        )

        # Check disk space
        if not self._check_disk_space(file_path):
            return False

        # Get audio track count
        track_count = self._get_audio_track_count(file_path)
        if track_count == 0:
            logger.error("No audio tracks found", file=str(file_path))
            return False

        if track_index >= track_count:
            logger.error(
                "Track index out of range",
                file=str(file_path),
                track_index=track_index,
                track_count=track_count,
            )
            return False

        # Create temp file in same directory (for atomic move)
        temp_file = file_path.parent / f".{file_path.name}.tmp"
        backup_file = file_path.parent / f"{file_path.name}.bak"

        try:
            # Build ffmpeg command
            cmd = self._build_ffmpeg_command(file_path, temp_file, track_index, track_count)

            logger.debug("Executing ffmpeg remux", file=str(file_path), command=cmd)

            # Execute ffmpeg remux
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            if result.returncode != 0:
                logger.error(
                    "ffmpeg failed",
                    file=str(file_path),
                    returncode=result.returncode,
                    stderr=result.stderr[:500],  # Truncate stderr
                )
                self._cleanup_files([temp_file])
                return False

            # Verify temp file was created and is valid
            if not temp_file.exists():
                logger.error("ffmpeg did not create output file", file=str(file_path))
                return False

            if temp_file.stat().st_size == 0:
                logger.error("ffmpeg created empty output file", file=str(file_path))
                self._cleanup_files([temp_file])
                return False

            # Verify temp file is not significantly smaller (indicates corruption)
            original_size = file_path.stat().st_size
            temp_size = temp_file.stat().st_size
            size_ratio = temp_size / original_size

            if size_ratio < 0.9:  # More than 10% smaller
                logger.error(
                    "ffmpeg output suspiciously small",
                    file=str(file_path),
                    original_mb=round(original_size / 1024 / 1024, 2),
                    temp_mb=round(temp_size / 1024 / 1024, 2),
                    ratio=round(size_ratio, 2),
                )
                self._cleanup_files([temp_file])
                return False

            # Create backup of original
            import shutil
            shutil.copy2(file_path, backup_file)
            logger.debug("Created backup", backup=str(backup_file))

            # Atomic replace
            temp_file.replace(file_path)
            logger.debug("Replaced original with remuxed file", file=str(file_path))

            # Remove backup on success
            self._cleanup_files([backup_file])

            logger.info(
                "Successfully updated MP4 file",
                file=str(file_path),
                track_index=track_index,
                original_mb=round(original_size / 1024 / 1024, 2),
                new_mb=round(temp_size / 1024 / 1024, 2),
            )
            return True

        except subprocess.TimeoutExpired:
            logger.error(
                "ffmpeg timeout",
                file=str(file_path),
                timeout=self.timeout_seconds,
            )
            self._cleanup_files([temp_file, backup_file])
            return False

        except Exception as e:
            logger.exception("MP4 processing failed", file=str(file_path), error=str(e))

            # Restore from backup if it exists
            if backup_file.exists():
                logger.info("Restoring from backup", file=str(file_path))
                import shutil
                try:
                    shutil.copy2(backup_file, file_path)
                    logger.info("Restored from backup successfully")
                except Exception as restore_error:
                    logger.error("Failed to restore from backup", error=str(restore_error))

            self._cleanup_files([temp_file, backup_file])
            return False


def get_executor(container_type: str, timeout_seconds: int = 300) -> AudioTrackExecutor:
    """Get the appropriate executor for a container type.

    Args:
        container_type: Container type ("mkv" or "mp4")
        timeout_seconds: Timeout for operations (only applies to MP4)

    Returns:
        Appropriate executor instance

    Raises:
        ValueError: If container type is not supported
    """
    if container_type.lower() == "mkv":
        return MKVExecutor()
    elif container_type.lower() == "mp4":
        return MP4Executor(timeout_seconds=timeout_seconds)
    else:
        raise ValueError(f"Unsupported container type: {container_type}")

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
    """Executor for MP4 files using ffmpeg.

    Note: MP4 support will be implemented in Phase 4.
    """

    def set_default_audio(self, file_path: Path, track_index: int) -> bool:
        """Set default audio track in MP4 file using ffmpeg.

        Args:
            file_path: Path to the MP4 file
            track_index: Index of the track to set as default (0-based)

        Returns:
            True if successful, False otherwise
        """
        logger.error(
            "MP4 support not yet implemented (Phase 4)",
            file=str(file_path),
        )
        return False


def get_executor(container_type: str) -> AudioTrackExecutor:
    """Get the appropriate executor for a container type.

    Args:
        container_type: Container type ("mkv" or "mp4")

    Returns:
        Appropriate executor instance

    Raises:
        ValueError: If container type is not supported
    """
    if container_type.lower() == "mkv":
        return MKVExecutor()
    elif container_type.lower() == "mp4":
        return MP4Executor()
    else:
        raise ValueError(f"Unsupported container type: {container_type}")

"""Container type detection using ffprobe."""

import json
import subprocess
from pathlib import Path

from arrtheaudio.models.file import ContainerType
from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class ContainerDetector:
    """Detect container format using ffprobe."""

    def detect(self, file_path: Path) -> ContainerType:
        """Detect container format of a video file.

        Args:
            file_path: Path to video file

        Returns:
            ContainerType enum value

        Raises:
            FileNotFoundError: If file doesn't exist
            subprocess.CalledProcessError: If ffprobe fails
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.debug("Detecting container type", file=str(file_path))

        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(file_path),
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=30
            )

            data = json.loads(result.stdout)
            format_name = data.get("format", {}).get("format_name", "")

            # Determine container type
            if "matroska" in format_name.lower():
                container = ContainerType.MKV
            elif "mp4" in format_name.lower() or "mov" in format_name.lower():
                container = ContainerType.MP4
            else:
                container = ContainerType.UNSUPPORTED
                logger.warning(
                    "Unsupported container format",
                    file=str(file_path),
                    format=format_name,
                )

            logger.debug(
                "Container detected",
                file=str(file_path),
                container=container.value,
                format_name=format_name,
            )

            return container

        except subprocess.TimeoutExpired:
            logger.error("ffprobe timeout", file=str(file_path), timeout=30)
            raise
        except subprocess.CalledProcessError as e:
            logger.error(
                "ffprobe failed",
                file=str(file_path),
                returncode=e.returncode,
                stderr=e.stderr,
            )
            raise
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse ffprobe output", file=str(file_path), error=str(e)
            )
            raise

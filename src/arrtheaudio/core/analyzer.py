"""Audio track analysis using ffprobe."""

import json
import subprocess
from pathlib import Path

from arrtheaudio.models.track import AudioTrack
from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class AudioAnalyzer:
    """Analyze audio tracks in video files using ffprobe."""

    def analyze(self, file_path: Path) -> list[AudioTrack]:
        """Extract audio track information from a video file.

        Args:
            file_path: Path to video file

        Returns:
            List of AudioTrack objects

        Raises:
            FileNotFoundError: If file doesn't exist
            subprocess.CalledProcessError: If ffprobe fails
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.debug("Analyzing audio tracks", file=str(file_path))

        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-select_streams",
                "a",  # Audio streams only
                str(file_path),
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=30
            )

            data = json.loads(result.stdout)
            streams = data.get("streams", [])

            tracks = []
            for idx, stream in enumerate(streams):
                # Extract track information
                track = AudioTrack(
                    index=idx,
                    stream_index=stream.get("index", idx),
                    codec=stream.get("codec_name", "unknown"),
                    language=stream.get("tags", {}).get("language", "und"),
                    title=stream.get("tags", {}).get("title"),
                    is_default=stream.get("disposition", {}).get("default", 0) == 1,
                    channels=stream.get("channels"),
                    bitrate=int(stream.get("bit_rate", 0))
                    if stream.get("bit_rate")
                    else None,
                )
                tracks.append(track)

            logger.info(
                "Audio tracks analyzed",
                file=str(file_path),
                track_count=len(tracks),
                languages=[t.language for t in tracks],
                default_track=next((i for i, t in enumerate(tracks) if t.is_default), None),
            )

            return tracks

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

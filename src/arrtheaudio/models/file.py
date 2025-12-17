"""Video file data models."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

from arrtheaudio.models.metadata import MediaMetadata
from arrtheaudio.models.track import AudioTrack


class ContainerType(Enum):
    """Supported container formats."""

    MKV = "mkv"
    MP4 = "mp4"
    UNSUPPORTED = "unsupported"


@dataclass
class VideoFile:
    """Represents a video file being processed."""

    path: Path
    container: ContainerType
    audio_tracks: list[AudioTrack]
    metadata: Optional[MediaMetadata] = None

    def __str__(self) -> str:
        """Human-readable representation."""
        return f"{self.path.name} ({self.container.value}, {len(self.audio_tracks)} audio tracks)"


@dataclass
class ProcessResult:
    """Result of processing a single file."""

    status: Literal["success", "skipped", "failed", "error", "dry_run"]
    file_path: Optional[Path] = None
    selected_track: Optional[AudioTrack] = None
    changed: bool = False
    reason: Optional[str] = None  # Reason for skip/failure
    error: Optional[str] = None  # Error message if failed

    def __str__(self) -> str:
        """Human-readable representation."""
        if self.status == "success":
            track_info = f"Track {self.selected_track.index}" if self.selected_track else "Unknown"
            return f"✓ {self.file_path.name}: {track_info} set as default"
        elif self.status == "skipped":
            return f"⊘ {self.file_path.name}: Skipped ({self.reason})"
        elif self.status == "dry_run":
            track_info = f"Track {self.selected_track.index}" if self.selected_track else "Unknown"
            return f"⊙ {self.file_path.name}: Would set {track_info} (dry run)"
        else:
            return f"✗ {self.file_path.name}: Failed ({self.error or self.reason})"

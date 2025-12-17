"""Audio track data models."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AudioTrack:
    """Represents an audio track in a video file."""

    index: int  # Track index (0-based)
    stream_index: int  # FFprobe stream index
    codec: str  # Codec name (e.g., "aac", "ac3")
    language: str  # ISO 639-2 language code (e.g., "eng", "jpn")
    title: Optional[str] = None  # Track title/name
    is_default: bool = False  # Whether this is the default track
    channels: Optional[int] = None  # Number of audio channels
    bitrate: Optional[int] = None  # Bitrate in bits/second

    def __str__(self) -> str:
        """Human-readable representation."""
        default_marker = " [DEFAULT]" if self.is_default else ""
        title_part = f" ({self.title})" if self.title else ""
        return f"Track {self.index}: {self.language} {self.codec}{title_part}{default_marker}"

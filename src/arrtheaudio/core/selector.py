"""Track selection logic with path-based priority resolution."""

from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

from arrtheaudio.config import Config, PathOverride
from arrtheaudio.models.metadata import MediaMetadata
from arrtheaudio.models.track import AudioTrack
from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class PriorityResolver:
    """Resolve language priority based on file path and configuration."""

    def __init__(self, config: Config):
        """Initialize priority resolver.

        Args:
            config: Application configuration
        """
        self.global_priority = config.language_priority
        self.overrides = config.path_overrides

    def resolve_priority(self, file_path: Path) -> list[str]:
        """Resolve language priority for a file based on path overrides.

        Checks path overrides in order. First matching pattern wins.
        Falls back to global priority if no override matches.

        Args:
            file_path: Path to the file

        Returns:
            List of language codes in priority order
        """
        file_path_str = str(file_path)

        # Check each override in order (first match wins)
        for override in self.overrides:
            pattern = override.path

            # Use fnmatch for glob pattern matching
            if fnmatch(file_path_str, pattern):
                logger.info(
                    "Using path-specific language priority",
                    file=file_path_str,
                    pattern=pattern,
                    priority=override.language_priority,
                )
                return override.language_priority

        # No override matched, use global priority
        logger.debug(
            "Using global language priority",
            file=file_path_str,
            priority=self.global_priority,
        )
        return self.global_priority


class TrackSelector:
    """Select the correct audio track based on metadata and priorities."""

    def __init__(self, config: Config):
        """Initialize track selector.

        Args:
            config: Application configuration
        """
        self.config = config
        self.priority_resolver = PriorityResolver(config)

    def select(
        self,
        tracks: list[AudioTrack],
        file_path: Path,
        metadata: Optional[MediaMetadata] = None,
    ) -> Optional[AudioTrack]:
        """Select the appropriate audio track.

        Selection logic:
        1. If original language is known AND present in tracks → select it
        2. Else, select first match from language_priority (global or path-specific)
        3. Else, return None (no suitable track found)

        Args:
            tracks: List of audio tracks
            file_path: Path to the file (for priority resolution)
            metadata: Optional media metadata

        Returns:
            Selected AudioTrack or None if no suitable track found
        """
        if not tracks:
            logger.warning("No audio tracks found", file=str(file_path))
            return None

        logger.debug(
            "Selecting audio track",
            file=str(file_path),
            available_languages=[t.language for t in tracks],
            original_language=metadata.original_language if metadata else None,
        )

        # Rule 1: Prefer original language if known
        if metadata and metadata.original_language:
            for track in tracks:
                if track.language == metadata.original_language:
                    logger.info(
                        "Selected original language track",
                        file=str(file_path),
                        language=track.language,
                        track_index=track.index,
                        selection_method="original_language",
                        metadata_source=metadata.source,
                    )
                    return track

            logger.debug(
                "Original language not found in tracks",
                file=str(file_path),
                original_language=metadata.original_language,
                available_languages=[t.language for t in tracks],
            )

        # Rule 2: Use priority list (global or path-specific)
        priority = self.priority_resolver.resolve_priority(file_path)

        for lang in priority:
            for track in tracks:
                if track.language == lang:
                    logger.info(
                        "Selected track from priority list",
                        file=str(file_path),
                        language=lang,
                        track_index=track.index,
                        selection_method="priority_list",
                        priority=priority,
                    )
                    return track

        # Rule 3: No match found
        logger.warning(
            "No matching track found",
            file=str(file_path),
            available_languages=[t.language for t in tracks],
            priority=priority,
            original_language=metadata.original_language if metadata else None,
        )
        return None

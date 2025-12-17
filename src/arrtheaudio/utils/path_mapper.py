"""Path mapping utility for Arr integration."""

from pathlib import Path
from typing import List, Tuple

from arrtheaudio.config import PathMapping
from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class PathMapper:
    """Map remote Arr paths to local filesystem paths."""

    def __init__(self, mappings: List[PathMapping]):
        """Initialize path mapper.

        Args:
            mappings: List of PathMapping objects
        """
        self.mappings = [(Path(m.remote), Path(m.local)) for m in mappings]

    def map_path(self, remote_path: str | Path) -> Path:
        """Translate Arr path to local filesystem path.

        Tries each mapping in order. First matching prefix wins.
        If no mapping matches, returns the original path.

        Args:
            remote_path: Path from Sonarr/Radarr

        Returns:
            Local filesystem path

        Example:
            mapper = PathMapper([
                PathMapping(remote="/tv", local="/data/media/tv"),
                PathMapping(remote="/movies", local="/data/media/movies"),
            ])

            mapper.map_path("/tv/Show/S01E01.mkv")
            # Returns: /data/media/tv/Show/S01E01.mkv
        """
        remote = Path(remote_path)

        # Try each mapping in order (first match wins)
        for remote_prefix, local_prefix in self.mappings:
            try:
                # Check if remote_path starts with remote_prefix
                relative = remote.relative_to(remote_prefix)

                # Build local path: local_prefix + relative_part
                local_path = local_prefix / relative

                logger.debug(
                    "Path mapped",
                    remote_path=str(remote_path),
                    remote_prefix=str(remote_prefix),
                    local_prefix=str(local_prefix),
                    local_path=str(local_path),
                )

                return local_path

            except ValueError:
                # Not a match, continue to next mapping
                continue

        # No mapping found, return original path
        logger.warning(
            "No path mapping found, using original path",
            remote_path=str(remote_path),
            configured_mappings=[(str(r), str(l)) for r, l in self.mappings],
        )
        return remote

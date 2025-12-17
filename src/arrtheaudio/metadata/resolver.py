"""Metadata resolver that orchestrates resolution from multiple sources."""

from pathlib import Path
from typing import Optional

import structlog

from arrtheaudio.models.metadata import MediaMetadata
from arrtheaudio.metadata.heuristic import parse_filename
from arrtheaudio.metadata.tmdb import TMDBClient

logger = structlog.get_logger(__name__)


class MetadataResolver:
    """Orchestrates metadata resolution from multiple sources."""

    def __init__(self, tmdb_client: Optional[TMDBClient], config):
        """Initialize metadata resolver.

        Args:
            tmdb_client: TMDB API client (None if TMDB disabled)
            config: Application configuration
        """
        self.tmdb_client = tmdb_client
        self.config = config
        self.tmdb_enabled = config.tmdb.enabled if hasattr(config, "tmdb") else False
        logger.info(
            "Initialized metadata resolver",
            tmdb_enabled=self.tmdb_enabled,
        )

    async def resolve(
        self,
        file_path: Path,
        arr_metadata: Optional[dict] = None,
    ) -> MediaMetadata:
        """Resolve metadata from all available sources.

        Resolution order:
        1. Arr metadata (from webhook) + TMDB lookup
        2. Filename heuristics + TMDB lookup
        3. None (fallback to priority list)

        Args:
            file_path: Path to the video file
            arr_metadata: Metadata from Sonarr/Radarr webhook

        Returns:
            MediaMetadata with original_language if found
        """
        logger.debug(
            "Resolving metadata",
            file=str(file_path),
            has_arr_metadata=arr_metadata is not None,
        )

        # Try Arr metadata first
        if arr_metadata and self.tmdb_enabled:
            if metadata := await self._resolve_from_arr(arr_metadata):
                logger.info(
                    "Resolved metadata from Arr + TMDB",
                    file=str(file_path),
                    metadata=str(metadata),
                )
                return metadata

        # Try filename heuristics
        if self.tmdb_enabled:
            if metadata := await self._resolve_from_filename(file_path):
                logger.info(
                    "Resolved metadata from filename + TMDB",
                    file=str(file_path),
                    metadata=str(metadata),
                )
                return metadata

        # No metadata found - return empty
        logger.debug(
            "No metadata resolved, will use priority list",
            file=str(file_path),
        )
        return MediaMetadata(original_language=None, source="none")

    async def _resolve_from_arr(
        self,
        arr_metadata: dict,
    ) -> Optional[MediaMetadata]:
        """Resolve using Arr metadata + TMDB lookup.

        Expected arr_metadata keys:
        - media_type: 'tv' or 'movie'
        - tmdb_id: TMDB ID (optional)
        - tvdb_id: TVDB ID (optional, for TV shows)
        - title: Show/movie title (optional)

        Args:
            arr_metadata: Metadata from Sonarr/Radarr webhook

        Returns:
            MediaMetadata if successful, None otherwise
        """
        if not self.tmdb_client:
            return None

        # Extract IDs from Arr
        tmdb_id = arr_metadata.get("tmdb_id")
        tvdb_id = arr_metadata.get("tvdb_id")
        media_type = arr_metadata.get("media_type")  # "tv" or "movie"
        title = arr_metadata.get("title")

        if not media_type:
            logger.warning("Arr metadata missing media_type")
            return None

        # Lookup on TMDB
        try:
            if media_type == "tv":
                tmdb_data = await self.tmdb_client.get_tv_show(
                    tvdb_id=tvdb_id,
                    tmdb_id=tmdb_id,
                )
            else:
                if not tmdb_id:
                    logger.warning("Movie missing tmdb_id")
                    return None
                tmdb_data = await self.tmdb_client.get_movie(tmdb_id)

            if tmdb_data:
                return self._create_metadata_from_tmdb(
                    tmdb_data,
                    media_type,
                    source="tmdb",
                )

        except Exception as e:
            logger.warning(
                "Failed to resolve metadata from Arr + TMDB",
                error=str(e),
                media_type=media_type,
                tmdb_id=tmdb_id,
                tvdb_id=tvdb_id,
            )

        return None

    async def _resolve_from_filename(
        self,
        file_path: Path,
    ) -> Optional[MediaMetadata]:
        """Parse filename and lookup on TMDB.

        Args:
            file_path: Path to video file

        Returns:
            MediaMetadata if successful, None otherwise
        """
        if not self.tmdb_client:
            return None

        # Parse filename using heuristics
        parsed = parse_filename(file_path.name)

        if not parsed:
            logger.debug("Could not parse filename", file=file_path.name)
            return None

        media_type = parsed["type"]
        title = parsed["title"]
        year = parsed.get("year")

        logger.debug(
            "Parsed filename",
            title=title,
            media_type=media_type,
            year=year,
        )

        # Search TMDB
        try:
            if media_type == "tv":
                results = await self.tmdb_client.search_tv(title, year=year)
            else:
                results = await self.tmdb_client.search_movie(title, year=year)

            if not results:
                logger.debug(
                    "No TMDB search results",
                    title=title,
                    media_type=media_type,
                )
                return None

            # Use first result (best match)
            best_match = results[0]
            tmdb_id = best_match["id"]

            # Fetch full details
            if media_type == "tv":
                tmdb_data = await self.tmdb_client.get_tv_show(tmdb_id=tmdb_id)
            else:
                tmdb_data = await self.tmdb_client.get_movie(tmdb_id)

            if tmdb_data:
                return self._create_metadata_from_tmdb(
                    tmdb_data,
                    media_type,
                    source="heuristic",
                )

        except Exception as e:
            logger.warning(
                "Failed to resolve metadata from filename + TMDB",
                error=str(e),
                title=title,
                media_type=media_type,
            )

        return None

    def _create_metadata_from_tmdb(
        self,
        tmdb_data: dict,
        media_type: str,
        source: str,
    ) -> MediaMetadata:
        """Create MediaMetadata from TMDB API response.

        Args:
            tmdb_data: TMDB API response data
            media_type: 'tv' or 'movie'
            source: Source of metadata ('tmdb' or 'heuristic')

        Returns:
            MediaMetadata instance
        """
        # Extract year from first_air_date or release_date
        year = None
        if media_type == "tv":
            if first_air_date := tmdb_data.get("first_air_date"):
                year = int(first_air_date[:4])
        else:
            if release_date := tmdb_data.get("release_date"):
                year = int(release_date[:4])

        return MediaMetadata(
            media_type=media_type,
            title=tmdb_data.get("name") or tmdb_data.get("title"),
            year=year,
            tmdb_id=tmdb_data.get("id"),
            original_language=tmdb_data.get("original_language"),
            source=source,
        )

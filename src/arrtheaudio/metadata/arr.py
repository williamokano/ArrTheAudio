"""Arr (Sonarr/Radarr) metadata parser.

This module extracts metadata from Sonarr and Radarr webhook payloads
for use in language resolution and TMDB lookups.
"""

from typing import Optional

from arrtheaudio.api.models import SonarrWebhookPayload, RadarrWebhookPayload
from arrtheaudio.models.metadata import MediaMetadata
from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class ArrMetadataParser:
    """Parser for Sonarr and Radarr webhook metadata."""

    def parse_sonarr(self, payload: SonarrWebhookPayload) -> MediaMetadata:
        """Parse Sonarr webhook payload to extract metadata.

        Args:
            payload: Sonarr webhook payload

        Returns:
            MediaMetadata with extracted information
        """
        logger.debug(
            "Parsing Sonarr metadata",
            series_title=payload.series.title,
            tvdb_id=payload.series.tvdbId,
        )

        return MediaMetadata(
            media_type="tv",
            title=payload.series.title,
            year=None,  # Sonarr doesn't provide series year in webhook
            tmdb_id=None,  # Sonarr uses TVDB, not TMDB
            tvdb_id=payload.series.tvdbId,
            original_language=None,  # Will be resolved via TMDB lookup
        )

    def parse_radarr(self, payload: RadarrWebhookPayload) -> MediaMetadata:
        """Parse Radarr webhook payload to extract metadata.

        Args:
            payload: Radarr webhook payload

        Returns:
            MediaMetadata with extracted information
        """
        logger.debug(
            "Parsing Radarr metadata",
            movie_title=payload.movie.title,
            tmdb_id=payload.movie.tmdbId,
        )

        return MediaMetadata(
            media_type="movie",
            title=payload.movie.title,
            year=payload.movie.year,
            tmdb_id=payload.movie.tmdbId,
            tvdb_id=None,
            original_language=None,  # Will be resolved via TMDB lookup
        )

    def extract_file_path_sonarr(self, payload: SonarrWebhookPayload) -> Optional[str]:
        """Extract file path from Sonarr webhook.

        Args:
            payload: Sonarr webhook payload

        Returns:
            File path if available, None otherwise
        """
        if payload.episodeFile:
            return payload.episodeFile.path
        return None

    def extract_file_path_radarr(self, payload: RadarrWebhookPayload) -> Optional[str]:
        """Extract file path from Radarr webhook.

        Args:
            payload: Radarr webhook payload

        Returns:
            File path if available, None otherwise
        """
        if payload.movieFile:
            return payload.movieFile.relativePath
        return None

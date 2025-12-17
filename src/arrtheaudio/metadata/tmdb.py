"""TMDB API client with caching and retry logic."""

from typing import Optional

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from arrtheaudio.metadata.cache import TMDBCache

logger = structlog.get_logger(__name__)


class TMDBError(Exception):
    """Base exception for TMDB API errors."""

    pass


class TMDBClient:
    """TMDB API client with rate limiting and caching."""

    def __init__(self, api_key: str, cache: TMDBCache):
        """Initialize TMDB client.

        Args:
            api_key: TMDB API key
            cache: Cache instance for API responses
        """
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.cache = cache
        self.client = httpx.AsyncClient(timeout=10.0)
        logger.info("Initialized TMDB client")

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def get_tv_show(
        self,
        tvdb_id: Optional[int] = None,
        tmdb_id: Optional[int] = None,
    ) -> Optional[dict]:
        """Get TV show details from TMDB.

        Args:
            tvdb_id: TVDB ID (will be converted to TMDB ID)
            tmdb_id: Direct TMDB ID

        Returns:
            TV show details including original_language, or None if not found
        """
        if not tvdb_id and not tmdb_id:
            logger.warning("get_tv_show called without tvdb_id or tmdb_id")
            return None

        # Generate cache key
        cache_key = f"tv_{tmdb_id or f'tvdb_{tvdb_id}'}"

        # Check cache first
        if cached := self.cache.get(cache_key):
            logger.debug("TMDB cache hit for TV show", cache_key=cache_key)
            return cached

        # If only TVDB ID, need to find TMDB ID first
        if tvdb_id and not tmdb_id:
            logger.debug("Converting TVDB ID to TMDB ID", tvdb_id=tvdb_id)
            tmdb_id = await self._find_tmdb_from_tvdb(tvdb_id)

        if not tmdb_id:
            logger.warning("Could not find TMDB ID", tvdb_id=tvdb_id)
            return None

        # Fetch from API
        try:
            response = await self.client.get(
                f"{self.base_url}/tv/{tmdb_id}",
                params={"api_key": self.api_key},
            )
            response.raise_for_status()

            data = response.json()
            logger.info(
                "Fetched TV show from TMDB",
                tmdb_id=tmdb_id,
                title=data.get("name"),
                original_language=data.get("original_language"),
            )

            # Cache result
            self.cache.set(cache_key, data)

            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("TV show not found on TMDB", tmdb_id=tmdb_id)
                return None
            logger.error(
                "TMDB API error",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise TMDBError(f"TMDB API error: {e}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def get_movie(self, tmdb_id: int) -> Optional[dict]:
        """Get movie details from TMDB.

        Args:
            tmdb_id: TMDB movie ID

        Returns:
            Movie details including original_language, or None if not found
        """
        cache_key = f"movie_{tmdb_id}"

        # Check cache first
        if cached := self.cache.get(cache_key):
            logger.debug("TMDB cache hit for movie", cache_key=cache_key)
            return cached

        # Fetch from API
        try:
            response = await self.client.get(
                f"{self.base_url}/movie/{tmdb_id}",
                params={"api_key": self.api_key},
            )
            response.raise_for_status()

            data = response.json()
            logger.info(
                "Fetched movie from TMDB",
                tmdb_id=tmdb_id,
                title=data.get("title"),
                original_language=data.get("original_language"),
            )

            # Cache result
            self.cache.set(cache_key, data)

            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("Movie not found on TMDB", tmdb_id=tmdb_id)
                return None
            logger.error(
                "TMDB API error",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise TMDBError(f"TMDB API error: {e}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def search_tv(
        self,
        query: str,
        year: Optional[int] = None,
    ) -> list[dict]:
        """Search for TV shows on TMDB.

        Args:
            query: Search query (show title)
            year: Optional year to filter results

        Returns:
            List of TV show search results (may be empty)
        """
        params = {
            "api_key": self.api_key,
            "query": query,
        }
        if year:
            params["first_air_date_year"] = year

        try:
            response = await self.client.get(
                f"{self.base_url}/search/tv",
                params=params,
            )
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])
            logger.info(
                "Searched TMDB for TV show",
                query=query,
                year=year,
                result_count=len(results),
            )
            return results

        except httpx.HTTPStatusError as e:
            logger.error(
                "TMDB search error",
                status_code=e.response.status_code,
                query=query,
                error=str(e),
            )
            raise TMDBError(f"TMDB search error: {e}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def search_movie(
        self,
        query: str,
        year: Optional[int] = None,
    ) -> list[dict]:
        """Search for movies on TMDB.

        Args:
            query: Search query (movie title)
            year: Optional year to filter results

        Returns:
            List of movie search results (may be empty)
        """
        params = {
            "api_key": self.api_key,
            "query": query,
        }
        if year:
            params["year"] = year

        try:
            response = await self.client.get(
                f"{self.base_url}/search/movie",
                params=params,
            )
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])
            logger.info(
                "Searched TMDB for movie",
                query=query,
                year=year,
                result_count=len(results),
            )
            return results

        except httpx.HTTPStatusError as e:
            logger.error(
                "TMDB search error",
                status_code=e.response.status_code,
                query=query,
                error=str(e),
            )
            raise TMDBError(f"TMDB search error: {e}") from e

    async def _find_tmdb_from_tvdb(self, tvdb_id: int) -> Optional[int]:
        """Convert TVDB ID to TMDB ID using external ID lookup.

        Args:
            tvdb_id: TVDB ID

        Returns:
            TMDB ID if found, None otherwise
        """
        cache_key = f"tvdb_to_tmdb_{tvdb_id}"

        # Check cache for conversion
        if cached := self.cache.get(cache_key):
            logger.debug("TVDB→TMDB cache hit", tvdb_id=tvdb_id)
            return cached.get("tmdb_id")

        try:
            response = await self.client.get(
                f"{self.base_url}/find/{tvdb_id}",
                params={
                    "api_key": self.api_key,
                    "external_source": "tvdb_id",
                },
            )
            response.raise_for_status()

            data = response.json()
            if results := data.get("tv_results", []):
                tmdb_id = results[0]["id"]
                logger.info(
                    "Converted TVDB ID to TMDB ID",
                    tvdb_id=tvdb_id,
                    tmdb_id=tmdb_id,
                )

                # Cache the conversion
                self.cache.set(cache_key, {"tmdb_id": tmdb_id})

                return tmdb_id

            logger.warning("No TMDB results for TVDB ID", tvdb_id=tvdb_id)
            return None

        except httpx.HTTPStatusError as e:
            logger.error(
                "TVDB→TMDB conversion error",
                tvdb_id=tvdb_id,
                status_code=e.response.status_code,
                error=str(e),
            )
            return None

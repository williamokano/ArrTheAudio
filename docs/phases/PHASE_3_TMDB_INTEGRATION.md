# Phase 3: TMDB Integration

**Status:** 🚧 Planned
**Goal:** Automatically detect original language from TMDB API
**Estimated Duration:** 1-2 weeks

## Overview

Phase 3 adds automatic original language detection using The Movie Database (TMDB) API. Instead of relying solely on language priority lists, ArrTheAudio will look up the original language of TV shows and movies and prioritize that track when available.

## Features

### 1. TMDB API Client
- HTTP client for TMDB API v3
- Rate limiting and retry logic
- Error handling for API failures
- Support for TV shows and movies

### 2. SQLite Cache
- Local caching of TMDB lookups
- Configurable TTL (default: 30 days)
- Cache invalidation strategies
- Database migrations

### 3. Metadata Resolution
- Automatic lookup chain:
  1. Sonarr/Radarr metadata (TVDB ID, TMDB ID)
  2. TMDB API lookup
  3. Filename heuristics
  4. Fallback to priority list
- Support for both TVDB ID → TMDB ID conversion
- Direct TMDB ID lookups from Radarr

### 4. Enhanced Track Selection
- Original language takes precedence over priority list
- Graceful fallback when API unavailable
- Logging of metadata sources

## Technical Details

### File Structure

```
src/arrtheaudio/metadata/
├── __init__.py
├── arr.py              # Existing (Phase 2)
├── tmdb.py             # NEW - TMDB API client
├── cache.py            # NEW - SQLite cache
├── heuristic.py        # NEW - Filename parsing
└── resolver.py         # NEW - Metadata resolution orchestrator
```

### TMDB Client (tmdb.py)

```python
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

class TMDBClient:
    """TMDB API client with rate limiting and caching."""

    def __init__(self, api_key: str, cache: TMDBCache):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.cache = cache
        self.client = httpx.AsyncClient(timeout=10.0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_tv_show(self, tvdb_id: Optional[int] = None,
                          tmdb_id: Optional[int] = None) -> Optional[dict]:
        """Get TV show details from TMDB.

        Args:
            tvdb_id: TVDB ID (will be converted to TMDB ID)
            tmdb_id: Direct TMDB ID

        Returns:
            TV show details including original_language
        """
        # Check cache first
        cache_key = f"tv_{tmdb_id or tvdb_id}"
        if cached := self.cache.get(cache_key):
            return cached

        # If only TVDB ID, need to find TMDB ID first
        if tvdb_id and not tmdb_id:
            tmdb_id = await self._find_tmdb_from_tvdb(tvdb_id)

        if not tmdb_id:
            return None

        # Fetch from API
        response = await self.client.get(
            f"{self.base_url}/tv/{tmdb_id}",
            params={"api_key": self.api_key}
        )
        response.raise_for_status()

        data = response.json()

        # Cache result
        self.cache.set(cache_key, data)

        return data

    async def get_movie(self, tmdb_id: int) -> Optional[dict]:
        """Get movie details from TMDB."""
        # Similar implementation
        pass

    async def _find_tmdb_from_tvdb(self, tvdb_id: int) -> Optional[int]:
        """Convert TVDB ID to TMDB ID using external ID lookup."""
        response = await self.client.get(
            f"{self.base_url}/find/{tvdb_id}",
            params={
                "api_key": self.api_key,
                "external_source": "tvdb_id"
            }
        )
        response.raise_for_status()

        data = response.json()
        if results := data.get("tv_results", []):
            return results[0]["id"]

        return None
```

### Cache (cache.py)

```python
import sqlite3
import json
import time
from pathlib import Path
from typing import Optional

class TMDBCache:
    """SQLite-based cache for TMDB API responses."""

    def __init__(self, db_path: Path, ttl_days: int = 30):
        self.db_path = db_path
        self.ttl_seconds = ttl_days * 24 * 60 * 60
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires
            ON cache(expires_at)
        """)
        conn.commit()
        conn.close()

    def get(self, key: str) -> Optional[dict]:
        """Get cached value if not expired."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT value FROM cache WHERE key = ? AND expires_at > ?",
            (key, int(time.time()))
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row[0])
        return None

    def set(self, key: str, value: dict):
        """Cache value with TTL."""
        conn = sqlite3.connect(self.db_path)
        expires_at = int(time.time()) + self.ttl_seconds
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), expires_at)
        )
        conn.commit()
        conn.close()

    def cleanup_expired(self):
        """Remove expired entries."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM cache WHERE expires_at < ?", (int(time.time()),))
        conn.commit()
        conn.close()
```

### Metadata Resolver (resolver.py)

```python
from typing import Optional
from pathlib import Path
from arrtheaudio.models.metadata import MediaMetadata

class MetadataResolver:
    """Orchestrates metadata resolution from multiple sources."""

    def __init__(self, tmdb_client: TMDBClient, config):
        self.tmdb_client = tmdb_client
        self.config = config

    async def resolve(self,
                      file_path: Path,
                      arr_metadata: Optional[dict] = None) -> MediaMetadata:
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
        # Try Arr metadata first
        if arr_metadata:
            if metadata := await self._resolve_from_arr(arr_metadata):
                return metadata

        # Try filename heuristics
        if metadata := await self._resolve_from_filename(file_path):
            return metadata

        # No metadata found - return empty
        return MediaMetadata(original_language=None, source="none")

    async def _resolve_from_arr(self, arr_metadata: dict) -> Optional[MediaMetadata]:
        """Resolve using Arr metadata + TMDB lookup."""
        # Extract IDs from Arr
        tmdb_id = arr_metadata.get("tmdb_id")
        tvdb_id = arr_metadata.get("tvdb_id")
        media_type = arr_metadata.get("media_type")  # "tv" or "movie"

        # Lookup on TMDB
        if media_type == "tv":
            tmdb_data = await self.tmdb_client.get_tv_show(
                tvdb_id=tvdb_id,
                tmdb_id=tmdb_id
            )
        else:
            tmdb_data = await self.tmdb_client.get_movie(tmdb_id)

        if tmdb_data:
            return MediaMetadata(
                media_type=media_type,
                title=tmdb_data.get("name") or tmdb_data.get("title"),
                year=self._extract_year(tmdb_data),
                tmdb_id=tmdb_data.get("id"),
                original_language=tmdb_data.get("original_language"),
                source="tmdb"
            )

        return None

    async def _resolve_from_filename(self, file_path: Path) -> Optional[MediaMetadata]:
        """Parse filename and lookup on TMDB."""
        # Parse filename using heuristics
        parsed = parse_filename(file_path.name)

        if not parsed:
            return None

        # Search TMDB
        if parsed["type"] == "tv":
            results = await self.tmdb_client.search_tv(
                parsed["title"],
                year=parsed.get("year")
            )
        else:
            results = await self.tmdb_client.search_movie(
                parsed["title"],
                year=parsed.get("year")
            )

        # Use first result (best match)
        if results:
            return await self._resolve_from_arr({
                "tmdb_id": results[0]["id"],
                "media_type": parsed["type"]
            })

        return None
```

### Heuristic Parser (heuristic.py)

```python
import re
from typing import Optional

def parse_filename(filename: str) -> Optional[dict]:
    """Parse filename to extract title, year, season/episode.

    Examples:
        "Show.Name.S01E01.1080p.mkv" → {"title": "Show Name", "type": "tv", ...}
        "Movie.Name.2023.1080p.mkv" → {"title": "Movie Name", "year": 2023, "type": "movie"}

    Returns:
        Parsed metadata or None if parsing fails
    """
    # TV show pattern: Show.Name.S01E01
    tv_pattern = r"^(.+?)\.S(\d+)E(\d+)"
    if match := re.match(tv_pattern, filename, re.IGNORECASE):
        title = match.group(1).replace(".", " ")
        return {
            "title": title,
            "season": int(match.group(2)),
            "episode": int(match.group(3)),
            "type": "tv"
        }

    # Movie pattern: Movie.Name.2023
    movie_pattern = r"^(.+?)\.(\d{4})\."
    if match := re.match(movie_pattern, filename):
        title = match.group(1).replace(".", " ")
        return {
            "title": title,
            "year": int(match.group(2)),
            "type": "movie"
        }

    return None
```

## Configuration

Add to `config.yaml`:

```yaml
tmdb:
  enabled: true
  api_key: "${TMDB_API_KEY}"
  cache_ttl_days: 30
  cache_path: /config/tmdb_cache.db
```

Add to `docker-compose.yml`:

```yaml
environment:
  - TMDB_API_KEY=${TMDB_API_KEY}
```

## Integration Points

### Update TrackSelector

```python
class TrackSelector:
    def select_track(self,
                     tracks: List[AudioTrack],
                     metadata: Optional[MediaMetadata] = None,
                     file_path: Optional[Path] = None,
                     config: Config = None) -> Optional[AudioTrack]:
        """Select best audio track with metadata support."""

        # 1. Try original language from metadata
        if metadata and metadata.original_language:
            for track in tracks:
                if track.language == metadata.original_language:
                    logger.info("Selected original language track",
                               language=track.language,
                               source=metadata.source)
                    return track

        # 2. Fallback to priority list (existing logic)
        priority = self.priority_resolver.resolve_priority(file_path)
        for lang in priority:
            for track in tracks:
                if track.language == lang:
                    logger.info("Selected track from priority list",
                               language=track.language)
                    return track

        return None
```

### Update Pipeline

```python
class ProcessingPipeline:
    async def process(self, file_path: Path,
                     arr_metadata: Optional[dict] = None) -> ProcessResult:
        """Process file with metadata resolution."""

        # Analyze tracks
        tracks = self.analyzer.analyze(file_path)

        # Resolve metadata (NEW)
        metadata = await self.resolver.resolve(file_path, arr_metadata)

        # Select track (with metadata)
        selected = self.selector.select_track(tracks, metadata, file_path)

        # ... rest of pipeline
```

### Update Webhook Routes

```python
async def process_file_task(file_path: Path, config, job_id: str,
                            arr_metadata: dict):
    """Background task with metadata."""
    pipeline = ProcessingPipeline(config)
    result = await pipeline.process(file_path, arr_metadata)
    # ...

@router.post("/webhook/sonarr")
async def sonarr_webhook(payload: SonarrWebhookPayload, ...):
    # Parse Arr metadata
    arr_metadata = {
        "media_type": "tv",
        "tvdb_id": payload.series_tvdb_id,
        "title": payload.series_title
    }

    # Pass to background task
    background_tasks.add_task(
        process_file_task,
        local_path,
        config,
        job_id,
        arr_metadata  # NEW
    )
```

## Implementation Steps

### Step 1: TMDB Client (1-2 days)
1. Create `metadata/tmdb.py` with TMDBClient class
2. Add API key configuration
3. Implement TV show and movie lookups
4. Add TVDB → TMDB ID conversion
5. Add retry logic with tenacity
6. Unit tests with mocked API responses

### Step 2: Cache Layer (1 day)
1. Create `metadata/cache.py` with SQLite backend
2. Add cache initialization and migrations
3. Implement get/set with TTL
4. Add cleanup job for expired entries
5. Unit tests for cache operations

### Step 3: Heuristic Parser (1 day)
1. Create `metadata/heuristic.py`
2. Implement TV show filename parsing
3. Implement movie filename parsing
4. Handle edge cases (multiple years, special characters)
5. Unit tests with various filename formats

### Step 4: Metadata Resolver (1-2 days)
1. Create `metadata/resolver.py`
2. Implement resolution chain
3. Add error handling and fallbacks
4. Integrate with existing TrackSelector
5. Unit tests for resolution logic

### Step 5: Pipeline Integration (1 day)
1. Update `core/pipeline.py` to be async
2. Add metadata parameter to track selection
3. Update webhook routes to pass metadata
4. Add structured logging for metadata sources

### Step 6: Testing (2-3 days)
1. Unit tests for each component
2. Integration tests with mocked TMDB API
3. End-to-end tests with real API (optional)
4. Test fallback behavior when API unavailable
5. Test cache hit/miss scenarios

### Step 7: Documentation (1 day)
1. Update README with TMDB setup
2. Update WEBHOOK_SETUP.md
3. Add TMDB API key instructions
4. Document cache behavior
5. Add troubleshooting guide

## Testing Requirements

### Unit Tests
- TMDBClient API calls (mocked)
- Cache operations (SQLite)
- Heuristic parsing (various formats)
- Metadata resolution chain
- Track selection with metadata

### Integration Tests
- Full metadata resolution flow
- Webhook integration with metadata
- Cache persistence across restarts
- Error handling (API failures, timeouts)

### Manual Testing
- Test with real TMDB API
- Verify original language detection
- Test fallback to priority list
- Monitor cache hit rates

## Success Criteria

- [ ] TMDB client successfully looks up TV shows and movies
- [ ] Cache reduces API calls by >80%
- [ ] Filename heuristics parse >90% of common formats
- [ ] Original language correctly detected for test files
- [ ] Fallback to priority list works when metadata unavailable
- [ ] No breaking changes to existing CLI/daemon functionality
- [ ] All tests pass with >70% coverage for new code
- [ ] Documentation complete with TMDB setup guide

## Dependencies

Add to `requirements.txt`:

```txt
# TMDB integration (Phase 3)
httpx==0.27.2  # Already included
tenacity==8.2.3
aiosqlite==0.19.0
```

## Breaking Changes

None - this phase is additive only.

## Rollback Plan

If Phase 3 causes issues:
1. Set `tmdb.enabled: false` in config
2. System falls back to priority list only
3. No data loss (cache is optional)

## Future Enhancements (Phase 6+)

- Web UI for cache management
- Manual metadata override
- Support for more metadata sources (IMDb, AniDB)
- Batch metadata refresh
- Metadata export/import

## Getting TMDB API Key

1. Go to https://www.themoviedb.org/signup
2. Create free account
3. Go to Settings → API
4. Request API key (free tier: 1000 requests/day)
5. Add to `.env` file:
   ```
   TMDB_API_KEY=your_key_here
   ```

## Notes

- TMDB API free tier has rate limits (40 requests/10 seconds)
- Cache is critical to avoid hitting limits
- Original language codes use ISO 639-1 (2-letter)
- TVDB→TMDB conversion may fail for older shows
- Filename parsing is best-effort (fallback exists)

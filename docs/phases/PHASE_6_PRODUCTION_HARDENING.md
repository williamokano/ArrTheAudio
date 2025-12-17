# Phase 6: Production Hardening

**Status:** 🚧 Planned
**Goal:** Production-ready reliability, monitoring, and performance
**Estimated Duration:** 2-3 weeks

## Overview

Phase 6 focuses on making ArrTheAudio production-ready with comprehensive monitoring, performance optimization, and operational tooling. This phase adds observability, metrics, graceful degradation, and production best practices.

## Features

### 1. Observability & Monitoring
- Prometheus metrics endpoint
- Structured logging enhancements
- Distributed tracing (optional)
- Health check improvements
- Alerting support

### 2. Performance Optimization
- Connection pooling
- Batch processing optimization
- Memory management
- Resource limits
- Caching strategies

### 3. Reliability & Resilience
- Circuit breakers
- Retry strategies with exponential backoff
- Graceful degradation
- Rate limiting
- Deadlock detection

### 4. Operational Tooling
- Admin CLI commands
- Database migrations
- Backup/restore utilities
- Configuration validation
- Debugging tools

### 5. Security Hardening
- Security headers
- Input validation
- SQL injection prevention
- Rate limiting per client
- Audit logging

## Prometheus Metrics

### Metrics to Track

```python
from prometheus_client import Counter, Histogram, Gauge, Info

# Request metrics
http_requests_total = Counter(
    'arrtheaudio_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'arrtheaudio_http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# Processing metrics
files_processed_total = Counter(
    'arrtheaudio_files_processed_total',
    'Total files processed',
    ['status', 'container_type']
)

file_processing_duration_seconds = Histogram(
    'arrtheaudio_file_processing_duration_seconds',
    'File processing duration',
    ['container_type']
)

# Job metrics
jobs_total = Counter(
    'arrtheaudio_jobs_total',
    'Total batch jobs',
    ['status']
)

jobs_active = Gauge(
    'arrtheaudio_jobs_active',
    'Currently active jobs'
)

queue_size = Gauge(
    'arrtheaudio_queue_size',
    'Current queue size'
)

# TMDB metrics
tmdb_api_requests_total = Counter(
    'arrtheaudio_tmdb_api_requests_total',
    'Total TMDB API requests',
    ['status']
)

tmdb_cache_hits_total = Counter(
    'arrtheaudio_tmdb_cache_hits_total',
    'TMDB cache hits'
)

# Error metrics
errors_total = Counter(
    'arrtheaudio_errors_total',
    'Total errors',
    ['type', 'component']
)

# System info
info = Info('arrtheaudio_version', 'Version information')
info.info({
    'version': __version__,
    'python_version': platform.python_version()
})
```

### Metrics Endpoint

```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

## Enhanced Health Checks

```python
from enum import Enum

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class HealthChecker:
    """Comprehensive health checking."""

    def __init__(self, config, job_queue, tmdb_client):
        self.config = config
        self.job_queue = job_queue
        self.tmdb_client = tmdb_client

    async def check_health(self) -> dict:
        """Run all health checks."""
        checks = {
            "ffprobe": self._check_ffprobe(),
            "mkvpropedit": self._check_mkvpropedit(),
            "ffmpeg": self._check_ffmpeg(),
            "database": await self._check_database(),
            "tmdb_api": await self._check_tmdb(),
            "disk_space": self._check_disk_space(),
            "queue": self._check_queue(),
        }

        # Determine overall status
        if all(checks.values()):
            status = HealthStatus.HEALTHY
        elif any(checks.values()):
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.UNHEALTHY

        return {
            "status": status.value,
            "version": __version__,
            "uptime_seconds": self._get_uptime(),
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }

    def _check_ffprobe(self) -> bool:
        """Check if ffprobe is available."""
        try:
            result = subprocess.run(
                ["ffprobe", "-version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def _check_disk_space(self) -> bool:
        """Check if sufficient disk space."""
        try:
            stat = shutil.disk_usage("/")
            free_percent = (stat.free / stat.total) * 100
            return free_percent > 10  # Need at least 10% free
        except:
            return False

    async def _check_database(self) -> bool:
        """Check database connectivity."""
        try:
            # Try a simple query
            conn = sqlite3.connect(self.config.jobs.storage_path)
            conn.execute("SELECT 1")
            conn.close()
            return True
        except:
            return False

    async def _check_tmdb(self) -> bool:
        """Check TMDB API connectivity."""
        if not self.config.tmdb.enabled:
            return True  # Not required

        try:
            # Try a simple API call
            response = await self.tmdb_client.client.get(
                f"{self.tmdb_client.base_url}/configuration",
                params={"api_key": self.tmdb_client.api_key},
                timeout=5.0
            )
            return response.status_code == 200
        except:
            return False

    def _check_queue(self) -> bool:
        """Check if queue is not full."""
        return self.job_queue.queue.qsize() < self.config.jobs.max_queue_size
```

## Circuit Breaker Pattern

```python
from typing import Callable, Any
import time

class CircuitBreaker:
    """Circuit breaker for external service calls."""

    def __init__(self, failure_threshold: int = 5,
                 timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout_seconds
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call."""
        self.failures = 0
        self.state = "closed"

    def _on_failure(self):
        """Handle failed call."""
        self.failures += 1
        self.last_failure_time = time.time()

        if self.failures >= self.failure_threshold:
            self.state = "open"
            logger.warning("Circuit breaker opened",
                          failures=self.failures)

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try again."""
        if self.last_failure_time is None:
            return True

        return time.time() - self.last_failure_time > self.timeout

class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass
```

### Apply to TMDB Client

```python
class TMDBClient:
    def __init__(self, api_key: str, cache: TMDBCache):
        self.api_key = api_key
        self.cache = cache
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout_seconds=60
        )

    async def get_tv_show(self, tvdb_id: int) -> Optional[dict]:
        """Get TV show with circuit breaker."""
        # Check cache first (bypass circuit breaker)
        if cached := self.cache.get(f"tv_{tvdb_id}"):
            return cached

        try:
            # Use circuit breaker for API call
            return self.circuit_breaker.call(
                self._fetch_tv_show,
                tvdb_id
            )
        except CircuitBreakerOpenError:
            logger.warning("TMDB API circuit breaker open, using fallback")
            return None  # Graceful degradation
```

## Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Create limiter
limiter = Limiter(key_func=get_remote_address)

# Apply to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to endpoints
@router.post("/batch")
@limiter.limit("10/minute")  # Max 10 batch jobs per minute per IP
async def start_batch(request: Request, ...):
    pass

@router.post("/webhook/sonarr")
@limiter.limit("100/minute")  # Max 100 webhooks per minute per IP
async def sonarr_webhook(request: Request, ...):
    pass
```

## Database Migrations

```python
# migrations/001_initial.sql
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

# migrations/002_add_priority.sql
ALTER TABLE jobs ADD COLUMN priority INTEGER DEFAULT 1;

# Migration runner
class MigrationRunner:
    """Database migration manager."""

    def __init__(self, db_path: Path, migrations_dir: Path):
        self.db_path = db_path
        self.migrations_dir = migrations_dir

    def run_migrations(self):
        """Run pending migrations."""
        conn = sqlite3.connect(self.db_path)

        # Create migrations table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                version INTEGER PRIMARY KEY,
                applied_at INTEGER NOT NULL
            )
        """)

        # Get applied migrations
        cursor = conn.execute("SELECT version FROM migrations")
        applied = {row[0] for row in cursor.fetchall()}

        # Get migration files
        migrations = sorted(self.migrations_dir.glob("*.sql"))

        for migration_file in migrations:
            version = int(migration_file.stem.split("_")[0])

            if version in applied:
                continue

            logger.info("Running migration", version=version,
                       file=migration_file.name)

            # Read and execute migration
            sql = migration_file.read_text()
            conn.executescript(sql)

            # Mark as applied
            conn.execute(
                "INSERT INTO migrations (version, applied_at) VALUES (?, ?)",
                (version, int(time.time()))
            )

        conn.commit()
        conn.close()

        logger.info("Migrations complete")
```

## Admin CLI Commands

```python
@cli.group()
def admin():
    """Admin commands."""
    pass

@admin.command()
@click.pass_context
def cleanup(ctx):
    """Clean up old jobs and cache entries."""
    config = ctx.obj["config"]

    # Clean job history
    storage = JobStorage(config.jobs.storage_path)
    deleted = storage.cleanup_old_jobs(config.jobs.retention_days)
    click.echo(f"Deleted {deleted} old jobs")

    # Clean TMDB cache
    cache = TMDBCache(config.tmdb.cache_path, config.tmdb.cache_ttl_days)
    cache.cleanup_expired()
    click.echo("TMDB cache cleaned")

@admin.command()
@click.pass_context
def stats(ctx):
    """Show system statistics."""
    config = ctx.obj["config"]

    # Job stats
    storage = JobStorage(config.jobs.storage_path)
    stats = storage.get_stats()

    click.echo("Job Statistics:")
    click.echo(f"  Total jobs: {stats['total']}")
    click.echo(f"  Completed: {stats['completed']}")
    click.echo(f"  Failed: {stats['failed']}")

    # Cache stats
    cache = TMDBCache(config.tmdb.cache_path)
    cache_stats = cache.get_stats()

    click.echo("\nTMDB Cache Statistics:")
    click.echo(f"  Entries: {cache_stats['entries']}")
    click.echo(f"  Hit rate: {cache_stats['hit_rate']:.2%}")

@admin.command()
@click.argument("config_file", type=click.Path(exists=True))
def validate_config(config_file):
    """Validate configuration file."""
    try:
        config = load_config(Path(config_file))
        click.secho("✓ Configuration is valid", fg="green")

        # Show summary
        click.echo(f"\nLanguages: {', '.join(config.language_priority)}")
        click.echo(f"Path overrides: {len(config.path_overrides)}")
        click.echo(f"Path mappings: {len(config.path_mappings)}")

    except Exception as e:
        click.secho(f"✗ Configuration invalid: {e}", fg="red", err=True)
        sys.exit(1)

@admin.command()
@click.option("--output", "-o", type=click.Path(), help="Backup file path")
@click.pass_context
def backup(ctx, output):
    """Backup database and cache."""
    config = ctx.obj["config"]

    if not output:
        output = f"arrtheaudio_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"

    with tarfile.open(output, "w:gz") as tar:
        # Add job database
        if Path(config.jobs.storage_path).exists():
            tar.add(config.jobs.storage_path, arcname="jobs.db")

        # Add TMDB cache
        if Path(config.tmdb.cache_path).exists():
            tar.add(config.tmdb.cache_path, arcname="tmdb_cache.db")

    click.echo(f"Backup created: {output}")

@admin.command()
@click.argument("backup_file", type=click.Path(exists=True))
@click.pass_context
def restore(ctx, backup_file):
    """Restore from backup."""
    config = ctx.obj["config"]

    click.confirm("This will overwrite existing data. Continue?", abort=True)

    with tarfile.open(backup_file, "r:gz") as tar:
        tar.extractall(path=config.config_dir)

    click.echo("Backup restored")
```

## Configuration Validation

```python
from pydantic import validator, root_validator

class Config(BaseModel):
    """Enhanced configuration with validation."""

    language_priority: List[str]

    @validator('language_priority')
    def validate_languages(cls, v):
        """Validate language codes."""
        # Check ISO 639-1 codes
        valid_codes = ['eng', 'jpn', 'spa', 'fra', 'deu', ...]  # Full list
        for code in v:
            if code not in valid_codes:
                logger.warning(f"Unknown language code: {code}")
        return v

    @root_validator
    def validate_paths(cls, values):
        """Validate path configurations."""
        path_mappings = values.get('path_mappings', [])

        # Check for conflicts
        remotes = [m.remote for m in path_mappings]
        if len(remotes) != len(set(remotes)):
            raise ValueError("Duplicate remote paths in path_mappings")

        return values
```

## Performance Optimizations

### Connection Pooling

```python
import httpx

# Create connection pool for TMDB
limits = httpx.Limits(
    max_keepalive_connections=5,
    max_connections=10,
    keepalive_expiry=30.0
)

client = httpx.AsyncClient(
    limits=limits,
    timeout=10.0,
    http2=True  # Enable HTTP/2
)
```

### Batch Processing Optimization

```python
async def process_batch_optimized(files: List[Path]) -> List[ProcessResult]:
    """Process files in optimal batch sizes."""
    results = []

    # Process in chunks to avoid memory issues
    chunk_size = 10
    for i in range(0, len(files), chunk_size):
        chunk = files[i:i+chunk_size]

        # Process chunk concurrently
        tasks = [process_file(f) for f in chunk]
        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

        results.extend(chunk_results)

        # Small delay between chunks to avoid overwhelming system
        await asyncio.sleep(0.1)

    return results
```

### Memory Management

```python
import gc
import resource

def set_resource_limits():
    """Set memory and file descriptor limits."""
    # Limit memory usage (2GB)
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 * 1024 * 1024, -1))

    # Limit open file descriptors
    resource.setrlimit(resource.RLIMIT_NOFILE, (1024, 2048))

def periodic_gc():
    """Periodic garbage collection."""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        gc.collect()
        logger.debug("Garbage collection run")
```

## Implementation Steps

### Step 1: Metrics (2-3 days)
1. Add prometheus_client dependency
2. Define all metrics
3. Add `/metrics` endpoint
4. Instrument key code paths
5. Test with Prometheus

### Step 2: Health Checks (1 day)
1. Enhance health check endpoint
2. Add component checks
3. Add degraded state support
4. Test various failure scenarios

### Step 3: Circuit Breakers (1-2 days)
1. Implement CircuitBreaker class
2. Apply to TMDB client
3. Add monitoring for circuit state
4. Test failure scenarios

### Step 4: Rate Limiting (1 day)
1. Add slowapi dependency
2. Configure rate limits
3. Test rate limit enforcement
4. Document limits

### Step 5: Database Migrations (1 day)
1. Create migrations system
2. Write initial migrations
3. Test migration runner
4. Document migration process

### Step 6: Admin CLI (2 days)
1. Add admin command group
2. Implement cleanup command
3. Implement stats command
4. Implement backup/restore
5. Test all commands

### Step 7: Performance Tuning (2-3 days)
1. Add connection pooling
2. Optimize batch processing
3. Add memory management
4. Profile and benchmark
5. Document optimizations

### Step 8: Documentation (2 days)
1. Operations guide
2. Monitoring setup (Prometheus/Grafana)
3. Troubleshooting guide
4. Performance tuning guide

## Success Criteria

- [ ] Prometheus metrics exported
- [ ] Health checks comprehensive
- [ ] Circuit breakers prevent cascading failures
- [ ] Rate limiting protects from abuse
- [ ] Database migrations work reliably
- [ ] Admin tools functional
- [ ] Performance benchmarks met:
  - API latency p99 < 100ms
  - File processing < 500ms (MKV)
  - Memory usage < 512MB under load
  - No memory leaks
- [ ] All tests pass
- [ ] Documentation complete

## Monitoring Setup

### Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'arrtheaudio'
    scrape_interval: 15s
    static_configs:
      - targets: ['arrtheaudio:9393']
```

### Grafana Dashboard

Create dashboard with panels for:
- Request rate and latency
- File processing rate
- Job queue size
- Error rate
- TMDB API calls and cache hits
- System resources (CPU, memory)

## Dependencies

Add to `requirements.txt`:

```txt
# Production hardening (Phase 6)
prometheus-client==0.19.0
slowapi==0.1.9
```

## Breaking Changes

None - all changes are additive or internal.

## Future Enhancements

- OpenTelemetry integration
- Distributed tracing
- Custom Grafana dashboard
- Alert manager integration
- Log aggregation (ELK, Loki)
- APM (Application Performance Monitoring)

## Notes

- Metrics add minimal overhead (<1%)
- Circuit breakers require tuning per environment
- Rate limits should be adjusted based on usage
- Backup/restore critical for production
- Monitor metrics regularly for anomalies

# ArrTheAudio - Development Phases

This directory contains detailed documentation for each development phase of ArrTheAudio. Each phase builds upon the previous one, adding functionality and moving towards a production-ready system.

## Phase Overview

| Phase | Status | Duration | Description |
|-------|--------|----------|-------------|
| [Phase 1](#phase-1-mvp-core) | ✅ Complete | 1-2 weeks | Core MKV processing with CLI |
| [Phase 2](#phase-2-daemon--webhooks) | ✅ Complete | 2-3 weeks | Webhook daemon for Arr integration |
| [Phase 3](#phase-3-tmdb-integration) | ✅ Complete | 1-2 weeks | Automatic language detection via TMDB |
| [Phase 4](#phase-4-mp4-support) | 🚧 Planned | 1 week | MP4 container format support |
| [Phase 5](#phase-5-batch-processing-api) | 🚧 Planned | 1-2 weeks | REST API for batch job management |
| [Phase 6](#phase-6-production-hardening) | 🚧 Planned | 2-3 weeks | Monitoring, metrics, and reliability |

**Total Estimated Duration:** 9-14 weeks

---

## Phase 1: MVP Core

**Status:** ✅ Complete
**Documentation:** _(No separate doc - see git history)_

### What Was Built

Phase 1 delivered the core functionality:

- **MKV Support** - In-place metadata editing with mkvpropedit (~200-300ms per file)
- **Audio Track Selection** - Intelligent selection based on language priorities
- **Path-Specific Priorities** - Glob pattern matching for different language rules per path
- **CLI Commands** - `process` (single file) and `scan` (directory batching)
- **Configuration System** - Pydantic-based validation with YAML config
- **Structured Logging** - JSON logging with structlog
- **Testing** - Comprehensive unit tests for core logic
- **Docker Support** - Container with ffmpeg and mkvtoolnix

### Key Features

```yaml
# Language priority with path overrides
language_priority:
  - eng
  - jpn

path_overrides:
  - path: "/media/anime/**"
    language_priority: [jpn, eng]
```

### Commands

```bash
# Process single file
arrtheaudio process /path/to/file.mkv

# Scan directory
arrtheaudio scan /path/to/media --recursive

# Dry run mode
arrtheaudio --config config-dryrun.yaml scan /media
```

---

## Phase 2: Daemon & Webhooks

**Status:** ✅ Complete
**Documentation:** _(No separate doc - see git history)_

### What Was Built

Phase 2 added real-time webhook integration:

- **FastAPI Daemon** - Runs on port 9393, receives webhooks from Sonarr/Radarr
- **Webhook Endpoints** - `/webhook/sonarr` and `/webhook/radarr`
- **HMAC Authentication** - Secure webhook verification
- **Path Mapping** - Translate Arr paths to local filesystem paths
- **Background Processing** - Async file processing with FastAPI BackgroundTasks
- **Health Check** - `/health` endpoint for monitoring
- **Docker Compose** - Easy deployment with docker-compose.yml
- **Integration Tests** - Full webhook flow testing

### Key Features

```yaml
# Path mappings for Arr integration
path_mappings:
  - remote: "/tv"              # Sonarr's path
    local: "/data/media/tv"    # Docker container's path
  - remote: "/movies"          # Radarr's path
    local: "/data/media/movies"

api:
  host: 0.0.0.0
  port: 9393
  webhook_secret: "${WEBHOOK_SECRET}"
```

### Endpoints

- `POST /webhook/sonarr` - Receive Sonarr download webhooks
- `POST /webhook/radarr` - Receive Radarr download webhooks
- `GET /health` - Health check for Docker
- `GET /docs` - Interactive API documentation

---

## Phase 3: TMDB Integration

**Status:** ✅ Complete
**Documentation:** [PHASE_3_TMDB_INTEGRATION.md](./PHASE_3_TMDB_INTEGRATION.md)
**Completed:** December 2024

### What Was Built

Automatic original language detection using The Movie Database (TMDB) API.

### Key Features

- **TMDB API Client** - HTTP client with rate limiting and retry logic
- **SQLite Cache** - Local caching with 30-day TTL to minimize API calls
- **Metadata Resolution Chain**:
  1. Sonarr/Radarr webhook data → TMDB lookup
  2. Filename heuristics → TMDB search
  3. Fallback to language priority list
- **Track Selection Enhancement** - Original language takes precedence over priority

### How It Works

```python
# Resolution flow
1. Extract TVDB/TMDB ID from Sonarr/Radarr webhook
2. Look up show/movie on TMDB API
3. Get original_language (e.g., "ja" for Japanese anime)
4. Select audio track matching original language
5. If not found, fall back to language_priority list
```

### Benefits

- **Automatic** - No manual configuration for original language
- **Accurate** - Uses authoritative TMDB data
- **Cached** - 80%+ reduction in API calls
- **Graceful Fallback** - Works even if API is down

### Configuration

```yaml
tmdb:
  enabled: true
  api_key: "${TMDB_API_KEY}"
  cache_ttl_days: 30
  cache_path: /config/tmdb_cache.db
```

---

## Phase 4: MP4 Support

**Status:** 🚧 Planned
**Documentation:** [PHASE_4_MP4_SUPPORT.md](./PHASE_4_MP4_SUPPORT.md)
**Estimated Duration:** 1 week

### What Will Be Built

Support for MP4 container format in addition to MKV.

### Key Features

- **MP4Executor** - FFmpeg-based remuxing (no re-encoding)
- **Atomic Operations** - Safe temp file → backup → replace workflow
- **Disk Space Check** - Verify space before processing (needs 2x file size)
- **Executor Factory** - Automatic selection of MKV or MP4 executor
- **Enhanced Detection** - Better container type detection

### How It Works

Unlike MKV which supports in-place editing, MP4 requires full remuxing:

1. Create temporary output file
2. Remux with ffmpeg, setting audio disposition
3. Create backup of original
4. Atomic replace original with temp file
5. Clean up backup on success

### Performance

| Container | Method | Speed | Disk Space |
|-----------|--------|-------|------------|
| MKV | mkvpropedit | ~200-300ms | None (in-place) |
| MP4 | ffmpeg remux | ~5-30s | 2x file size (temp) |

### Configuration

```yaml
containers:
  mkv: true   # Use mkvpropedit
  mp4: true   # Use ffmpeg remux

processing:
  timeout_seconds: 300  # Allow time for large MP4s
  max_file_size_gb: 50  # Reject oversized files
```

---

## Phase 5: Batch Processing API

**Status:** 🚧 Planned
**Documentation:** [PHASE_5_BATCH_PROCESSING_API.md](./PHASE_5_BATCH_PROCESSING_API.md)
**Estimated Duration:** 1-2 weeks

### What Will Be Built

Full-featured REST API for batch job management and monitoring.

### Key Features

- **Batch Endpoint** - `POST /batch` to start directory scans
- **Job Management** - List, monitor, and cancel jobs
- **Priority Queue** - Webhooks prioritized over manual batches
- **Progress Tracking** - Real-time progress with files processed/remaining
- **Job History** - Persistent storage of job results
- **Concurrent Workers** - Multiple files processed simultaneously

### API Endpoints

- `POST /batch` - Start new batch job
- `GET /batch/{job_id}` - Get job status and progress
- `DELETE /batch/{job_id}` - Cancel running job
- `GET /jobs` - List all jobs with filtering
- `GET /jobs/stats` - Overall statistics

### Example Usage

```bash
# Start batch job
curl -X POST http://localhost:9393/batch \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/media/tv",
    "recursive": true,
    "pattern": "**/*.mkv",
    "dry_run": false
  }'

# Get job status
curl http://localhost:9393/batch/job_20240115_abc123

# Response
{
  "job_id": "job_20240115_abc123",
  "status": "running",
  "progress": {
    "total_files": 120,
    "processed": 45,
    "success": 40,
    "skipped": 3,
    "failed": 2,
    "percent": 37.5,
    "eta_seconds": 225
  }
}
```

### Job Queue

- **Persistent** - Jobs survive daemon restarts
- **Prioritized** - Webhooks > High > Normal > Low
- **Concurrent** - 2 workers by default (configurable)
- **History** - 30 days retention (configurable)

---

## Phase 6: Production Hardening

**Status:** 🚧 Planned
**Documentation:** [PHASE_6_PRODUCTION_HARDENING.md](./PHASE_6_PRODUCTION_HARDENING.md)
**Estimated Duration:** 2-3 weeks

### What Will Be Built

Production-ready reliability, monitoring, and operational tooling.

### Key Features

#### 1. Observability
- **Prometheus Metrics** - `/metrics` endpoint with comprehensive metrics
- **Enhanced Logging** - Additional context and correlation IDs
- **Health Checks** - Detailed component health status

#### 2. Reliability
- **Circuit Breakers** - Prevent cascading failures (especially for TMDB API)
- **Retry Strategies** - Exponential backoff for transient failures
- **Rate Limiting** - Protect against abuse
- **Graceful Degradation** - Continue working when external services fail

#### 3. Performance
- **Connection Pooling** - Reuse HTTP connections
- **Batch Optimization** - Process files in optimal chunks
- **Memory Management** - Resource limits and periodic GC
- **Caching Strategies** - Intelligent caching at multiple levels

#### 4. Operations
- **Admin CLI** - Management commands:
  - `arrtheaudio admin cleanup` - Clean old jobs/cache
  - `arrtheaudio admin stats` - System statistics
  - `arrtheaudio admin backup` - Backup databases
  - `arrtheaudio admin validate-config` - Config validation
- **Database Migrations** - Version-controlled schema changes
- **Backup/Restore** - Utilities for disaster recovery

#### 5. Security
- **Security Headers** - CORS, CSP, etc.
- **Input Validation** - Comprehensive validation
- **Audit Logging** - Track administrative actions
- **Rate Limiting** - Per-client rate limits

### Metrics Exported

```
# HTTP metrics
arrtheaudio_http_requests_total
arrtheaudio_http_request_duration_seconds

# Processing metrics
arrtheaudio_files_processed_total
arrtheaudio_file_processing_duration_seconds

# Job metrics
arrtheaudio_jobs_total
arrtheaudio_jobs_active
arrtheaudio_queue_size

# TMDB metrics
arrtheaudio_tmdb_api_requests_total
arrtheaudio_tmdb_cache_hits_total

# Error metrics
arrtheaudio_errors_total
```

### Monitoring Setup

```bash
# Prometheus scrapes metrics
curl http://localhost:9393/metrics

# Grafana dashboard shows:
- Request rate and latency
- File processing throughput
- Job queue size
- Error rates
- Cache hit rates
- System resources
```

---

## Development Workflow

### Starting a New Phase

1. **Read the phase document** - Understand goals and requirements
2. **Create a feature branch** - `git checkout -b phase-N-feature-name`
3. **Follow implementation steps** - Work through steps in order
4. **Write tests** - TDD approach recommended
5. **Update documentation** - Keep docs in sync with code
6. **Create PR** - Follow PR template

### Testing Strategy

Each phase should include:

- **Unit Tests** - Test individual components
- **Integration Tests** - Test component interactions
- **Manual Testing** - Verify with real files/webhooks
- **Performance Testing** - Ensure acceptable performance

### Code Review Checklist

- [ ] All tests pass
- [ ] Code follows existing style
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] Performance acceptable
- [ ] Security considerations addressed

---

## Dependency Graph

```
Phase 1 (MVP Core)
    ↓
Phase 2 (Daemon & Webhooks) ← requires Phase 1
    ↓
Phase 3 (TMDB) ← requires Phase 2
    ↓
Phase 4 (MP4) ← can be done in parallel with Phase 3
    ↓
Phase 5 (Batch API) ← requires Phases 1-4
    ↓
Phase 6 (Production Hardening) ← requires all previous phases
```

**Note:** Phases 3 and 4 can be developed in parallel as they're independent.

---

## Getting Started

### For Contributors

1. **Choose a phase** - Start with the next incomplete phase
2. **Read the phase doc** - Understand the requirements
3. **Check dependencies** - Ensure previous phases are complete
4. **Create an issue** - Discuss approach before coding
5. **Follow implementation steps** - Work systematically
6. **Submit PR** - Follow contribution guidelines

### For Users

- **Phase 1-2 (Current)** - Ready for production use
- **Phase 3-6 (Future)** - Coming soon, features can be requested

---

## Questions?

- **General questions** - Open a discussion on GitHub
- **Feature requests** - Use the feature request template
- **Bug reports** - Use the bug report template
- **Phase-specific questions** - Comment on the phase implementation issue

---

## Timeline

### Historical

- **Phase 1** - Completed: December 2024
- **Phase 2** - Completed: December 2024
- **Phase 3** - Completed: December 2024

### Projected

- **Phase 4** - Target: Q1 2025
- **Phase 5** - Target: Q2 2025
- **Phase 6** - Target: Q2 2025

**Note:** Timeline is approximate and may change based on contributor availability and community feedback.

---

## Contributing

Want to contribute? Great! Here's how:

1. Read [CONTRIBUTING.md](../../.github/CONTRIBUTING.md)
2. Choose a phase that interests you
3. Read the phase documentation
4. Open an issue to discuss your approach
5. Submit a PR following the guidelines

**Priority Areas:**
- Phase 3 (TMDB integration) - Most requested feature
- Phase 4 (MP4 support) - High user demand
- Tests for existing functionality
- Documentation improvements

Thank you for contributing to ArrTheAudio! 🎉

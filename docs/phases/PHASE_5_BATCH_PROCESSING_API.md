# Phase 5: Unified Job Queue & Batch Processing

**Status:** 🚧 Planned
**Goal:** Add persistent job queue system with batch processing and monitoring APIs
**Estimated Duration:** 2-3 weeks
**Dependencies:** Phases 1-4 complete

## Overview

Phase 5 implements a **unified job queue system** that handles both webhook-triggered and manual batch processing through a single persistent queue with concurrent workers.

**Key Changes:**
- **Fixes webhook multi-file bug** - Currently only processes first file from Sonarr/Radarr
- **Adds manual batch processing** - Scan existing libraries on demand
- **Persistent job queue** - Survives daemon restarts
- **Concurrent workers** - Process multiple files in parallel
- **Resource management** - Limits MP4 concurrent jobs for disk space safety
- **Full monitoring APIs** - Track queue, jobs, batches, and statistics

## Architecture

### Core Concept: Everything is a Job

```
Single Job = Process 1 File

Webhook with 3 files → 3 jobs (linked by webhook_id)
Manual scan of 100 files → 100 jobs (linked by batch_id)
```

### Job Model

```python
Job {
  "job_id": "job_abc123",
  "file_path": "/media/Show/S01E01.mkv",
  "status": "queued",  # queued, running, completed, failed, cancelled
  "priority": "high",  # high (webhooks), normal (manual), low (retry)
  "container": "mkv",  # mkv or mp4

  # Linking metadata
  "webhook_id": "webhook_xyz789",  # Links jobs from same webhook
  "batch_id": None,                # Or batch_id for manual scans
  "source": "sonarr",              # sonarr, radarr, manual

  # Timestamps
  "created_at": "2024-12-19T10:30:00Z",
  "started_at": "2024-12-19T10:30:05Z",
  "completed_at": "2024-12-19T10:30:10Z",

  # Result
  "result": "success",  # success, failed, skipped
  "reason": None,       # Reason for skip/failure
  "duration_ms": 5234
}
```

### Queue System

**Single Persistent Queue (SQLite)**
- One queue for all sources (webhooks + manual batches)
- Jobs ordered by: priority (high > normal > low), then FIFO
- Survives daemon restarts
- Concurrent workers pull from queue

**Queue Example:**
```
┌─────────────────────────────────────┐
│ Priority Queue                       │
├─────────────────────────────────────┤
│ [HIGH] job_1 (sonarr webhook)      │
│ [HIGH] job_2 (sonarr webhook)      │
│ [HIGH] job_3 (radarr webhook)      │
│ [NORMAL] job_4 (manual batch)      │
│ [NORMAL] job_5 (manual batch)      │
│ [LOW] job_6 (retry)                │
└─────────────────────────────────────┘
         ↓
   ┌─────────┬─────────┐
   │ Worker 1│ Worker 2│  (Configurable: 1-8 workers)
   └─────────┴─────────┘
```

### Worker Pool

**Configurable Concurrency:**
```yaml
processing:
  worker_count: 2              # Number of concurrent workers (default: 2)
  max_mp4_concurrent: 1        # Max MP4 jobs at once (disk space safety)
  max_queue_size: 100          # Reject new jobs if queue is full
  timeout_seconds: 300         # Per-job timeout
  retry_attempts: 2            # Retry failed jobs
  retry_delay_seconds: 60      # Wait before retry
```

**MP4 Resource Management:**
- Before starting MP4 job: check `free_space > (file_size * 2)`
- If insufficient: mark job as `waiting_for_space`, retry every 60s
- OR: Set `max_mp4_concurrent: 1` to serialize MP4 processing
- MKV jobs can run concurrently (no disk space concern)

## Features

### 1. Multi-File Webhook Support (Bug Fix)

**Current Behavior (Bug):**
- Sonarr sends 3 files → Only first file processed
- Files 2 and 3 are silently dropped

**New Behavior:**
```python
POST /webhook/sonarr
{
  "episodeFiles": [
    {"path": "/media/Show/S01E01.mkv"},
    {"path": "/media/Show/S01E02.mkv"},
    {"path": "/media/Show/S01E03.mkv"}
  ]
}

# Response:
{
  "status": "accepted",
  "webhook_id": "webhook_xyz789",
  "job_ids": ["job_1", "job_2", "job_3"],
  "file_count": 3,
  "message": "3 files queued for processing"
}
```

**What Happens:**
1. Create 3 separate jobs with same `webhook_id`
2. Add all to queue with `priority=high`
3. Return immediately (async processing)
4. Workers process them concurrently

### 2. Manual Batch Processing

**Start Batch Scan:**
```python
POST /batch
{
  "path": "/media/tv",
  "recursive": true,
  "pattern": "**/*.mkv",  # Optional glob pattern
  "dry_run": false,
  "priority": "normal"    # normal or low
}

# Response:
{
  "status": "started",
  "batch_id": "batch_abc123",
  "estimated_files": 120,
  "message": "Batch scan started"
}
```

**What Happens:**
1. Scan directory for matching files
2. Create one job per file (linked by `batch_id`)
3. Add all to queue with specified priority
4. Return immediately
5. Workers process them as they become available

### 3. Job Management APIs

**Get Queue Status:**
```python
GET /queue

{
  "total_jobs": 45,
  "queued": 40,
  "running": 2,
  "completed_today": 150,
  "failed_today": 3,
  "workers": {
    "total": 2,
    "active": 2,
    "idle": 0
  },
  "current_jobs": [
    {
      "job_id": "job_1",
      "status": "running",
      "file": "/media/Show/S01E01.mkv",
      "container": "mkv",
      "started_at": "2024-12-19T10:30:00Z",
      "worker_id": 1
    },
    {
      "job_id": "job_2",
      "status": "running",
      "file": "/media/Movie.mp4",
      "container": "mp4",
      "started_at": "2024-12-19T10:30:05Z",
      "worker_id": 2
    }
  ],
  "next_jobs": [
    {
      "job_id": "job_3",
      "status": "queued",
      "file": "/media/Show/S01E02.mkv",
      "priority": "high",
      "position": 1
    }
  ]
}
```

**Get Specific Job:**
```python
GET /jobs/job_abc123

{
  "job_id": "job_abc123",
  "status": "completed",
  "file_path": "/media/Show/S01E01.mkv",
  "container": "mkv",
  "priority": "high",
  "source": "sonarr",
  "webhook_id": "webhook_xyz789",
  "created_at": "2024-12-19T10:29:55Z",
  "started_at": "2024-12-19T10:30:00Z",
  "completed_at": "2024-12-19T10:30:15Z",
  "duration_ms": 15234,
  "result": "success",
  "track_changed": true,
  "selected_track": {
    "index": 1,
    "language": "eng"
  }
}
```

**List Jobs (with filters):**
```python
GET /jobs?status=running
GET /jobs?webhook_id=webhook_xyz789
GET /jobs?batch_id=batch_abc123
GET /jobs?source=sonarr
GET /jobs?limit=50&offset=0

{
  "total": 150,
  "limit": 50,
  "offset": 0,
  "jobs": [...]
}
```

**Cancel Job:**
```python
DELETE /jobs/job_abc123

{
  "status": "cancelled",
  "job_id": "job_abc123",
  "message": "Job cancelled"
}
```

### 4. Batch Progress Tracking

**Get Batch Progress:**
```python
GET /batch/batch_abc123

{
  "batch_id": "batch_abc123",
  "status": "running",
  "path": "/media/tv",
  "recursive": true,
  "priority": "normal",
  "created_at": "2024-12-19T10:00:00Z",
  "started_at": "2024-12-19T10:00:05Z",
  "progress": {
    "total_files": 120,
    "completed": 45,
    "running": 2,
    "queued": 73,
    "failed": 0,
    "skipped": 5,
    "progress_percent": 37.5,
    "eta_seconds": 225
  },
  "results": {
    "success": 40,
    "failed": 0,
    "skipped": 5,
    "track_changes": 38
  }
}
```

**Cancel Batch:**
```python
DELETE /batch/batch_abc123

{
  "status": "cancelling",
  "batch_id": "batch_abc123",
  "cancelled_jobs": 73,  # Jobs that were queued
  "message": "Batch cancelled, running jobs will complete"
}
```

### 5. Webhook Progress Tracking

**Get All Jobs from Webhook:**
```python
GET /webhook/webhook_xyz789

{
  "webhook_id": "webhook_xyz789",
  "source": "sonarr",
  "series_title": "My Show",
  "created_at": "2024-12-19T10:29:55Z",
  "total_jobs": 3,
  "completed": 2,
  "running": 1,
  "failed": 0,
  "jobs": [
    {
      "job_id": "job_1",
      "status": "completed",
      "file": "/media/Show/S01E01.mkv",
      "duration_ms": 5234
    },
    {
      "job_id": "job_2",
      "status": "running",
      "file": "/media/Show/S01E02.mkv"
    },
    {
      "job_id": "job_3",
      "status": "queued",
      "file": "/media/Show/S01E03.mkv"
    }
  ]
}
```

### 6. Statistics & Monitoring

**Get Overall Stats:**
```python
GET /stats

{
  "queue": {
    "size": 45,
    "queued": 40,
    "running": 2,
    "waiting_for_space": 3
  },
  "workers": {
    "total": 2,
    "active": 2,
    "idle": 0
  },
  "today": {
    "jobs_completed": 150,
    "jobs_failed": 3,
    "success_rate": 98.0,
    "avg_duration_ms": 8500
  },
  "lifetime": {
    "total_jobs": 5420,
    "total_files_processed": 5200,
    "total_time_hours": 12.5
  },
  "containers": {
    "mkv_processed": 4800,
    "mp4_processed": 400,
    "avg_mkv_ms": 300,
    "avg_mp4_ms": 25000
  }
}
```

### 7. Job History & Cleanup

**Job Retention:**
```yaml
processing:
  job_history_days: 30  # Keep completed jobs for 30 days
  failed_job_days: 90   # Keep failed jobs longer for debugging
  cleanup_interval_hours: 24
```

**Manual Cleanup:**
```bash
# Via API
POST /admin/cleanup
{
  "older_than_days": 30,
  "statuses": ["completed", "cancelled"]
}

# Via CLI
arrtheaudio admin cleanup --older-than 30d
```

## API Endpoints

### Batch Operations

#### `POST /batch`
Start a new batch processing job.

**Request:**
```json
{
  "path": "/media/tv",
  "recursive": true,
  "pattern": "**/*.mkv",
  "dry_run": false,
  "priority": "normal",
  "filters": {
    "min_size_mb": 100,
    "max_age_days": 30,
    "exclude_patterns": ["*sample*", "*trailer*"]
  }
}
```

**Response:**
```json
{
  "status": "started",
  "job_id": "job_2024-01-15_abc123",
  "estimated_files": 120,
  "message": "Batch job started"
}
```

**Status Codes:**
- `202 Accepted` - Job started
- `400 Bad Request` - Invalid parameters
- `409 Conflict` - Another job already running for this path
- `503 Service Unavailable` - Queue full

#### `GET /batch/{job_id}`
Get batch job details and progress.

**Response:**
```json
{
  "job_id": "job_2024-01-15_abc123",
  "status": "running",
  "path": "/media/tv",
  "recursive": true,
  "dry_run": false,
  "priority": "normal",
  "progress": {
    "total_files": 120,
    "processed": 45,
    "success": 40,
    "skipped": 3,
    "failed": 2,
    "remaining": 75,
    "percent": 37.5,
    "eta_seconds": 225
  },
  "started_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:32:30Z",
  "completed_at": null,
  "results": [
    {
      "file": "/media/tv/Show/S01E01.mkv",
      "status": "success",
      "message": "Set default audio track to 'eng'",
      "duration_ms": 250
    }
  ]
}
```

#### `DELETE /batch/{job_id}`
Cancel a running job.

**Response:**
```json
{
  "status": "cancelled",
  "message": "Job cancelled successfully",
  "processed_before_cancel": 45
}
```

### Job Management

#### `GET /jobs`
List all jobs with optional filtering.

**Query Parameters:**
- `status` - Filter by status (queued, running, completed, failed, cancelled)
- `limit` - Max results (default: 50)
- `offset` - Pagination offset
- `order_by` - Sort field (created_at, updated_at)

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "job_2024-01-15_abc123",
      "status": "running",
      "path": "/media/tv",
      "progress": {
        "percent": 37.5
      },
      "started_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 15,
  "limit": 50,
  "offset": 0
}
```

#### `GET /jobs/stats`
Get overall job statistics.

**Response:**
```json
{
  "total_jobs": 150,
  "running": 1,
  "queued": 2,
  "completed": 140,
  "failed": 5,
  "cancelled": 2,
  "total_files_processed": 12450,
  "success_rate": 0.96,
  "average_duration_seconds": 180
}
```

## Technical Details

### File Structure

```
src/arrtheaudio/
├── api/
│   ├── routes.py          # UPDATE - Add batch routes
│   └── models.py          # UPDATE - Add batch models
├── jobs/
│   ├── __init__.py
│   ├── queue.py           # NEW - Job queue management
│   ├── worker.py          # NEW - Background job worker
│   ├── models.py          # NEW - Job data models
│   └── storage.py         # NEW - Job persistence
└── core/
    └── pipeline.py        # UPDATE - Add progress callbacks
```

### Job Models

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    WEBHOOK = 3  # Highest priority

@dataclass
class JobProgress:
    """Job progress tracking."""
    total_files: int
    processed: int
    success: int
    skipped: int
    failed: int

    @property
    def remaining(self) -> int:
        return self.total_files - self.processed

    @property
    def percent(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.processed / self.total_files) * 100

@dataclass
class FileResult:
    """Result of processing a single file."""
    file: str
    status: str
    message: str
    duration_ms: int
    timestamp: datetime

@dataclass
class BatchJob:
    """Batch processing job."""
    job_id: str
    status: JobStatus
    path: str
    recursive: bool
    pattern: Optional[str]
    dry_run: bool
    priority: JobPriority
    progress: JobProgress
    results: List[FileResult]
    started_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str]
```

### Job Queue

```python
import asyncio
from typing import Optional, List
from queue import PriorityQueue

class JobQueue:
    """Priority queue for batch jobs."""

    def __init__(self, max_size: int = 100):
        self.queue = PriorityQueue(maxsize=max_size)
        self.active_jobs: dict[str, BatchJob] = {}
        self.storage = JobStorage()

    def enqueue(self, job: BatchJob) -> bool:
        """Add job to queue.

        Args:
            job: Batch job to queue

        Returns:
            True if queued, False if queue full
        """
        try:
            # Store job in persistence layer
            self.storage.save(job)

            # Add to priority queue (lower number = higher priority)
            priority = -job.priority.value
            self.queue.put((priority, job.job_id, job))

            logger.info("Job queued",
                       job_id=job.job_id,
                       priority=job.priority.name)
            return True

        except Full:
            logger.warning("Job queue full", job_id=job.job_id)
            return False

    def dequeue(self) -> Optional[BatchJob]:
        """Get next job from queue.

        Returns:
            Next job or None if queue empty
        """
        try:
            _, job_id, job = self.queue.get(block=False)
            self.active_jobs[job_id] = job
            return job
        except Empty:
            return None

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get job by ID."""
        # Check active jobs first
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]

        # Check storage
        return self.storage.get(job_id)

    def update_job(self, job: BatchJob):
        """Update job status and progress."""
        self.storage.save(job)
        if job.job_id in self.active_jobs:
            self.active_jobs[job.job_id] = job

    def complete_job(self, job_id: str):
        """Mark job as complete and remove from active."""
        if job_id in self.active_jobs:
            job = self.active_jobs.pop(job_id)
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            self.storage.save(job)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel job if running."""
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            self.storage.save(job)
            return True
        return False

    def list_jobs(self, status: Optional[JobStatus] = None,
                  limit: int = 50, offset: int = 0) -> List[BatchJob]:
        """List jobs with filtering."""
        return self.storage.list(status, limit, offset)
```

### Job Worker

```python
import asyncio
from typing import Callable

class JobWorker:
    """Background worker for processing batch jobs."""

    def __init__(self, queue: JobQueue, pipeline: ProcessingPipeline,
                 max_concurrent: int = 2):
        self.queue = queue
        self.pipeline = pipeline
        self.max_concurrent = max_concurrent
        self.running = False
        self.tasks: List[asyncio.Task] = []

    async def start(self):
        """Start worker threads."""
        self.running = True
        self.tasks = [
            asyncio.create_task(self._worker(i))
            for i in range(self.max_concurrent)
        ]
        logger.info("Job workers started", count=self.max_concurrent)

    async def stop(self):
        """Stop workers gracefully."""
        self.running = False
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("Job workers stopped")

    async def _worker(self, worker_id: int):
        """Worker loop."""
        logger.info("Worker started", worker_id=worker_id)

        while self.running:
            # Get next job
            job = self.queue.dequeue()

            if not job:
                await asyncio.sleep(1)
                continue

            try:
                await self._process_job(job)
            except Exception as e:
                logger.exception("Job processing failed",
                               job_id=job.job_id,
                               error=str(e))
                job.status = JobStatus.FAILED
                job.error = str(e)
                job.completed_at = datetime.now()
                self.queue.update_job(job)

        logger.info("Worker stopped", worker_id=worker_id)

    async def _process_job(self, job: BatchJob):
        """Process a single job."""
        logger.info("Processing job", job_id=job.job_id, path=job.path)

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        self.queue.update_job(job)

        # Discover files
        scanner = FileScanner()
        files = scanner.scan(Path(job.path), recursive=job.recursive)

        if job.pattern:
            files = [f for f in files if fnmatch(f.name, job.pattern)]

        job.progress.total_files = len(files)
        self.queue.update_job(job)

        # Process each file
        for idx, file in enumerate(files):
            if job.status == JobStatus.CANCELLED:
                logger.info("Job cancelled", job_id=job.job_id)
                break

            result = await self._process_file(job, file)

            # Update progress
            job.progress.processed += 1
            if result.status == "success":
                job.progress.success += 1
            elif result.status == "skipped":
                job.progress.skipped += 1
            else:
                job.progress.failed += 1

            job.results.append(result)
            job.updated_at = datetime.now()

            # Save progress periodically
            if idx % 10 == 0:
                self.queue.update_job(job)

        # Complete job
        self.queue.complete_job(job.job_id)
        logger.info("Job completed",
                   job_id=job.job_id,
                   processed=job.progress.processed,
                   success=job.progress.success)

    async def _process_file(self, job: BatchJob, file: Path) -> FileResult:
        """Process single file."""
        start_time = time.time()

        try:
            result = await self.pipeline.process(file)

            return FileResult(
                file=str(file),
                status=result.status,
                message=result.message,
                duration_ms=int((time.time() - start_time) * 1000),
                timestamp=datetime.now()
            )

        except Exception as e:
            return FileResult(
                file=str(file),
                status="error",
                message=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
                timestamp=datetime.now()
            )
```

### API Routes

```python
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter()

@router.post("/batch", response_model=BatchResponse)
async def start_batch(request: BatchRequest, background_tasks: BackgroundTasks):
    """Start batch processing job."""
    app_state = request.app.state.arrtheaudio

    # Validate path
    path = Path(request.path)
    if not path.exists():
        raise HTTPException(400, f"Path not found: {path}")

    # Create job
    job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    job = BatchJob(
        job_id=job_id,
        status=JobStatus.QUEUED,
        path=str(path),
        recursive=request.recursive,
        pattern=request.pattern,
        dry_run=request.dry_run,
        priority=JobPriority.NORMAL,
        progress=JobProgress(0, 0, 0, 0, 0),
        results=[],
        started_at=datetime.now(),
        updated_at=datetime.now(),
        completed_at=None,
        error=None
    )

    # Enqueue job
    if not app_state.job_queue.enqueue(job):
        raise HTTPException(503, "Job queue full")

    return BatchResponse(
        status="started",
        batch_id=job_id,
        estimated_files=None,  # Unknown until scanned
        message="Batch job queued"
    )

@router.get("/batch/{job_id}")
async def get_batch(job_id: str):
    """Get batch job status."""
    app_state = request.app.state.arrtheaudio

    job = app_state.job_queue.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    return job

@router.delete("/batch/{job_id}")
async def cancel_batch(job_id: str):
    """Cancel batch job."""
    app_state = request.app.state.arrtheaudio

    if not app_state.job_queue.cancel_job(job_id):
        raise HTTPException(404, "Job not found or already completed")

    return {"status": "cancelled", "message": "Job cancelled"}

@router.get("/jobs")
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0)
):
    """List all jobs."""
    app_state = request.app.state.arrtheaudio

    jobs = app_state.job_queue.list_jobs(status, limit, offset)

    return {
        "jobs": jobs,
        "total": len(jobs),
        "limit": limit,
        "offset": offset
    }

@router.get("/jobs/stats")
async def get_stats():
    """Get job statistics."""
    app_state = request.app.state.arrtheaudio

    return app_state.job_queue.get_stats()
```

## Configuration

Add to `config.yaml`:

```yaml
jobs:
  max_queue_size: 100
  max_concurrent: 2
  storage_path: /config/jobs.db
  retention_days: 30  # Keep job history for 30 days
  cleanup_interval_hours: 24
```

## Implementation Steps

### Step 1: Job Models (1 day)
1. Create `jobs/models.py` with data classes
2. Add JobStatus and JobPriority enums
3. Implement JobProgress calculations
4. Unit tests for models

### Step 2: Job Storage (1-2 days)
1. Create `jobs/storage.py` with SQLite backend
2. Implement CRUD operations
3. Add job history queries
4. Add cleanup for old jobs
5. Unit tests

### Step 3: Job Queue (1-2 days)
1. Create `jobs/queue.py` with priority queue
2. Implement enqueue/dequeue logic
3. Add job status tracking
4. Integration with storage
5. Unit tests

### Step 4: Job Worker (2-3 days)
1. Create `jobs/worker.py` with async workers
2. Implement job processing loop
3. Add progress tracking
4. Add cancellation support
5. Unit tests with mocked pipeline

### Step 5: API Routes (1-2 days)
1. Add batch endpoints to `api/routes.py`
2. Add job management endpoints
3. Implement filtering and pagination
4. Add statistics endpoint
5. Integration tests

### Step 6: Webhook Multi-File Support (1 day)
1. Update webhook routes to process all files in array
2. Return webhook_id and job_ids array
3. Update response models
4. Integration tests with multi-file payloads

### Step 7: Integration (1 day)
1. Update app startup to initialize job queue
2. Start worker pool on daemon start
3. Graceful shutdown of workers
4. Update health check to include queue status

### Step 8: Testing (2 days)
1. Unit tests for all job components
2. Integration tests for batch API
3. Integration tests for multi-file webhooks
4. Load testing with large queues
5. Test worker concurrency
6. Test MP4 resource limiting

### Step 9: Documentation (1 day)
1. Update README with batch processing examples
2. Add API documentation
3. Update troubleshooting guide
4. Document queue management best practices

## Testing Requirements

### Unit Tests
- Job models and calculations
- Job storage CRUD operations
- Queue enqueue/dequeue logic
- Worker job processing
- API endpoint validation

### Integration Tests
- End-to-end batch processing
- Multi-file webhook processing
- Job cancellation
- Queue overflow handling
- Worker concurrency
- MP4 resource limiting

### Load Testing
```bash
# Test with large queue
python scripts/test-batch-load.py --files 1000 --workers 4

# Test webhook flood
python scripts/test-webhook-flood.py --count 100
```

## Success Criteria

- [ ] Multi-file webhooks process all files
- [ ] Manual batch scans work correctly
- [ ] Persistent queue survives restarts
- [ ] Workers process jobs concurrently
- [ ] MP4 resource limits enforced
- [ ] Progress tracking accurate
- [ ] Job cancellation works
- [ ] All tests pass with >70% coverage
- [ ] Documentation complete

## Breaking Changes

**Webhook Response Format Change:**

**Before:**
```json
{
  "status": "accepted",
  "job_id": "job_abc123",
  "message": "File queued for processing"
}
```

**After:**
```json
{
  "status": "accepted",
  "webhook_id": "webhook_xyz789",
  "job_ids": ["job_1", "job_2", "job_3"],
  "file_count": 3,
  "message": "3 files queued for processing"
}
```

**Migration:**
- Single-file webhooks still work (job_ids will have 1 element)
- Clients should check `file_count` or `job_ids` length
- `webhook_id` can be used to track all related jobs

## Performance Expectations

| Operation | Expected Time | Notes |
|-----------|---------------|-------|
| Queue 100 jobs | <1 second | Just adding to queue |
| Process 100 MKV files (2 workers) | ~15 minutes | 300ms/file, 50 per worker |
| Process 100 MP4 files (1 worker) | ~40 minutes | 25s/file, serialized |
| Batch scan 1000 files | ~1 second | Just discovery |

## Rollback Plan

If Phase 5 causes issues:
1. Set `processing.worker_count: 0` to disable background workers
2. Webhooks will process files immediately (blocking, like Phase 2)
3. Batch API will return 503 Service Unavailable
4. Queue will remain but not process

## Future Enhancements (Phase 6+)

- WebSocket for real-time progress updates
- Distributed workers across multiple nodes
- Redis instead of SQLite for multi-instance support
- Job scheduling (cron-like batches)
- Job dependencies (process file A before file B)
- Bandwidth throttling for network storage
2. Add graceful shutdown
3. Update health check to include job stats
4. End-to-end testing

### Step 7: Documentation (1 day)
1. API documentation with examples
2. Update README
3. Add batch processing guide
4. Troubleshooting section

## Testing Requirements

### Unit Tests
- Job models and calculations
- Job queue operations
- Job storage CRUD
- Worker processing logic
- API endpoint handlers

### Integration Tests
- Full batch job flow
- Job cancellation
- Concurrent jobs
- Queue overflow handling
- Job persistence across restarts

### Load Testing
- Multiple concurrent jobs
- Large batch jobs (1000+ files)
- Queue capacity
- Worker performance

## Success Criteria

- [ ] Batch API functional and tested
- [ ] Jobs persist across daemon restarts
- [ ] Progress tracking accurate
- [ ] Cancellation works correctly
- [ ] Concurrent jobs don't interfere
- [ ] API documentation complete
- [ ] Performance acceptable (see below)
- [ ] All tests pass with >70% coverage

## Performance Expectations

- Job startup latency: <1 second
- Progress update interval: ~10 files
- Max concurrent jobs: 2 (configurable)
- Queue capacity: 100 jobs
- Job history retention: 30 days (configurable)

## Breaking Changes

None - this is additive functionality.

## Future Enhancements (Phase 6+)

- WebSocket for real-time progress
- Job scheduling (cron-like)
- Email notifications on completion
- Job templates/presets
- Distributed processing (multiple workers)

## Notes

- Jobs persist in SQLite database
- Workers use asyncio for concurrency
- Priority queue ensures webhooks processed first
- Old jobs auto-cleaned after retention period
- API follows REST conventions

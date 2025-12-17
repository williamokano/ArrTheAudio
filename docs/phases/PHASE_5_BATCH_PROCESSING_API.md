# Phase 5: Batch Processing API

**Status:** 🚧 Planned
**Goal:** Add REST API for batch processing and job management
**Estimated Duration:** 1-2 weeks

## Overview

Phase 5 extends the daemon with a full-featured batch processing API. While Phase 2 added webhook support for real-time processing, Phase 5 adds the ability to manually trigger scans, monitor progress, and manage batch jobs through REST endpoints.

## Features

### 1. Batch Processing Endpoint
- POST `/batch` - Start new batch scan
- Support for path patterns and filters
- Configurable options (dry-run, recursive, etc.)
- Background job execution

### 2. Job Management
- GET `/jobs` - List all jobs
- GET `/jobs/{id}` - Get job details
- DELETE `/jobs/{id}` - Cancel job
- Job status tracking (queued, running, completed, failed)

### 3. Job Queue
- Persistent job queue (Redis or SQLite)
- Concurrent job execution with worker pool
- Priority support (webhook > manual batch)
- Job retry on failure

### 4. Progress Tracking
- Real-time progress updates
- Files processed / total files
- Success / failure counts
- Estimated time remaining

### 5. Job History
- Store completed job results
- Query historical jobs
- Job logs and errors
- Cleanup old jobs

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

### Step 6: Integration (1 day)
1. Update app startup to start workers
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

# Technical Debt & Future Improvements

This document tracks known issues, technical debt, and future improvements for ArrTheAudio.

---

## Testing

### Missing Integration Tests for MP4 Processing

**Status:** 📋 To Do
**Priority:** Medium
**Phase:** 4 (MP4 Support)

**Issue:**
While MP4 support has comprehensive unit tests (22 tests with mocked subprocess calls), there are no integration tests with real MP4 files. All current testing uses mocks and doesn't verify actual ffmpeg behavior with real video files.

**Current Coverage:**
- ✅ Unit tests with mocked ffmpeg/ffprobe (77% coverage of executor.py)
- ✅ Command building logic verified
- ✅ Error handling paths tested
- ❌ No tests with real MP4 files
- ❌ No tests with different codecs (h264, h265, av1, etc.)
- ❌ No tests with various audio formats (AAC, AC3, DTS, etc.)
- ❌ No performance benchmarking

**Why This Matters:**
- Real ffmpeg behavior might differ from mocked behavior
- Codec compatibility issues wouldn't be caught
- Performance characteristics unknown
- Edge cases with malformed files untested

**Proposed Solution:**

1. **Create Test Fixtures**
   ```bash
   # Generate small test files for different scenarios
   tests/fixtures/
   ├── mp4_dual_audio_aac.mp4      # Standard case: 2 AAC tracks
   ├── mp4_multi_audio_mixed.mp4   # Mixed codecs: AAC + AC3
   ├── mp4_single_audio.mp4        # Edge case: 1 track
   ├── mp4_many_audio.mp4          # Edge case: 5+ tracks
   └── mp4_4k_large.mp4            # Performance test: large file
   ```

2. **Integration Test Structure**
   ```python
   # tests/integration/test_mp4_processing.py

   @pytest.mark.integration
   @pytest.mark.skipif(not has_fixtures(), reason="Test fixtures not available")
   class TestMP4Integration:
       """Integration tests with real MP4 files."""

       def test_process_dual_audio_mp4(self):
           """Test processing MP4 with dual audio tracks."""
           # Real ffmpeg execution, verify disposition changes

       def test_process_large_mp4_performance(self):
           """Test processing large MP4 within timeout."""
           # Verify timeout handling with real large files

       def test_rollback_on_real_failure(self):
           """Test rollback with actual filesystem operations."""
           # Kill ffmpeg mid-process, verify backup restoration
   ```

3. **Fixture Generation Script**
   ```bash
   # scripts/generate-test-fixtures.sh
   # Creates small MP4 files with various configurations
   # Can be run manually or in CI for deep integration testing
   ```

**Workarounds:**
- Rely on manual testing with user-provided files
- Unit tests provide good coverage of logic paths
- Docker build includes ffmpeg, so basic availability is verified

**Effort Estimate:** 2-3 days
- 1 day: Create fixture generation scripts
- 1 day: Write integration tests
- 0.5 day: Set up optional CI integration testing

**Related Issues:** None yet

---

## Performance

### No Performance Metrics for MP4 Remuxing

**Status:** 📋 To Do
**Priority:** Low
**Phase:** 4 (MP4 Support)

**Issue:**
MP4 processing time is estimated at "~5-30 seconds" but not measured. No metrics on:
- Average remux time by file size
- Disk I/O patterns
- Memory usage during remux
- CPU utilization

**Proposed Solution:**
- Add benchmarking script with sample files
- Collect metrics: `scripts/benchmark-mp4.sh`
- Document performance characteristics in README

**Effort Estimate:** 1-2 days

---

## Code Quality

### Pydantic v2 Deprecation Warnings

**Status:** ⚠️ Warning
**Priority:** Medium
**Phase:** All

**Issue:**
Tests show deprecation warnings:
```
PydanticDeprecatedSince20: Support for class-based `config` is deprecated,
use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0.
```

**Location:**
- Likely in `src/arrtheaudio/api/models.py` webhook payload models

**Proposed Solution:**
- Migrate from class-based `Config` to `ConfigDict`
- Example:
  ```python
  # Old
  class SonarrWebhookPayload(BaseModel):
      class Config:
          populate_by_name = True

  # New
  class SonarrWebhookPayload(BaseModel):
      model_config = ConfigDict(populate_by_name=True)
  ```

**Effort Estimate:** 1 day

---

### httpx Deprecation Warning

**Status:** ⚠️ Warning
**Priority:** Low
**Phase:** Testing

**Issue:**
```
DeprecationWarning: The 'app' shortcut is now deprecated.
Use the explicit style 'transport=WSGITransport(app=...)' instead.
```

**Location:**
- Test setup in `tests/integration/test_webhook.py`

**Proposed Solution:**
- Update test client initialization to use new httpx API

**Effort Estimate:** 0.5 day

---

## Critical Bugs

### Webhook Multi-File Bug - Only First File Processed

**Status:** 🐛 **CRITICAL BUG** - Will be fixed in Phase 5
**Priority:** High
**Phase:** 5 (Unified Job Queue & Batch Processing)

**Issue:**
When Sonarr/Radarr sends webhooks with multiple files (e.g., season pack imports, batch imports), **only the first file is processed and the rest are silently dropped**.

**Current Behavior:**
```python
# models.py line 84-88
@property
def episode_file_path(self) -> Optional[str]:
    """Get episode file path (from first file in array)."""
    if self.episodeFiles and len(self.episodeFiles) > 0:
        return self.episodeFiles[0].path  # ← ONLY FIRST FILE!
    return None
```

**When This Happens:**
- Batch imports - User manually imports multiple episodes
- Season packs - Downloading entire seasons
- Multi-episode files - Files with multiple episodes
- Re-imports - Replacing multiple existing files

**Example:**
```json
// Sonarr sends 3 files
{
  "episodeFiles": [
    {"path": "/media/Show/S01E01.mkv"},  // ← Processed
    {"path": "/media/Show/S01E02.mkv"},  // ← DROPPED!
    {"path": "/media/Show/S01E03.mkv"}   // ← DROPPED!
  ]
}
```

**Impact:**
- User expects all 3 files processed
- Only 1 file gets audio fixed
- No error or warning logged
- Silent data loss

**Fix (Phase 5):**
- Create one job per file (linked by webhook_id)
- Process all files via job queue
- Return array of job_ids

**Related Issues:** Phase 5 implementation

---

## Architecture

### No Concurrent Processing

**Status:** 📋 To Do - **Will be implemented in Phase 5**
**Priority:** Medium
**Phase:** 5 (Unified Job Queue & Batch Processing)

**Issue:**
Files currently processed sequentially via FastAPI BackgroundTasks. MP4 remuxing is CPU/IO intensive and blocks for 5-30 seconds per file. No support for concurrent processing or queue management.

**Current Behavior:**
- One file at a time via BackgroundTasks
- MP4 remux blocks for 5-30 seconds
- No queue, no priority system
- No progress tracking
- No way to cancel running operations

**Proposed Solution (Phase 5):**
- Unified job queue system (SQLite-based)
- Configurable worker pool (default: 2 workers)
- Priority system: webhooks (high) > manual batches (normal)
- MP4 resource limits: `max_mp4_concurrent: 1` for disk space safety
- Full monitoring APIs

**Effort Estimate:** Core part of Phase 5 implementation (2-3 weeks)

---

## Documentation

### Missing MP4 Troubleshooting Guide

**Status:** 📋 To Do
**Priority:** Low
**Phase:** 4 (MP4 Support)

**Issue:**
No documentation on common MP4 processing issues:
- "Insufficient disk space" errors
- "ffmpeg timeout" errors
- When to increase timeout_seconds
- How to verify ffmpeg version compatibility

**Proposed Solution:**
- Add troubleshooting section to README or WEBHOOK_SETUP.md
- Document common error messages and solutions

**Effort Estimate:** 0.5 day

---

## Security

### No Rate Limiting on Webhook Endpoints

**Status:** 📋 To Do
**Priority:** Medium
**Phase:** 6 (Production Hardening)

**Issue:**
Webhook endpoints have no rate limiting. A malicious or misconfigured Arr instance could spam the API with requests, causing:
- Queue exhaustion
- Disk space issues (MP4 temp files)
- CPU/memory exhaustion

**Current Mitigation:**
- HMAC signature validation prevents unauthorized requests
- BackgroundTasks has implicit queueing

**Proposed Solution:**
- Implement per-client rate limiting (Phase 6)
- Add queue size limits (already in config, needs enforcement)
- Monitor and alert on queue depth

**Effort Estimate:** Part of Phase 6 implementation

---

## Known Limitations

### MP4 Processing Not Truly Atomic

**Status:** ℹ️ Known Limitation
**Priority:** Low
**Phase:** 4 (MP4 Support)

**Issue:**
Despite "atomic" operations, there's a small window where:
1. Backup exists
2. Original still exists
3. Temp file exists

If the system crashes during this window, manual cleanup may be needed.

**Mitigation:**
- Temp files are prefixed with `.` (hidden)
- Cleanup is attempted in finally blocks
- Backup is only removed on success

**Proposed Solution:**
- Document this limitation
- Add cleanup script: `arrtheaudio admin cleanup-temp-files`

**Effort Estimate:** 1 day (admin CLI implementation)

---

### No Progress Tracking for MP4 Remux

**Status:** ℹ️ Known Limitation
**Priority:** Low
**Phase:** 4 (MP4 Support)

**Issue:**
Large MP4 files (>10 GB) can take minutes to remux, but there's no progress indicator. Users only see:
- "Processing..."
- (long wait)
- "Success" or timeout

**Proposed Solution:**
- Parse ffmpeg stderr for progress (complex, ffmpeg output varies)
- Add estimated time remaining based on file size
- WebSocket updates for real-time progress (Phase 5+)

**Effort Estimate:** 2-3 days

---

## Contributing

Want to tackle one of these items? Great!

1. Open an issue referencing this document
2. Discuss approach in the issue
3. Submit a PR when ready

For questions, open a discussion on GitHub.

---

## Changelog

| Date | Item | Action |
|------|------|--------|
| 2024-12-19 | Missing MP4 integration tests | Documented |
| 2024-12-19 | Pydantic v2 deprecation warnings | Documented |
| 2024-12-19 | httpx deprecation warning | Documented |
| 2024-12-19 | No MP4 performance metrics | Documented |
| 2024-12-19 | MP4 not truly atomic | Documented |
| 2024-12-19 | No MP4 progress tracking | Documented |
| 2024-12-19 | No rate limiting | Documented |
| 2024-12-19 | Missing troubleshooting guide | Documented |
| 2024-12-19 | No concurrent MP4 processing | Documented |

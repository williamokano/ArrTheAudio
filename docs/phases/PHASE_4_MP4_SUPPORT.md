# Phase 4: MP4 Support

**Status:** ✅ Complete
**Goal:** Add support for MP4 container format
**Completed:** December 2024

## Overview

Phase 4 extends ArrTheAudio to support MP4 files in addition to MKV. Unlike MKV which supports in-place metadata editing via mkvpropedit, MP4 requires remuxing with ffmpeg to change audio track flags. This phase implements safe, atomic MP4 processing with proper error handling.

## Key Differences: MKV vs MP4

| Feature | MKV (mkvpropedit) | MP4 (ffmpeg) |
|---------|-------------------|--------------|
| **Edit Type** | In-place metadata edit | Full remux required |
| **Speed** | ~200-300ms | ~5-30 seconds |
| **Disk Space** | None (in-place) | Temporary copy (~same size) |
| **Risk** | Very low | Low (with atomic operations) |
| **Tools** | mkvpropedit | ffmpeg |

## Features

### 1. MP4Executor
- FFmpeg-based remuxing
- Atomic file operations (temp → backup → replace)
- Progress tracking for large files
- Cleanup on failure
- Preservation of all streams (video, audio, subtitles)

### 2. Container Detection Enhancement
- Accurate MP4/M4V detection
- Support for MOV files
- File extension validation

### 3. Safety Features
- Atomic file replacement
- Backup creation before modification
- Rollback on failure
- Disk space verification

## Technical Details

### File Structure

```
src/arrtheaudio/core/
├── executor.py         # EXISTING - Add MP4Executor class
└── detector.py         # UPDATE - Better MP4 detection
```

### MP4 Executor Implementation

```python
import shutil
import tempfile
from pathlib import Path
from typing import Optional
import subprocess

class MP4Executor:
    """Executor for MP4 container format using ffmpeg remux."""

    def __init__(self, config):
        self.config = config
        self.ffmpeg_path = shutil.which("ffmpeg")
        if not self.ffmpeg_path:
            raise RuntimeError("ffmpeg not found in PATH")

    def set_default_audio(self, file_path: Path, track_index: int) -> bool:
        """Set default audio track for MP4 file.

        Process:
        1. Create temp output file
        2. Remux with ffmpeg, setting disposition
        3. Create backup of original
        4. Atomic replace original with temp
        5. Clean up

        Args:
            file_path: Path to MP4 file
            track_index: Audio track index to set as default (0-based)

        Returns:
            True if successful, False otherwise
        """
        logger.info("Setting default audio track for MP4",
                   file=str(file_path), track_index=track_index)

        # Check disk space (need ~2x file size)
        if not self._check_disk_space(file_path):
            logger.error("Insufficient disk space for MP4 processing")
            return False

        # Create temp file in same directory (for atomic move)
        temp_file = file_path.parent / f".{file_path.name}.tmp"
        backup_file = file_path.parent / f"{file_path.name}.bak"

        try:
            # Build ffmpeg command
            cmd = self._build_ffmpeg_command(file_path, temp_file, track_index)

            # Execute ffmpeg remux
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.processing.timeout_seconds
            )

            if result.returncode != 0:
                logger.error("ffmpeg failed",
                           returncode=result.returncode,
                           stderr=result.stderr)
                return False

            # Verify temp file was created and is valid
            if not temp_file.exists():
                logger.error("ffmpeg did not create output file")
                return False

            if temp_file.stat().st_size == 0:
                logger.error("ffmpeg created empty output file")
                temp_file.unlink()
                return False

            # Create backup of original
            shutil.copy2(file_path, backup_file)

            # Atomic replace
            temp_file.replace(file_path)

            # Remove backup on success
            backup_file.unlink()

            logger.info("Successfully updated MP4 file",
                       file=str(file_path),
                       track_index=track_index)
            return True

        except subprocess.TimeoutExpired:
            logger.error("ffmpeg timed out", file=str(file_path))
            self._cleanup_files([temp_file, backup_file])
            return False

        except Exception as e:
            logger.exception("MP4 processing failed", error=str(e))

            # Restore from backup if it exists
            if backup_file.exists():
                logger.info("Restoring from backup")
                shutil.copy2(backup_file, file_path)

            self._cleanup_files([temp_file, backup_file])
            return False

    def _build_ffmpeg_command(self, input_file: Path,
                             output_file: Path,
                             default_track_index: int) -> list[str]:
        """Build ffmpeg command for remuxing with audio disposition.

        Args:
            input_file: Source MP4 file
            output_file: Destination file
            default_track_index: Audio track to mark as default (0-based)

        Returns:
            Command list for subprocess
        """
        cmd = [
            self.ffmpeg_path,
            "-i", str(input_file),
            "-map", "0",  # Map all streams
            "-c", "copy",  # Copy codecs (no re-encode)
        ]

        # Get total audio track count
        track_count = self._get_audio_track_count(input_file)

        # Set disposition for each audio track
        for i in range(track_count):
            disposition = "default" if i == default_track_index else "0"
            cmd.extend([f"-disposition:a:{i}", disposition])

        # Output options
        cmd.extend([
            "-movflags", "+faststart",  # Optimize for streaming
            "-y",  # Overwrite output
            str(output_file)
        ])

        return cmd

    def _get_audio_track_count(self, file_path: Path) -> int:
        """Get number of audio tracks using ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-select_streams", "a",
            str(file_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return 0

        data = json.loads(result.stdout)
        return len(data.get("streams", []))

    def _check_disk_space(self, file_path: Path) -> bool:
        """Check if sufficient disk space for remuxing.

        Need at least 2x file size (original + temp).
        """
        file_size = file_path.stat().st_size
        required_space = file_size * 2

        stat = shutil.disk_usage(file_path.parent)
        available_space = stat.free

        if available_space < required_space:
            logger.warning("Insufficient disk space",
                          required_mb=required_space / 1024 / 1024,
                          available_mb=available_space / 1024 / 1024)
            return False

        return True

    def _cleanup_files(self, files: list[Path]):
        """Remove temporary/backup files."""
        for file in files:
            try:
                if file.exists():
                    file.unlink()
            except Exception as e:
                logger.warning("Failed to cleanup file",
                             file=str(file), error=str(e))
```

### Executor Factory Pattern

Update `executor.py` to select executor based on container type:

```python
class ExecutorFactory:
    """Factory for creating appropriate executor based on container."""

    @staticmethod
    def create(container_type: ContainerType, config) -> Executor:
        """Create executor for container type.

        Args:
            container_type: MKV or MP4
            config: Application configuration

        Returns:
            Appropriate executor instance

        Raises:
            ValueError: If container type not supported
        """
        if container_type == ContainerType.MKV:
            return MKVExecutor(config)
        elif container_type == ContainerType.MP4:
            return MP4Executor(config)
        else:
            raise ValueError(f"Unsupported container: {container_type}")
```

### Pipeline Integration

```python
class ProcessingPipeline:
    def process(self, file_path: Path, ...) -> ProcessResult:
        """Process file with automatic executor selection."""

        # Detect container
        container = self.detector.detect(file_path)

        if container == ContainerType.UNSUPPORTED:
            return ProcessResult(
                status="error",
                message="Unsupported container format"
            )

        # Get appropriate executor
        executor = ExecutorFactory.create(container, self.config)

        # ... rest of processing

        # Execute with selected executor
        if self.config.execution.dry_run:
            # Dry run
            return ProcessResult(status="dry_run", ...)
        else:
            success = executor.set_default_audio(file_path, selected.index)
            # ...
```

### Container Detection Enhancement

```python
class ContainerDetector:
    """Enhanced container detection with better MP4 support."""

    EXTENSIONS = {
        ContainerType.MKV: [".mkv", ".mka"],
        ContainerType.MP4: [".mp4", ".m4v", ".mov"],
    }

    def detect(self, file_path: Path) -> ContainerType:
        """Detect container type using ffprobe.

        Returns:
            ContainerType enum value
        """
        # Quick check by extension
        ext = file_path.suffix.lower()
        for container, exts in self.EXTENSIONS.items():
            if ext in exts:
                # Verify with ffprobe
                return self._verify_with_ffprobe(file_path, container)

        return ContainerType.UNSUPPORTED

    def _verify_with_ffprobe(self, file_path: Path,
                            expected: ContainerType) -> ContainerType:
        """Verify container type using ffprobe."""
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
               "-show_format", str(file_path)]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return ContainerType.UNSUPPORTED

        data = json.loads(result.stdout)
        format_name = data.get("format", {}).get("format_name", "")

        # Check if format matches expected container
        if expected == ContainerType.MKV and "matroska" in format_name:
            return ContainerType.MKV
        elif expected == ContainerType.MP4 and any(f in format_name for f in ["mp4", "mov", "m4a"]):
            return ContainerType.MP4

        return ContainerType.UNSUPPORTED
```

## Configuration

Add to `config.yaml`:

```yaml
containers:
  mkv: true   # Use mkvpropedit
  mp4: true   # Use ffmpeg remux

processing:
  timeout_seconds: 300  # Allow time for large MP4s
  max_file_size_gb: 50  # Reject files larger than this
```

## Implementation Steps

### Step 1: MP4 Executor (2-3 days)
1. Create `MP4Executor` class in `executor.py`
2. Implement ffmpeg command building
3. Add disk space checking
4. Implement atomic file operations
5. Add comprehensive error handling
6. Unit tests with mocked subprocess

### Step 2: Executor Factory (1 day)
1. Create `ExecutorFactory` in `executor.py`
2. Update pipeline to use factory
3. Add configuration support
4. Unit tests for factory logic

### Step 3: Enhanced Detection (1 day)
1. Update `ContainerDetector` class
2. Add MP4/MOV extension support
3. Improve ffprobe verification
4. Unit tests for detection

### Step 4: Integration (1 day)
1. Update pipeline to handle both formats
2. Update CLI output for MP4 processing
3. Add progress indicators for long operations
4. Integration tests with sample files

### Step 5: Testing (2 days)
1. Unit tests for MP4 executor
2. Integration tests with real MP4 files
3. Test edge cases (large files, corrupted files, no space)
4. Test rollback on failure
5. Performance testing

### Step 6: Documentation (1 day)
1. Update README with MP4 support
2. Update WEBHOOK_SETUP.md
3. Add troubleshooting for MP4 issues
4. Document performance differences

## Testing Requirements

### Unit Tests
- MP4Executor command building
- Disk space checking
- Atomic operations
- Error handling and rollback
- ExecutorFactory selection logic

### Integration Tests
- Process real MP4 files
- Test with various sizes (small, medium, large)
- Test failure scenarios (no space, corrupted file)
- Verify audio track changes with ffprobe
- Test with multiple audio tracks

### Manual Testing
```bash
# Test MP4 processing
make build
docker run --rm -v $(pwd)/tests/fixtures:/media arrtheaudio:latest \
  arrtheaudio --config /config/config.yaml process "/media/sample.mp4"

# Verify result
ffprobe -v quiet -print_format json -show_streams -select_streams a "/path/to/sample.mp4"
```

## Success Criteria

- [ ] MP4 files processed successfully
- [ ] Atomic operations prevent file corruption
- [ ] Rollback works on failure
- [ ] Disk space checked before processing
- [ ] All streams preserved (video, audio, subs)
- [ ] Processing time acceptable (<30s for typical files)
- [ ] No breaking changes to MKV support
- [ ] All tests pass with >70% coverage
- [ ] Documentation complete

## Performance Expectations

| File Size | Expected Time | Notes |
|-----------|---------------|-------|
| <1 GB | 5-10 seconds | Fast |
| 1-5 GB | 10-20 seconds | Typical movie |
| 5-20 GB | 20-60 seconds | Large 4K movie |
| >20 GB | 60+ seconds | Very large/uncompressed |

Note: Times vary based on disk speed and CPU.

## Breaking Changes

None - MP4 support is additive.

## Rollback Plan

If MP4 processing causes issues:
1. Set `containers.mp4: false` in config
2. Only MKV files will be processed
3. MP4 files will be skipped with warning

## Known Limitations

1. **Slower than MKV** - Remuxing takes longer
2. **Disk space required** - Need 2x file size temporarily
3. **Not truly atomic** - Small window where both original and temp exist
4. **Limited progress tracking** - ffmpeg progress parsing is complex

## Safety Measures

1. **Backup creation** - Original saved before replacement
2. **Temp file validation** - Check size and existence
3. **Atomic replace** - Use `Path.replace()` for atomic move
4. **Cleanup on failure** - Remove temp files
5. **Disk space check** - Verify space before starting

## Future Enhancements (Phase 6+)

- Progress bars for large files
- Parallel processing of multiple MP4s
- Smart codec selection (prefer certain codecs)
- Hardware acceleration support (NVENC, Quick Sync)
- Resume interrupted operations

## Troubleshooting

### "Insufficient disk space"
- Free up space in media directory
- Process smaller files first
- Use external drive with more space

### "ffmpeg failed" with stderr
- Check ffmpeg version (need 4.0+)
- Verify file is valid MP4
- Check file permissions

### Processing takes too long
- Increase timeout in config
- Check disk speed (use SSD if possible)
- Consider skipping very large files

## Notes

- ffmpeg must be in PATH (included in Docker image)
- MP4 processing is CPU-bound (single-threaded)
- Original file modified only after successful remux
- Subtitles and chapters are preserved
- Metadata (title, year, etc.) is preserved

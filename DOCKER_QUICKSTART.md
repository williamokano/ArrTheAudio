# Docker Quick Start Guide

## Build the Image

```bash
cd /Users/williamokano/Workspace/Personal/ArrTheAudio
docker build -t arrtheaudio:latest .
```

## Usage Examples

### 1. Help Command

```bash
docker run --rm arrtheaudio:latest arrtheaudio --help
docker run --rm arrtheaudio:latest arrtheaudio scan --help
```

### 2. Scan a Directory (Dry Run - Safe Testing)

**Scan all video files in a directory:**

```bash
docker run --rm \
  -v /path/to/your/media:/media \
  -v $(pwd)/config:/config \
  -v $(pwd)/logs:/logs \
  arrtheaudio:latest \
  arrtheaudio --config /config/config-dryrun.yaml scan /media
```

**Scan only a specific season (no recursion):**

```bash
docker run --rm \
  -v /path/to/your/media:/media \
  -v $(pwd)/config:/config \
  -v $(pwd)/logs:/logs \
  arrtheaudio:latest \
  arrtheaudio --config /config/config-dryrun.yaml scan --no-recursive /media
```

**Scan with a pattern (only MKV files):**

```bash
docker run --rm \
  -v /path/to/your/media:/media \
  -v $(pwd)/config:/config \
  -v $(pwd)/logs:/logs \
  arrtheaudio:latest \
  arrtheaudio --config /config/config-dryrun.yaml scan --pattern "**/*.mkv" /media
```

### 3. Process a Single File (Dry Run - Safe Testing)

**Replace `/path/to/your/media` with your actual media directory:**

```bash
docker run --rm \
  -v /path/to/your/media:/media \
  -v $(pwd)/config:/config \
  -v $(pwd)/logs:/logs \
  arrtheaudio:latest \
  arrtheaudio --config /config/config-dryrun.yaml process /media/subfolder/video.mkv
```

**Example with real path:**

```bash
# If your video is at: /Users/you/Movies/Anime/Show/S01E01.mkv
docker run --rm \
  -v /Users/you/Movies:/media \
  -v $(pwd)/config:/config \
  -v $(pwd)/logs:/logs \
  arrtheaudio:latest \
  arrtheaudio --config /config/config-dryrun.yaml process /media/Anime/Show/S01E01.mkv
```

### 4. Scan a Directory (REAL - Actually Modify)

⚠️ **This WILL modify your files!**

```bash
docker run --rm \
  -v /path/to/your/media:/media \
  -v $(pwd)/config:/config \
  -v $(pwd)/logs:/logs \
  arrtheaudio:latest \
  arrtheaudio --config /config/config.yaml scan /media
```

### 5. Process a Single File (REAL - Actually Modify)

⚠️ **This WILL modify your file!**

```bash
docker run --rm \
  -v /path/to/your/media:/media \
  -v $(pwd)/config:/config \
  -v $(pwd)/logs:/logs \
  arrtheaudio:latest \
  arrtheaudio --config /config/config.yaml process /media/subfolder/video.mkv
```

### 6. Using the Helper Script

**Easier way:**

```bash
# Make script executable (first time only)
chmod +x scripts/docker-run.sh

# Run it
./scripts/docker-run.sh /path/to/your/media subfolder/video.mkv
```

**Example:**

```bash
./scripts/docker-run.sh ~/Videos anime/Attack_on_Titan/S01E01.mkv
```

## Volume Mappings Explained

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `/path/to/your/media` | `/media` | Your video files |
| `$(pwd)/config` | `/config` | Configuration files |
| `$(pwd)/logs` | `/logs` | Log output |

## Configuration Files

- **`config/config.yaml`** - Normal mode (WILL modify files)
- **`config/config-dryrun.yaml`** - Dry run mode (test only, no changes)

## Testing Workflow

1. **Build image:**
   ```bash
   docker build -t arrtheaudio:latest .
   ```

2. **Test with dry-run first:**
   ```bash
   docker run --rm \
     -v ~/Videos:/media \
     -v $(pwd)/config:/config \
     -v $(pwd)/logs:/logs \
     arrtheaudio:latest \
     arrtheaudio --config /config/config-dryrun.yaml process /media/test.mkv
   ```

3. **Check logs:**
   ```bash
   cat logs/arrtheaudio.log
   ```

4. **If looks good, run for real:**
   ```bash
   docker run --rm \
     -v ~/Videos:/media \
     -v $(pwd)/config:/config \
     -v $(pwd)/logs:/logs \
     arrtheaudio:latest \
     arrtheaudio --config /config/config.yaml process /media/test.mkv
   ```

## Troubleshooting

### "File not found"
- Make sure your volume mapping is correct
- The path inside the container must start with `/media/`
- Example: If host has `/Users/you/Videos/movie.mkv`, and you map `-v /Users/you/Videos:/media`, then use `/media/movie.mkv`

### "Permission denied"
- Docker needs read/write access to your media folder
- On Linux, you might need to run with `--user $(id -u):$(id -g)`

### Check if tools are available
```bash
docker run --rm arrtheaudio:latest ffprobe -version
docker run --rm arrtheaudio:latest mkvpropedit --version
```

## Interactive Shell (for debugging)

```bash
docker run --rm -it \
  -v /path/to/your/media:/media \
  -v $(pwd)/config:/config \
  -v $(pwd)/logs:/logs \
  arrtheaudio:latest \
  /bin/bash
```

Then inside the container:
```bash
arrtheaudio --config /config/config-dryrun.yaml process /media/video.mkv
```

## One-Liner for Quick Testing

```bash
docker build -t arrtheaudio:latest . && \
docker run --rm \
  -v ~/Videos:/media \
  -v $(pwd)/config:/config \
  -v $(pwd)/logs:/logs \
  arrtheaudio:latest \
  arrtheaudio --config /config/config-dryrun.yaml process /media/test.mkv
```

# Webhook Setup Guide - Sonarr & Radarr Integration

This guide shows you how to configure Sonarr and Radarr to automatically fix audio tracks when new files are downloaded.

## Overview

ArrTheAudio runs as a daemon and receives webhooks from Sonarr/Radarr. When a download completes, the daemon automatically:
1. Receives the webhook with file path
2. Maps the path from Arr → local filesystem
3. Analyzes audio tracks
4. Sets the correct default audio track
5. Logs the result

**Processing time:** ~200-300ms per file

---

## Prerequisites

- ArrTheAudio daemon running (via Docker Compose)
- Sonarr and/or Radarr installed and running
- Network connectivity between Arr apps and ArrTheAudio

---

## Step 1: Start ArrTheAudio Daemon

### Using Docker Compose

1. **Configure docker-compose.yml:**

```yaml
version: '3.8'

services:
  arrtheaudio:
    image: arrtheaudio:latest
    container_name: arrtheaudio
    restart: unless-stopped
    command: arrtheaudio --config /config/config.yaml daemon

    environment:
      - WEBHOOK_SECRET=your_secret_key_here  # Change this!
      - TMDB_API_KEY=${TMDB_API_KEY}         # Optional (Phase 3)

    volumes:
      - ./config:/config
      - /path/to/media:/media  # Your media folder
      - ./logs:/logs

    ports:
      - "9393:9393"

    networks:
      - arr-network

networks:
  arr-network:
    external: true
```

2. **Configure config.yaml:**

```yaml
language_priority:
  - eng
  - jpn

path_overrides:
  - path: "/media/anime/**"
    language_priority: [jpn, eng]

# IMPORTANT: Configure path mappings!
path_mappings:
  - remote: "/tv"              # Sonarr's path
    local: "/media/tv"          # Docker container's path
  - remote: "/movies"           # Radarr's path
    local: "/media/movies"

api:
  host: 0.0.0.0
  port: 9393
  webhook_secret: "${WEBHOOK_SECRET}"  # Must match docker-compose

execution:
  dry_run: false
  skip_if_correct: true
```

3. **Start the daemon:**

```bash
docker-compose up -d
```

4. **Verify it's running:**

```bash
curl http://localhost:9393/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "queue_size": 0,
  "uptime_seconds": 123.45,
  "checks": {
    "ffprobe": true,
    "mkvpropedit": true,
    "api": true
  }
}
```

---

## Step 2: Configure Path Mappings

**Critical:** Sonarr/Radarr and ArrTheAudio must agree on file paths!

### Understanding Path Mappings

- **Sonarr/Radarr path:** Where Arr apps think the files are
- **ArrTheAudio path:** Where the daemon can actually access them

### Example Scenario

**Your setup:**
- Sonarr root folder: `/tv`
- Docker media mount: `/data/media/tv`

**What happens:**
1. Sonarr downloads to `/tv/Show/S01E01.mkv`
2. Sonarr sends webhook with path: `/tv/Show/S01E01.mkv`
3. ArrTheAudio maps: `/tv` → `/media/tv`
4. ArrTheAudio processes: `/media/tv/Show/S01E01.mkv`

### Configure in config.yaml

```yaml
path_mappings:
  # Sonarr paths
  - remote: "/tv"
    local: "/media/tv"

  - remote: "/anime"
    local: "/media/anime"

  # Radarr paths
  - remote: "/movies"
    local: "/media/movies"
```

**Important:**
- First matching prefix wins
- Order matters (more specific first)
- Use absolute paths

---

## Step 3: Configure Sonarr

1. **Open Sonarr** → Settings → Connect

2. **Click** the "+" button → Select "Webhook"

3. **Configure webhook:**

   | Field | Value |
   |-------|-------|
   | Name | ArrTheAudio |
   | On Grab | ❌ No |
   | On Import | ✅ **Yes** |
   | On Upgrade | ✅ Yes (optional) |
   | On Rename | ❌ No |
   | On Series Delete | ❌ No |
   | On Episode File Delete | ❌ No |
   | On Health Issue | ❌ No |
   | Tags | (leave empty for all series) |

4. **Set webhook URL:**
   ```
   http://arrtheaudio:9393/webhook/sonarr
   ```

   Or if not on same Docker network:
   ```
   http://192.168.1.100:9393/webhook/sonarr
   ```

5. **Set Method:** POST

6. **Add Header** (for authentication):
   ```
   X-Webhook-Signature: your_secret_key_here
   ```
   ⚠️ Must match `WEBHOOK_SECRET` in docker-compose!

7. **Click "Test"** - Should see:
   ```
   ✓ Successfully sent webhook
   ```

8. **Save**

---

## Step 4: Configure Radarr

Same as Sonarr, but:

1. **Open Radarr** → Settings → Connect

2. **Webhook URL:**
   ```
   http://arrtheaudio:9393/webhook/radarr
   ```

3. **On Import:** ✅ Yes

4. **Header:**
   ```
   X-Webhook-Signature: your_secret_key_here
   ```

5. **Test and Save**

---

## Step 5: Test the Integration

### Manual Test

1. **Trigger a download in Sonarr/Radarr**

2. **Watch daemon logs:**
   ```bash
   docker logs -f arrtheaudio
   ```

3. **Expected log output:**
   ```json
   {"event": "Sonarr webhook received", "series_title": "Show Name", "file_path": "/tv/Show/S01E01.mkv"}
   {"event": "Path mapped", "remote_path": "/tv/Show/S01E01.mkv", "local_path": "/media/tv/Show/S01E01.mkv"}
   {"event": "File queued for processing", "file": "/media/tv/Show/S01E01.mkv", "job_id": "uuid"}
   {"event": "Processing file", "file": "/media/tv/Show/S01E01.mkv"}
   {"event": "Audio tracks analyzed", "languages": ["ita", "eng"], "track_count": 2}
   {"event": "Selected track from priority list", "language": "eng", "track_index": 1}
   {"event": "Successfully updated MKV", "file": "/media/tv/Show/S01E01.mkv"}
   ```

### Verify File

```bash
# Check audio tracks
docker exec arrtheaudio ffprobe -v quiet -print_format json -show_streams -select_streams a "/media/tv/Show/S01E01.mkv"

# Look for:
# "disposition": { "default": 1 }  on the English track
```

---

## Troubleshooting

### Webhook Not Received

**Check connectivity:**
```bash
# From Sonarr/Radarr container
curl http://arrtheaudio:9393/health
```

**Check Docker network:**
```bash
docker network ls
docker network inspect arr-network
```

Both containers must be on same network!

### "Invalid signature" Error

- Webhook secret in header must match `WEBHOOK_SECRET` in docker-compose
- Check Sonarr/Radarr logs for the exact signature being sent

### "File not found after path mapping"

**Path mapping is incorrect!**

1. Check Sonarr root folder: Settings → Media Management → Root Folders
2. Check ArrTheAudio mapping in config.yaml
3. Example:
   - Sonarr root: `/tv`
   - Docker volume: `/data/media/tv:/media/tv`
   - Mapping: `remote: "/tv"`, `local: "/media/tv"`

**Debug path mapping:**
```bash
# Check Sonarr's path
# In Sonarr webhook test, look at the JSON payload

# Check what ArrTheAudio sees
docker exec arrtheaudio ls -la /media/tv
```

### Track Not Changed

**Check logs for:**
- "Track already correct" - File already has correct default
- "No matching track found" - No track matches your priority list
- "Skipped (already_correct)" - Working as intended!

**Force reprocess:**
```yaml
execution:
  skip_if_correct: false  # Process even if already correct
```

---

## Security Considerations

### Webhook Secret

**ALWAYS set a webhook secret in production!**

```yaml
api:
  webhook_secret: "generate-a-strong-random-key-here"
```

Generate a secure secret:
```bash
openssl rand -base64 32
```

### Network Security

- Run on internal Docker network (not exposed to internet)
- Use reverse proxy (nginx/traefik) if external access needed
- Consider firewall rules

---

## Monitoring

### Health Check Endpoint

```bash
curl http://localhost:9393/health
```

### View Logs

```bash
# Real-time logs
docker logs -f arrtheaudio

# Last 100 lines
docker logs --tail 100 arrtheaudio

# Log file (JSON format)
cat logs/arrtheaudio.log | jq
```

### Metrics (Future)

Phase 6 will add Prometheus metrics at `/metrics`

---

## Advanced Configuration

### Multiple Path Mappings

```yaml
path_mappings:
  # Multiple Sonarr instances
  - remote: "/tv-hd"
    local: "/media/tv-hd"
  - remote: "/tv-4k"
    local: "/media/tv-4k"

  # Multiple Radarr instances
  - remote: "/movies-hd"
    local: "/media/movies-hd"
  - remote: "/movies-4k"
    local: "/media/movies-4k"
```

### Path-Specific Priorities

```yaml
path_overrides:
  - path: "/media/tv/Anime/**"
    language_priority: [jpn, eng]

  - path: "/media/tv/Korean/**"
    language_priority: [kor, eng]

  - path: "/media/movies/Bollywood/**"
    language_priority: [hin, eng]
```

---

## FAQ

**Q: Does this work with Plex/Jellyfin/Emby?**
A: Yes! It only modifies MKV metadata. Media servers will see the new default audio track immediately (may need to refresh metadata).

**Q: Does it re-encode the video?**
A: **No!** Only metadata is modified. Processing takes ~200ms per file.

**Q: Can I use this without Sonarr/Radarr?**
A: Yes! Use the `scan` command for batch processing instead of webhooks.

**Q: What if I have multiple audio tracks in the same language?**
A: It sets the first matching track as default. Future versions may add codec preferences.

**Q: Does it work with MP4 files?**
A: Not yet - Phase 4 will add MP4 support via ffmpeg.

---

## Support

- **Issues:** https://github.com/yourusername/ArrTheAudio/issues
- **Logs:** Always include logs when reporting issues
- **Config:** Sanitize secrets before sharing config files

---

## Summary Checklist

- [ ] ArrTheAudio daemon running
- [ ] Health check returns "healthy"
- [ ] Path mappings configured correctly
- [ ] Webhook secret set and matching
- [ ] Sonarr webhook configured and tested
- [ ] Radarr webhook configured and tested
- [ ] Test download completed successfully
- [ ] Logs show successful processing

**Congratulations!** Your audio tracks will now be automatically fixed on every download! 🎉

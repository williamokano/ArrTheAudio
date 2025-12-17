---
name: Bug Report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description

<!-- A clear and concise description of what the bug is -->

## Steps to Reproduce

1. Go to '...'
2. Configure '...'
3. Run command '...'
4. See error

## Expected Behavior

<!-- A clear and concise description of what you expected to happen -->

## Actual Behavior

<!-- What actually happened -->

## Environment

**ArrTheAudio Version:**
- Docker image tag: <!-- e.g., latest, v1.0.0 -->
- Or commit hash: <!-- if building from source -->

**Arr Stack:**
- Sonarr version: <!-- e.g., 4.0.0 -->
- Radarr version: <!-- e.g., 5.0.0 -->

**System:**
- OS: <!-- e.g., Ubuntu 22.04, macOS 13, Windows 11 -->
- Docker version: <!-- run: docker --version -->
- Docker Compose version: <!-- run: docker-compose --version -->

## Configuration

**config.yaml** (sanitize sensitive data!):
```yaml
# Paste relevant parts of your config here
```

**docker-compose.yml** (sanitize sensitive data!):
```yaml
# Paste relevant parts of your docker-compose here
```

## Logs

**ArrTheAudio logs:**
```
# Paste relevant logs here (docker logs arrtheaudio)
# Please include timestamps and sanitize any sensitive data
```

**Sonarr/Radarr webhook logs** (if applicable):
```
# Paste webhook-related logs from Sonarr/Radarr
```

## Sample File (if applicable)

**File that causes the issue:**
- File name: <!-- e.g., Show.S01E01.mkv -->
- Container: <!-- MKV or MP4 -->
- Audio tracks: <!-- list audio track languages -->

**ffprobe output:**
```bash
ffprobe -v quiet -print_format json -show_streams -select_streams a "filename.mkv"
```
```json
# Paste output here
```

## Screenshots

<!-- If applicable, add screenshots to help explain your problem -->

## Additional Context

<!-- Add any other context about the problem here -->

## Possible Solution

<!-- Optional: Suggest a fix or reason for the bug -->

## Checklist

- [ ] I have searched existing issues to ensure this is not a duplicate
- [ ] I have included all relevant logs
- [ ] I have sanitized sensitive data (API keys, paths, etc.)
- [ ] I have tested with the latest version

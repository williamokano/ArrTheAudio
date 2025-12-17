# Audio Default Track Fixer – Implementation Plan

## Purpose

Automatically ensure the **correct audio track is marked as default** in video files (MKV / MP4), prioritizing:

1. **Original language**, when determinable
2. Otherwise, a **configurable language priority list**

This tool is designed to:

- Repair large existing libraries
- Act as a **Sonarr/Radarr post-download hook**
- Run safely and repeatedly
- Complement Bazarr (subtitles) without overlap

---

## Core Requirements

### Functional

- Recursively scan folders OR process a single file
- Detect audio tracks and language metadata
- Select correct default audio track
- Modify container metadata **without re-encoding**
- Support MKV and MP4
- Log all actions and failures

### Non-Functional

- Linux-compatible
- Docker-friendly
- Idempotent
- Observable (structured logs)
- Extensible (future rules & heuristics)

---

## Supported Containers

| Container | Method                 | Tool        |
| --------- | ---------------------- | ----------- |
| MKV       | In-place metadata edit | mkvpropedit |
| MP4       | Remux (no re-encode)   | ffmpeg      |
| Other     | Skip + log             | —           |

---

## Language Selection Rules

### Decision Order

1. If **original language** is known AND present in audio tracks → select it
2. Else, select first match from **language priority list**
3. Else, do nothing and log

### Example Priority List

```yaml
language_priority:
  - eng
  - jpn
  - ita
  - spa
  - fre
```

---

## Metadata Resolution Strategy

### Resolution Order

1. **Sonarr / Radarr environment variables**
2. **TMDB API lookup**
3. Folder / filename heuristics
4. Fallback to priority list

### Metadata Output Model

```json
{
  "original_language": "eng",
  "source": "sonarr | radarr | tmdb | heuristic | none"
}
```

---

## System Architecture

```
┌─────────────┐
│ Entry Point │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ File Scanner│
└──────┬──────┘
       │
       ▼
┌────────────────┐
│ Container Type │
│   Detection    │
└──────┬─────────┘
       │
       ├─ MKV → mkvpropedit executor
       ├─ MP4 → ffmpeg remux executor
       └─ Other → log + skip
       ▼
┌────────────────┐
│ Audio Analyzer │
└──────┬─────────┘
       │
       ▼
┌────────────────┐
│ Language       │
│ Resolver       │
└──────┬─────────┘
       │
       ▼
┌────────────────┐
│ Track Selector │
└──────┬─────────┘
       │
       ▼
┌────────────────┐
│ Executor       │
└──────┬─────────┘
       │
       ▼
┌────────────────┐
│ Logger         │
└────────────────┘
```

---

## Entry Points

### CLI Commands

```bash
audio-fixer scan /media
audio-fixer process --file /media/show/episode.mkv
audio-fixer dry-run /media
```

---

## Sonarr / Radarr Integration

### Hook Type

- On Download / On Import

### Available Metadata (examples)

- `sonarr_series_title`
- `sonarr_series_id`
- `sonarr_episodefile_path`
- `radarr_movie_title`
- `radarr_movie_tmdbid`

---

## Docker Design

### Container Includes

- Python runtime
- ffmpeg
- mkvtoolnix
- jq

---

## Configuration (YAML)

```yaml
language_priority:
  - eng
  - jpn
  - ita

tmdb:
  enabled: true
  api_key: "${TMDB_API_KEY}"
  cache_ttl_days: 30

containers:
  mkv: true
  mp4: true

logging:
  format: json
  level: info
  output: /logs/audio-fixer.log
```

---

## Logging & Observability

### Log Format (JSON)

```json
{
  "file": "/media/show/S01E01.mkv",
  "container": "mkv",
  "audio_tracks": ["eng", "ita"],
  "selected_language": "eng",
  "selection_method": "original_language",
  "changed": true,
  "error": null
}
```

---

## Implementation Phases

1. Core Engine (MKV + priority)
2. MP4 Support
3. Arr Integration
4. TMDB Integration
5. Heuristics

---

## Expected Outcome

- Correct default audio across entire library
- Seamless Arr + Bazarr integration
- Safe, repeatable execution

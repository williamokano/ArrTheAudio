# ArrTheAudio

[![Tests](https://github.com/yourusername/arrtheaudio/actions/workflows/test.yml/badge.svg)](https://github.com/yourusername/arrtheaudio/actions/workflows/test.yml)
[![Release](https://github.com/yourusername/arrtheaudio/actions/workflows/release.yml/badge.svg)](https://github.com/yourusername/arrtheaudio/actions/workflows/release.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/yourusername/arrtheaudio)](https://hub.docker.com/r/yourusername/arrtheaudio)
[![License](https://img.shields.io/github/license/yourusername/arrtheaudio)](LICENSE)
[![codecov](https://codecov.io/gh/yourusername/arrtheaudio/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/arrtheaudio)

Automatic audio track fixer for Sonarr/Radarr (Arr stack). Ensures the correct audio track is set as default in video files based on original language or configurable priorities.

## Features

- **Automatic audio track selection** based on original language or priority
- **Path-specific language priorities** using glob patterns (e.g., prefer Japanese for `/anime/**` paths)
- **Path mappings** for Arr integration (translate Sonarr/Radarr paths to local filesystem)
- **MKV support** with in-place metadata editing (no re-encoding)
- **Non-destructive** - only modifies metadata, never re-encodes video
- **Idempotent** - safe to run multiple times on the same files
- **Structured JSON logging** for observability

## Current Status

**Phase 1 (MVP Core) - ✅ Complete**

- ✅ MKV support with mkvpropedit
- ✅ Language priority (global + path-specific overrides)
- ✅ Path mapping configuration
- ✅ CLI for processing single files and batch scanning
- ✅ Structured logging
- ✅ Unit tests

**Phase 2 (Daemon & Webhooks) - ✅ Complete**

- ✅ FastAPI webhook receiver on port 9393
- ✅ Sonarr/Radarr webhook integration
- ✅ HMAC signature authentication
- ✅ Path mapping (Arr → local filesystem)
- ✅ Background task processing
- ✅ Docker Compose deployment
- ✅ Integration tests
- ✅ Comprehensive setup documentation

**Coming Soon:**

- Phase 3: TMDB integration for automatic original language detection
- Phase 4: MP4 support with ffmpeg
- Phase 5: Batch processing API endpoint
- Phase 6: Production hardening (metrics, monitoring)

## Requirements

- Python 3.11+
- `ffprobe` (from ffmpeg)
- `mkvpropedit` (from mkvtoolnix)

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/ArrTheAudio.git
cd ArrTheAudio

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## Quick Start

### 1. Create Configuration

```bash
cp config.yaml.example config/config.yaml
```

Edit `config/config.yaml` to customize your language priorities and path overrides.

### 2. Process a File

```bash
# Using default configuration
python -m arrtheaudio process /path/to/video.mkv

# Using custom configuration
python -m arrtheaudio --config config/config.yaml process /path/to/video.mkv

# Or use the installed command
arrtheaudio process /path/to/video.mkv
```

## Configuration

### Basic Example

```yaml
# Global language priority (fallback order)
language_priority:
  - eng  # English
  - jpn  # Japanese
  - ita  # Italian

# Path-specific overrides
path_overrides:
  - path: "/media/anime/**"
    language_priority:
      - jpn  # Japanese first for anime
      - eng

# Execution
execution:
  dry_run: false          # Set true to test without changes
  skip_if_correct: true   # Skip if track already correct
```

### Path Override Examples

```yaml
path_overrides:
  # Anime: Prefer Japanese
  - path: "/media/anime/**"
    language_priority: [jpn, eng]

  # Korean shows: Prefer Korean
  - path: "/media/tv/Korean/**"
    language_priority: [kor, eng]

  # Bollywood: Prefer Hindi
  - path: "/media/movies/Bollywood/**"
    language_priority: [hin, eng]
```

### Path Mapping (for Arr Integration - Phase 2)

```yaml
path_mappings:
  - remote: "/tv"                # Sonarr's path
    local: "/data/media/tv"      # Daemon's path

  - remote: "/movies"            # Radarr's path
    local: "/data/media/movies"
```

## How It Works

1. **Container Detection**: Uses `ffprobe` to detect MKV/MP4/unsupported
2. **Audio Analysis**: Extracts all audio tracks with language metadata
3. **Language Resolution**: Determines original language (future: TMDB integration)
4. **Track Selection**:
   - If original language known → select it
   - Else → select first match from priority list (global or path-specific)
5. **Skip Check**: Skip if selected track is already default
6. **Execution**: Modify metadata using `mkvpropedit` (MKV) or `ffmpeg` (MP4, Phase 4)

## Language Selection Logic

### Priority Order

1. **Original Language** (if known and available)
2. **Path-Specific Priority** (if path matches a glob pattern)
3. **Global Priority** (fallback)

### Example

```yaml
language_priority: [eng, jpn]  # Global

path_overrides:
  - path: "/anime/**"
    language_priority: [jpn, eng]
```

For `/anime/Show/S01E01.mkv` with tracks: `[eng, jpn, ita]`
- Result: **Japanese** (matches path override)

For `/movies/Movie.mkv` with tracks: `[jpn, ita, spa]`
- Result: **Japanese** (first in global priority)

## Development

### Run Tests

```bash
pytest tests/ -v --cov=arrtheaudio
```

### Project Structure

```
ArrTheAudio/
├── src/arrtheaudio/
│   ├── config.py         # Configuration management
│   ├── cli.py            # CLI interface
│   ├── core/
│   │   ├── pipeline.py   # Main orchestrator
│   │   ├── selector.py   # Track selection logic
│   │   ├── executor.py   # File modification
│   │   ├── analyzer.py   # Audio track analysis
│   │   └── detector.py   # Container detection
│   ├── models/           # Data models
│   └── utils/            # Utilities (logging, etc.)
└── tests/
    ├── unit/             # Unit tests
    └── integration/      # Integration tests
```

## Roadmap

- [x] **Phase 1**: MVP Core (MKV + priority)
- [ ] **Phase 2**: Daemon & Webhooks
- [ ] **Phase 3**: TMDB Integration
- [ ] **Phase 4**: MP4 Support
- [ ] **Phase 5**: Batch Processing
- [ ] **Phase 6**: Production Hardening

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [Click](https://click.palletsprojects.com/) - CLI framework
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [structlog](https://www.structlog.org/) - Structured logging

## Support

- GitHub Issues: [Report bugs or request features](https://github.com/yourusername/ArrTheAudio/issues)
- Documentation: See the [plan document](audio-default-track-fixer-plan.md) for detailed architecture

---

Made with ❤️ for the Arr stack community

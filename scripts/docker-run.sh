#!/bin/bash
# Helper script to run ArrTheAudio in Docker

set -e

# Configuration
IMAGE_NAME="arrtheaudio:latest"
MEDIA_PATH="${1:-}"
VIDEO_FILE="${2:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function usage() {
    echo "Usage: $0 <media_path> <video_file>"
    echo ""
    echo "Examples:"
    echo "  $0 /path/to/media movies/Film.mkv"
    echo "  $0 ~/Videos anime/Show/S01E01.mkv"
    echo ""
    echo "The video_file is relative to media_path"
    exit 1
}

# Check arguments
if [ -z "$MEDIA_PATH" ] || [ -z "$VIDEO_FILE" ]; then
    usage
fi

# Check if media path exists
if [ ! -d "$MEDIA_PATH" ]; then
    echo -e "${RED}Error: Media path does not exist: $MEDIA_PATH${NC}"
    exit 1
fi

# Get absolute path
MEDIA_PATH=$(cd "$MEDIA_PATH" && pwd)

# Check if Docker image exists
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo -e "${YELLOW}Docker image not found. Building...${NC}"
    docker build -t "$IMAGE_NAME" .
fi

echo -e "${GREEN}Running ArrTheAudio in Docker...${NC}"
echo "Media path: $MEDIA_PATH"
echo "Video file: /media/$VIDEO_FILE"
echo ""

# Run in Docker
docker run --rm \
  -v "$MEDIA_PATH":/media \
  -v "$(pwd)/config":/config \
  -v "$(pwd)/logs":/logs \
  "$IMAGE_NAME" \
  arrtheaudio --config /config/config.yaml process "/media/$VIDEO_FILE"

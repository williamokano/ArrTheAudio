#!/bin/bash
# Test Sonarr webhook with real v4 payload

set -e

# Configuration
HOST="${HOST:-localhost}"
PORT="${PORT:-9393}"
BASE_URL="http://${HOST}:${PORT}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:-changeme}"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to calculate HMAC signature
calculate_signature() {
    local payload="$1"
    echo -n "$payload" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.* //'
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is required but not installed${NC}"
    echo "Install with: brew install jq (macOS) or apt install jq (Linux)"
    exit 1
fi

echo "=========================================="
echo "ArrTheAudio Sonarr Webhook Test"
echo "=========================================="
echo ""
echo "Target: ${BASE_URL}/webhook/sonarr"
echo "Webhook Secret: ${WEBHOOK_SECRET}"
echo ""

# Real Sonarr v4 Download event payload
sonarr_payload='{
  "series": {
    "id": 452,
    "title": "My Status as an Assassin Obviously Exceeds the Hero'"'"'s",
    "titleSlug": "my-status-as-an-assassin-obviously-exceeds-the-heros",
    "path": "/media/Animes/My Status as an Assassin Obviously Exceeds the Hero'"'"'s",
    "tvdbId": 460341,
    "tvMazeId": 0,
    "tmdbId": 284644,
    "imdbId": "tt36230718",
    "type": "standard",
    "year": 2025,
    "genres": [
      "Animation",
      "Anime",
      "Fantasy"
    ],
    "tags": [
      "anime"
    ],
    "originalLanguage": {
      "id": 8,
      "name": "Japanese"
    }
  },
  "episodes": [
    {
      "id": 17939,
      "episodeNumber": 11,
      "seasonNumber": 1,
      "title": "The Assassin Browses",
      "overview": "Akira and the others investigate the Uruk City Adventurer'"'"'s Guild to obtain information about Gram.",
      "airDate": "2025-12-16",
      "airDateUtc": "2025-12-15T16:30:00Z",
      "seriesId": 452,
      "tvdbId": 11386120
    }
  ],
  "episodeFiles": [
    {
      "id": 19264,
      "relativePath": "Season 1/My Status as an Assassin Obviously Exceeds the Hero'"'"'s - S01E11 - The Assassin Browses WEBDL-1080p VARYG.mkv",
      "path": "/media/Animes/My Status as an Assassin Obviously Exceeds the Hero'"'"'s/Season 1/My Status as an Assassin Obviously Exceeds the Hero'"'"'s - S01E11 - The Assassin Browses WEBDL-1080p VARYG.mkv",
      "quality": "WEBDL-1080p",
      "qualityVersion": 1,
      "releaseGroup": "VARYG",
      "sceneName": "My Status as an Assassin Obviously Exceeds the Heros S01E11 1080p NF WEB-DL AAC2.0 H 264-VARYG",
      "size": 916240797,
      "dateAdded": "2025-12-18T15:07:05.3944668Z",
      "languages": [
        {
          "id": 8,
          "name": "Japanese"
        }
      ],
      "mediaInfo": {
        "audioChannels": 2,
        "audioCodec": "AAC",
        "audioLanguages": [
          "jpn"
        ],
        "height": 1080,
        "width": 1920,
        "subtitles": [
          "eng",
          "ind",
          "may",
          "tha",
          "vie",
          "chi"
        ],
        "videoCodec": "x264",
        "videoDynamicRange": "",
        "videoDynamicRangeType": ""
      }
    }
  ],
  "downloadClient": "qbittorrent_local",
  "downloadClientType": "qBittorrent",
  "downloadId": "D199DBB9161A3EE6B855F5BDFCBC3B27CB9C070E",
  "release": {
    "releaseTitle": "My Status as an Assassin Obviously Exceeds the Heros S01E11 1080p NF WEB DL AAC2 0 H 264 VARYG",
    "indexer": "LimeTorrents (Prowlarr)",
    "size": 916245696,
    "releaseType": "singleEpisode"
  },
  "fileCount": 1,
  "sourcePath": "/media/Downloads/My.Status.as.an.Assassin.Obviously.Exceeds.the.Heros.S01E11.1080p.NF.WEB-DL.AAC2.0.H.264-VARYG.mkv",
  "destinationPath": "/media/Animes/My Status as an Assassin Obviously Exceeds the Hero'"'"'s/Season 1",
  "eventType": "Download",
  "instanceName": "Sonarr",
  "applicationUrl": ""
}'

echo -e "${YELLOW}Testing: Sonarr Download Event${NC}"
echo "Payload:"
echo "$sonarr_payload" | jq .

# Calculate signature
signature=$(calculate_signature "$sonarr_payload")

# Send request
echo -e "\nSending request..."
response=$(curl -s -w "\n%{http_code}" -X POST \
    "${BASE_URL}/webhook/sonarr" \
    -H "Content-Type: application/json" \
    -H "X-Webhook-Signature: ${signature}" \
    -d "$sonarr_payload")

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ Success (HTTP ${http_code})${NC}"
    echo "$body" | jq .
else
    echo -e "${RED}✗ Failed (HTTP ${http_code})${NC}"
    echo "$body"
fi
echo ""

echo "=========================================="
echo "Test Complete"
echo "=========================================="

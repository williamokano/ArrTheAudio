#!/bin/bash
# Test Radarr webhook with real v4 payload

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
echo "ArrTheAudio Radarr Webhook Test"
echo "=========================================="
echo ""
echo "Target: ${BASE_URL}/webhook/radarr"
echo "Webhook Secret: ${WEBHOOK_SECRET}"
echo ""

# Real Radarr v4 Download event payload
radarr_payload='{
  "movie": {
    "id": 432,
    "title": "28 Days Later",
    "year": 2002,
    "releaseDate": "2003-06-04",
    "folderPath": "/media/Movies/28 Days Later (2002)",
    "tmdbId": 170,
    "imdbId": "tt0289043",
    "overview": "Twenty-eight days after a killer virus was accidentally unleashed from a British research facility, a small group of London survivors are caught in a desperate struggle to protect themselves from the infected. Carried by animals and humans, the virus turns those it infects into homicidal maniacs -- and it'"'"'s absolutely impossible to contain.",
    "genres": [
      "Horror",
      "Thriller",
      "Science Fiction"
    ],
    "tags": [],
    "originalLanguage": {
      "id": 1,
      "name": "English"
    }
  },
  "remoteMovie": {
    "tmdbId": 170,
    "imdbId": "tt0289043",
    "title": "28 Days Later",
    "year": 2002
  },
  "movieFile": {
    "id": 356,
    "relativePath": "28.Days.Later.2002.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265.mkv",
    "path": "/media/Movies/28 Days Later (2002)/28.Days.Later.2002.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265.mkv",
    "quality": "Bluray-1080p",
    "qualityVersion": 1,
    "releaseGroup": "GalaxyRG265",
    "sceneName": "28.Days.Later.2002.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265",
    "indexerFlags": "G_Freeleech",
    "size": 3591895998,
    "dateAdded": "2025-12-18T15:14:59.7111117Z",
    "languages": [
      {
        "id": 1,
        "name": "English"
      }
    ],
    "mediaInfo": {
      "audioChannels": 5.1,
      "audioCodec": "EAC3",
      "audioLanguages": [
        "eng"
      ],
      "height": 1040,
      "width": 1920,
      "subtitles": [
        "eng"
      ],
      "videoCodec": "x265",
      "videoDynamicRange": "",
      "videoDynamicRangeType": ""
    },
    "sourcePath": "/media/Downloads/28.Days.Later.2002.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265[TGx]/28.Days.Later.2002.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265.mkv"
  },
  "isUpgrade": false,
  "downloadClient": "qbittorrent_local",
  "downloadClientType": "qBittorrent",
  "downloadId": "0283C5676D83B6E6CCEEC3F732EE2C563042C692",
  "customFormatInfo": {
    "customFormats": [],
    "customFormatScore": 0
  },
  "release": {
    "releaseTitle": "28.Days.Later.2002.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265",
    "indexer": "The Pirate Bay (Prowlarr)",
    "size": 3591896576,
    "indexerFlags": [
      "G_Freeleech"
    ]
  },
  "eventType": "Download",
  "instanceName": "Radarr",
  "applicationUrl": ""
}'

echo -e "${YELLOW}Testing: Radarr Download Event${NC}"
echo "Payload:"
echo "$radarr_payload" | jq .

# Calculate signature
signature=$(calculate_signature "$radarr_payload")

# Send request
echo -e "\nSending request..."
response=$(curl -s -w "\n%{http_code}" -X POST \
    "${BASE_URL}/webhook/radarr" \
    -H "Content-Type: application/json" \
    -H "X-Webhook-Signature: ${signature}" \
    -d "$radarr_payload")

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

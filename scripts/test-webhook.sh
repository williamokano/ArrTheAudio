#!/bin/bash
# Test webhook endpoints with simulated Sonarr/Radarr requests

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

# Function to test endpoint
test_endpoint() {
    local endpoint="$1"
    local payload="$2"
    local description="$3"

    echo -e "${YELLOW}Testing: ${description}${NC}"
    echo "Endpoint: ${endpoint}"
    echo "Payload:"
    echo "$payload" | jq .

    # Calculate signature
    signature=$(calculate_signature "$payload")

    # Send request
    echo -e "\nSending request..."
    response=$(curl -s -w "\n%{http_code}" -X POST \
        "${BASE_URL}${endpoint}" \
        -H "Content-Type: application/json" \
        -H "X-Webhook-Signature: ${signature}" \
        -d "$payload")

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
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is required but not installed${NC}"
    echo "Install with: brew install jq (macOS) or apt install jq (Linux)"
    exit 1
fi

echo "=========================================="
echo "ArrTheAudio Webhook Testing"
echo "=========================================="
echo ""
echo "Target: ${BASE_URL}"
echo "Webhook Secret: ${WEBHOOK_SECRET}"
echo ""

# Test 1: Sonarr webhook (TV show)
sonarr_payload='{
  "eventType": "Download",
  "series": {
    "id": 1,
    "title": "PLUR1BUS",
    "tvdbId": 12345,
    "imdbId": "tt1234567"
  },
  "episodes": [
    {
      "id": 1,
      "episodeNumber": 1,
      "seasonNumber": 1,
      "title": "We is Us"
    }
  ],
  "episodeFile": {
    "id": 1,
    "path": "/media/Season 1/PLUR1BUS - S01E01 - We is Us WEBDL-1080p MeM.mkv"
  }
}'

test_endpoint "/webhook/sonarr" "$sonarr_payload" "Sonarr Download Event (TV Show)"

# Test 2: Radarr webhook (Movie)
radarr_payload='{
  "eventType": "Download",
  "movie": {
    "id": 1,
    "title": "The Matrix",
    "year": 1999,
    "tmdbId": 603,
    "imdbId": "tt0133093"
  },
  "movieFile": {
    "id": 1,
    "relativePath": "The Matrix (1999)/The Matrix (1999) - 1080p.mkv"
  }
}'

test_endpoint "/webhook/radarr" "$radarr_payload" "Radarr Download Event (Movie)"

# Test 3: Health check
echo -e "${YELLOW}Testing: Health Check${NC}"
echo "Endpoint: /health"
echo ""

health_response=$(curl -s -w "\n%{http_code}" "${BASE_URL}/health")
http_code=$(echo "$health_response" | tail -n1)
body=$(echo "$health_response" | head -n-1)

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ Health check passed${NC}"
    echo "$body" | jq .
else
    echo -e "${RED}✗ Health check failed (HTTP ${http_code})${NC}"
    echo "$body"
fi
echo ""

echo "=========================================="
echo "Testing Complete"
echo "=========================================="

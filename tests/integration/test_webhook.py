"""Integration tests for webhook endpoints."""

import hmac
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from arrtheaudio.api.app import create_app
from arrtheaudio.config import Config, PathMapping, APIConfig


@pytest.fixture
def webhook_config(tmp_path):
    """Create configuration for webhook testing."""
    # Create test media directory
    media_dir = tmp_path / "media"
    media_dir.mkdir()

    # Create a test file
    test_file = media_dir / "test_show" / "S01E01.mkv"
    test_file.parent.mkdir(parents=True)
    test_file.touch()

    return Config(
        language_priority=["eng", "jpn"],
        path_mappings=[
            PathMapping(remote="/tv", local=str(media_dir)),
            PathMapping(remote="/movies", local=str(media_dir)),
        ],
        api=APIConfig(
            host="0.0.0.0",
            port=9393,
            webhook_secret="test_secret_key",
        ),
    )


@pytest.fixture
def test_client(webhook_config):
    """Create a test client for the FastAPI app."""
    app = create_app(webhook_config)
    return TestClient(app)


def create_signature(payload: dict, secret: str) -> str:
    """Create HMAC signature for webhook payload.

    Args:
        payload: Webhook payload dictionary
        secret: Shared secret

    Returns:
        HMAC signature as hex string
    """
    body = json.dumps(payload).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestSonarrWebhook:
    """Tests for Sonarr webhook endpoint."""

    def test_sonarr_webhook_success(self, test_client, webhook_config):
        """Test successful Sonarr webhook processing."""
        payload = {
            "eventType": "Download",
            "series": {
                "id": 1,
                "title": "Test Show",
                "tvdbId": 12345,
                "imdbId": "tt1234567",
            },
            "episodes": [
                {
                    "id": 1,
                    "seasonNumber": 1,
                    "episodeNumber": 1,
                }
            ],
            "episodeFile": {
                "id": 1,
                "path": "/tv/test_show/S01E01.mkv",
            },
        }

        signature = create_signature(payload, "test_secret_key")

        with patch("arrtheaudio.api.routes.ProcessingPipeline") as mock_pipeline:
            # Mock the pipeline to avoid actual processing
            mock_result = Mock()
            mock_result.status = "success"
            mock_pipeline.return_value.process.return_value = mock_result

            response = test_client.post(
                "/webhook/sonarr",
                json=payload,
                headers={"X-Webhook-Signature": signature},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "job_id" in data

    def test_sonarr_webhook_invalid_signature(self, test_client):
        """Test Sonarr webhook with invalid signature."""
        payload = {
            "eventType": "Download",
            "series": {"id": 1, "title": "Test", "tvdbId": 12345},
            "episodes": [{"id": 1, "seasonNumber": 1, "episodeNumber": 1}],
            "episodeFile": {"id": 1, "path": "/tv/test.mkv"},
        }

        response = test_client.post(
            "/webhook/sonarr",
            json=payload,
            headers={"X-Webhook-Signature": "invalid_signature"},
        )

        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    def test_sonarr_webhook_missing_signature(self, test_client):
        """Test Sonarr webhook with missing signature."""
        payload = {
            "eventType": "Download",
            "series": {"id": 1, "title": "Test", "tvdbId": 12345},
            "episodes": [{"id": 1, "seasonNumber": 1, "episodeNumber": 1}],
            "episodeFile": {"id": 1, "path": "/tv/test.mkv"},
        }

        response = test_client.post("/webhook/sonarr", json=payload)

        assert response.status_code == 401
        assert "Missing signature" in response.json()["detail"]

    def test_sonarr_webhook_file_not_found(self, test_client):
        """Test Sonarr webhook when file doesn't exist."""
        payload = {
            "eventType": "Download",
            "series": {"id": 1, "title": "Test", "tvdbId": 12345},
            "episodes": [{"id": 1, "seasonNumber": 1, "episodeNumber": 1}],
            "episodeFile": {"id": 1, "path": "/tv/nonexistent/S01E01.mkv"},
        }

        signature = create_signature(payload, "test_secret_key")

        response = test_client.post(
            "/webhook/sonarr",
            json=payload,
            headers={"X-Webhook-Signature": signature},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert "not found" in data["message"].lower()

    def test_sonarr_webhook_missing_file_path(self, test_client):
        """Test Sonarr webhook with missing file path."""
        payload = {
            "eventType": "Download",
            "series": {"id": 1, "title": "Test", "tvdbId": 12345},
            "episodes": [{"id": 1, "seasonNumber": 1, "episodeNumber": 1}],
            # No episodeFile
        }

        signature = create_signature(payload, "test_secret_key")

        response = test_client.post(
            "/webhook/sonarr",
            json=payload,
            headers={"X-Webhook-Signature": signature},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert "Missing" in data["message"]


class TestRadarrWebhook:
    """Tests for Radarr webhook endpoint."""

    def test_radarr_webhook_success(self, test_client, webhook_config):
        """Test successful Radarr webhook processing."""
        payload = {
            "eventType": "Download",
            "movie": {
                "id": 1,
                "title": "Test Movie",
                "year": 2023,
                "tmdbId": 12345,
                "imdbId": "tt1234567",
            },
            "movieFile": {
                "id": 1,
                "relativePath": "/movies/test_show/S01E01.mkv",  # Using existing test file path
            },
        }

        signature = create_signature(payload, "test_secret_key")

        with patch("arrtheaudio.api.routes.ProcessingPipeline") as mock_pipeline:
            # Mock the pipeline to avoid actual processing
            mock_result = Mock()
            mock_result.status = "success"
            mock_pipeline.return_value.process.return_value = mock_result

            response = test_client.post(
                "/webhook/radarr",
                json=payload,
                headers={"X-Webhook-Signature": signature},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "job_id" in data

    def test_radarr_webhook_invalid_signature(self, test_client):
        """Test Radarr webhook with invalid signature."""
        payload = {
            "eventType": "Download",
            "movie": {"id": 1, "title": "Test", "year": 2023, "tmdbId": 12345},
            "movieFile": {"id": 1, "relativePath": "/movies/test.mkv"},
        }

        response = test_client.post(
            "/webhook/radarr",
            json=payload,
            headers={"X-Webhook-Signature": "invalid_signature"},
        )

        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    def test_radarr_webhook_file_not_found(self, test_client):
        """Test Radarr webhook when file doesn't exist."""
        payload = {
            "eventType": "Download",
            "movie": {"id": 1, "title": "Test", "year": 2023, "tmdbId": 12345},
            "movieFile": {"id": 1, "relativePath": "/movies/nonexistent.mkv"},
        }

        signature = create_signature(payload, "test_secret_key")

        response = test_client.post(
            "/webhook/radarr",
            json=payload,
            headers={"X-Webhook-Signature": signature},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert "not found" in data["message"].lower()


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data


class TestPathMapping:
    """Tests for path mapping in webhooks."""

    def test_path_mapping_applied(self, test_client, webhook_config):
        """Test that path mapping is correctly applied."""
        # Create a file at the mapped location
        media_dir = Path(webhook_config.path_mappings[0].local)
        test_file = media_dir / "mapped_show" / "S01E01.mkv"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.touch()

        payload = {
            "eventType": "Download",
            "series": {"id": 1, "title": "Test", "tvdbId": 12345},
            "episodes": [{"id": 1, "seasonNumber": 1, "episodeNumber": 1}],
            "episodeFile": {"id": 1, "path": "/tv/mapped_show/S01E01.mkv"},
        }

        signature = create_signature(payload, "test_secret_key")

        with patch("arrtheaudio.api.routes.ProcessingPipeline") as mock_pipeline:
            mock_result = Mock()
            mock_result.status = "success"
            mock_pipeline.return_value.process.return_value = mock_result

            response = test_client.post(
                "/webhook/sonarr",
                json=payload,
                headers={"X-Webhook-Signature": signature},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"

        # Verify that the pipeline was called with the mapped path
        mock_pipeline.assert_called_once()
        called_path = mock_pipeline.return_value.process.call_args[0][0]
        assert str(called_path).startswith(str(media_dir))


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_endpoint(self, test_client):
        """Test root endpoint returns API information."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "ArrTheAudio"
        assert "version" in data

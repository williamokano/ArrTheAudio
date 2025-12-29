"""Integration tests for multi-file webhook fix (Phase 5 critical bug fix)."""

import hmac
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from arrtheaudio.api.app import create_app
from arrtheaudio.config import Config, PathMapping, APIConfig
from arrtheaudio.core.queue_manager import JobQueueManager
from arrtheaudio.core.worker_pool import WorkerPool
from arrtheaudio.core.pipeline import ProcessingPipeline
from arrtheaudio.core.detector import ContainerType


def create_signature(payload: dict, secret: str) -> str:
    """Create HMAC signature for webhook payload."""
    body = json.dumps(payload).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def webhook_config(tmp_path):
    """Create configuration for webhook testing."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()

    # Create test files for multi-file testing
    show_dir = media_dir / "test_show"
    show_dir.mkdir()
    for i in range(1, 4):  # 3 episodes
        (show_dir / f"S01E0{i}.mkv").touch()

    return Config(
        language_priority=["eng", "jpn"],
        path_mappings=[
            PathMapping(remote="/tv", local=str(media_dir)),
        ],
        api=APIConfig(
            host="0.0.0.0",
            port=9393,
            webhook_secret="test_secret_key",
        ),
    )


@pytest.fixture
def test_client(webhook_config, tmp_path):
    """Create test client with job queue."""
    from arrtheaudio import api

    app = create_app(webhook_config)

    # Initialize queue manager
    db_path = tmp_path / "test_jobs.db"
    queue_manager = JobQueueManager(webhook_config, db_path)

    # Initialize worker pool
    pipeline = ProcessingPipeline(webhook_config)
    worker_pool = WorkerPool(webhook_config, queue_manager, pipeline)

    # Set app state
    app.state.arrtheaudio.queue_manager = queue_manager
    app.state.arrtheaudio.worker_pool = worker_pool

    # Set global state for dependency injection (needed for job_routes.py dependencies)
    api.app._app_state = {
        "queue_manager": queue_manager,
        "worker_pool": worker_pool,
        "config": webhook_config,
    }

    return TestClient(app)


class TestMultiFileWebhookFix:
    """Test the critical multi-file webhook bug fix."""

    def test_sonarr_single_file(self, test_client):
        """Test Sonarr webhook with single file (baseline)."""
        payload = {
            "eventType": "Download",
            "series": {
                "id": 1,
                "title": "Test Show",
                "tvdbId": 12345,
            },
            "episodes": [{"id": 1, "seasonNumber": 1, "episodeNumber": 1}],
            "episodeFiles": [
                {"id": 1, "path": "/tv/test_show/S01E01.mkv"},
            ],
        }

        signature = create_signature(payload, "test_secret_key")

        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            response = test_client.post(
                "/webhook/sonarr",
                json=payload,
                headers={"X-Webhook-Signature": signature},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "webhook_id" in data
        assert len(data["job_ids"]) == 1
        assert data["files_queued"] == 1

    def test_sonarr_multiple_files_all_processed(self, test_client):
        """Test Sonarr webhook with multiple files - ALL should be processed."""
        payload = {
            "eventType": "Download",
            "series": {
                "id": 1,
                "title": "Test Show",
                "tvdbId": 12345,
            },
            "episodes": [
                {"id": 1, "seasonNumber": 1, "episodeNumber": 1},
                {"id": 2, "seasonNumber": 1, "episodeNumber": 2},
                {"id": 3, "seasonNumber": 1, "episodeNumber": 3},
            ],
            "episodeFiles": [
                {"id": 1, "path": "/tv/test_show/S01E01.mkv"},
                {"id": 2, "path": "/tv/test_show/S01E02.mkv"},
                {"id": 3, "path": "/tv/test_show/S01E03.mkv"},
            ],
        }

        signature = create_signature(payload, "test_secret_key")

        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            response = test_client.post(
                "/webhook/sonarr",
                json=payload,
                headers={"X-Webhook-Signature": signature},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "webhook_id" in data

        # CRITICAL: All 3 files should be processed, not just the first!
        assert len(data["job_ids"]) == 3, "All files must be processed, not just the first one!"
        assert data["files_queued"] == 3

        # Verify all jobs were created
        webhook_id = data["webhook_id"]
        webhook_response = test_client.get(f"/api/v1/webhook/{webhook_id}")
        assert webhook_response.status_code == 200
        webhook_data = webhook_response.json()
        assert webhook_data["total_jobs"] == 3
        assert len(webhook_data["jobs"]) == 3

        # Verify all jobs have the same webhook_id
        job_ids = set(job["job_id"] for job in webhook_data["jobs"])
        assert len(job_ids) == 3  # All jobs unique
        assert all(job["webhook_id"] == webhook_id for job in webhook_data["jobs"])

    def test_sonarr_season_pack_scenario(self, test_client):
        """Test Sonarr webhook for season pack (10 episodes) - real-world scenario."""
        # Simulate a season pack download with 10 episodes
        episode_files = [
            {"id": i, "path": f"/tv/test_show/S01E{i:02d}.mkv"}
            for i in range(1, 11)
        ]
        episodes = [
            {"id": i, "seasonNumber": 1, "episodeNumber": i}
            for i in range(1, 11)
        ]

        payload = {
            "eventType": "Download",
            "series": {
                "id": 1,
                "title": "Test Show",
                "tvdbId": 12345,
            },
            "episodes": episodes,
            "episodeFiles": episode_files,
        }

        # Create all files
        media_dir = Path(test_client.app.state.arrtheaudio.config.path_mappings[0].local)
        show_dir = media_dir / "test_show"
        show_dir.mkdir(exist_ok=True)
        for i in range(1, 11):
            (show_dir / f"S01E{i:02d}.mkv").touch()

        signature = create_signature(payload, "test_secret_key")

        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            response = test_client.post(
                "/webhook/sonarr",
                json=payload,
                headers={"X-Webhook-Signature": signature},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"

        # ALL 10 episodes must be queued
        assert len(data["job_ids"]) == 10, "Season pack: all episodes must be processed!"
        assert data["files_queued"] == 10

    def test_sonarr_partial_files_exist(self, test_client):
        """Test when only some files exist (should process what's available)."""
        payload = {
            "eventType": "Download",
            "series": {
                "id": 1,
                "title": "Test Show",
                "tvdbId": 12345,
            },
            "episodes": [
                {"id": 1, "seasonNumber": 1, "episodeNumber": 1},
                {"id": 2, "seasonNumber": 1, "episodeNumber": 2},
            ],
            "episodeFiles": [
                {"id": 1, "path": "/tv/test_show/S01E01.mkv"},  # Exists
                {"id": 2, "path": "/tv/test_show/S01E99.mkv"},  # Doesn't exist
            ],
        }

        signature = create_signature(payload, "test_secret_key")

        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            response = test_client.post(
                "/webhook/sonarr",
                json=payload,
                headers={"X-Webhook-Signature": signature},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"

        # Only 1 file should be processed (the one that exists)
        assert len(data["job_ids"]) == 1
        assert data["files_queued"] == 1

    def test_sonarr_multi_file_jobs_linked_by_webhook_id(self, test_client):
        """Test that multi-file jobs are properly linked by webhook_id."""
        payload = {
            "eventType": "Download",
            "series": {
                "id": 1,
                "title": "Test Show",
                "tvdbId": 12345,
            },
            "episodes": [
                {"id": 1, "seasonNumber": 1, "episodeNumber": 1},
                {"id": 2, "seasonNumber": 1, "episodeNumber": 2},
            ],
            "episodeFiles": [
                {"id": 1, "path": "/tv/test_show/S01E01.mkv"},
                {"id": 2, "path": "/tv/test_show/S01E02.mkv"},
            ],
        }

        signature = create_signature(payload, "test_secret_key")

        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            response = test_client.post(
                "/webhook/sonarr",
                json=payload,
                headers={"X-Webhook-Signature": signature},
            )

        assert response.status_code == 200
        data = response.json()
        webhook_id = data["webhook_id"]
        job_ids = data["job_ids"]

        # Verify all jobs have the same webhook_id
        for job_id in job_ids:
            job_response = test_client.get(f"/api/v1/jobs/{job_id}")
            job_data = job_response.json()
            assert job_data["webhook_id"] == webhook_id
            assert job_data["source"] == "sonarr"
            assert job_data["priority"] == "high"  # Webhooks are high priority

    def test_sonarr_multi_file_different_tmdb_metadata(self, test_client):
        """Test that TMDB metadata is preserved for multi-file webhooks."""
        payload = {
            "eventType": "Download",
            "series": {
                "id": 1,
                "title": "Anime Show",
                "tvdbId": 12345,
                "tmdbId": 67890,
                "originalLanguage": {
                    "id": 1,
                    "name": "Japanese",
                },
            },
            "episodes": [
                {"id": 1, "seasonNumber": 1, "episodeNumber": 1},
                {"id": 2, "seasonNumber": 1, "episodeNumber": 2},
            ],
            "episodeFiles": [
                {"id": 1, "path": "/tv/test_show/S01E01.mkv"},
                {"id": 2, "path": "/tv/test_show/S01E02.mkv"},
            ],
        }

        signature = create_signature(payload, "test_secret_key")

        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            response = test_client.post(
                "/webhook/sonarr",
                json=payload,
                headers={"X-Webhook-Signature": signature},
            )

        assert response.status_code == 200
        data = response.json()

        # Verify metadata is set on all jobs
        queue_manager = test_client.app.state.arrtheaudio.queue_manager
        import asyncio
        jobs = asyncio.run(queue_manager.get_jobs_by_webhook(data["webhook_id"]))

        for job in jobs:
            assert job.tmdb_id == 67890
            assert job.original_language == "Japanese"
            assert job.series_title == "Anime Show"


class TestMultiFileWebhookRegressionPrevention:
    """Regression tests to ensure the bug doesn't come back."""

    def test_episodeFiles_array_not_truncated(self, test_client):
        """Ensure episodeFiles array is not truncated to first element."""
        payload = {
            "eventType": "Download",
            "series": {"id": 1, "title": "Test", "tvdbId": 12345},
            "episodes": [
                {"id": 1, "seasonNumber": 1, "episodeNumber": 1},
                {"id": 2, "seasonNumber": 1, "episodeNumber": 2},
            ],
            "episodeFiles": [
                {"id": 1, "path": "/tv/test_show/S01E01.mkv"},
                {"id": 2, "path": "/tv/test_show/S01E02.mkv"},
            ],
        }

        signature = create_signature(payload, "test_secret_key")

        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            response = test_client.post(
                "/webhook/sonarr",
                json=payload,
                headers={"X-Webhook-Signature": signature},
            )

        data = response.json()

        # The bug was: only job_ids[0] would exist
        # Fix: all job_ids should exist
        assert len(data["job_ids"]) == 2, "Regression: Only first file processed!"

        # Verify both files are in different jobs
        file_paths = []
        for job_id in data["job_ids"]:
            job_response = test_client.get(f"/api/v1/jobs/{job_id}")
            file_paths.append(job_response.json()["file_path"])

        assert len(set(file_paths)) == 2, "Jobs should have different file paths!"

    def test_no_silent_data_loss(self, test_client):
        """Ensure no files are silently dropped without warning."""
        payload = {
            "eventType": "Download",
            "series": {"id": 1, "title": "Test", "tvdbId": 12345},
            "episodes": [
                {"id": i, "seasonNumber": 1, "episodeNumber": i}
                for i in range(1, 6)
            ],
            "episodeFiles": [
                {"id": i, "path": f"/tv/test_show/S01E{i:02d}.mkv"}
                for i in range(1, 6)
            ],
        }

        # Create files
        media_dir = Path(test_client.app.state.arrtheaudio.config.path_mappings[0].local)
        show_dir = media_dir / "test_show"
        show_dir.mkdir(exist_ok=True)
        for i in range(1, 6):
            (show_dir / f"S01E{i:02d}.mkv").touch()

        signature = create_signature(payload, "test_secret_key")

        with patch("arrtheaudio.core.detector.ContainerDetector.detect", return_value=ContainerType.MKV):
            response = test_client.post(
                "/webhook/sonarr",
                json=payload,
                headers={"X-Webhook-Signature": signature},
            )

        data = response.json()

        # ALL files must be accounted for
        assert data["files_queued"] == 5, "Silent data loss detected!"
        assert len(data["job_ids"]) == 5, "Not all files were queued!"

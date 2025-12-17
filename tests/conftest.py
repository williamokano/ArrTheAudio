"""Shared pytest fixtures for ArrTheAudio tests."""

from pathlib import Path

import pytest

from arrtheaudio.config import Config, PathOverride
from arrtheaudio.models.metadata import MediaMetadata
from arrtheaudio.models.track import AudioTrack


@pytest.fixture
def default_config():
    """Create a default configuration for testing."""
    return Config(
        language_priority=["eng", "jpn", "ita"],
        path_overrides=[
            PathOverride(path="/media/anime/**", language_priority=["jpn", "eng"]),
            PathOverride(path="/media/korean/**", language_priority=["kor", "eng"]),
        ],
    )


@pytest.fixture
def sample_audio_tracks():
    """Create sample audio tracks for testing."""
    return [
        AudioTrack(
            index=0,
            stream_index=1,
            codec="aac",
            language="eng",
            title="English",
            is_default=True,
            channels=2,
        ),
        AudioTrack(
            index=1,
            stream_index=2,
            codec="ac3",
            language="jpn",
            title="Japanese",
            is_default=False,
            channels=6,
        ),
        AudioTrack(
            index=2,
            stream_index=3,
            codec="aac",
            language="ita",
            title="Italian",
            is_default=False,
            channels=2,
        ),
    ]


@pytest.fixture
def sample_metadata_jpn():
    """Create sample metadata with Japanese as original language."""
    return MediaMetadata(
        original_language="jpn",
        source="tmdb",
        title="Attack on Titan",
        year=2013,
        tmdb_id=1429,
    )


@pytest.fixture
def sample_metadata_eng():
    """Create sample metadata with English as original language."""
    return MediaMetadata(
        original_language="eng",
        source="tmdb",
        title="The Office",
        year=2005,
        tmdb_id=2316,
    )


@pytest.fixture
def sample_metadata_none():
    """Create sample metadata with no original language."""
    return MediaMetadata(original_language=None, source="none")

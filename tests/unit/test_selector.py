"""Unit tests for track selector and priority resolver."""

from pathlib import Path

import pytest

from arrtheaudio.core.selector import PriorityResolver, TrackSelector
from arrtheaudio.models.track import AudioTrack


class TestPriorityResolver:
    """Test path-based priority resolution."""

    def test_global_priority_when_no_override_matches(self, default_config):
        """Should use global priority when no path override matches."""
        resolver = PriorityResolver(default_config)
        file_path = Path("/media/movies/The Office/S01E01.mkv")

        priority = resolver.resolve_priority(file_path)

        assert priority == ["eng", "jpn", "ita"]

    def test_path_override_for_anime(self, default_config):
        """Should use anime-specific priority for anime paths."""
        resolver = PriorityResolver(default_config)
        file_path = Path("/media/anime/Attack on Titan/S01E01.mkv")

        priority = resolver.resolve_priority(file_path)

        assert priority == ["jpn", "eng"]

    def test_path_override_for_korean(self, default_config):
        """Should use Korean-specific priority for Korean paths."""
        resolver = PriorityResolver(default_config)
        file_path = Path("/media/korean/Squid Game/S01E01.mkv")

        priority = resolver.resolve_priority(file_path)

        assert priority == ["kor", "eng"]

    def test_first_matching_override_wins(self, default_config):
        """Should use first matching override pattern."""
        resolver = PriorityResolver(default_config)

        # This matches the anime pattern (first in list)
        file_path = Path("/media/anime/Show/S01E01.mkv")
        priority = resolver.resolve_priority(file_path)

        assert priority == ["jpn", "eng"]


class TestTrackSelector:
    """Test track selection logic."""

    def test_select_original_language_when_available(
        self, default_config, sample_audio_tracks, sample_metadata_jpn
    ):
        """Should prefer original language when known and available."""
        selector = TrackSelector(default_config)
        file_path = Path("/media/movies/AOT.mkv")

        selected = selector.select(sample_audio_tracks, file_path, sample_metadata_jpn)

        assert selected is not None
        assert selected.language == "jpn"
        assert selected.index == 1

    def test_fallback_to_priority_when_original_not_available(
        self, default_config, sample_metadata_eng
    ):
        """Should use priority list when original language not in tracks."""
        # Tracks without English
        tracks = [
            AudioTrack(0, 1, "aac", "jpn", is_default=True),
            AudioTrack(1, 2, "ac3", "ita", is_default=False),
        ]

        selector = TrackSelector(default_config)
        file_path = Path("/media/movies/Movie.mkv")

        # Original is "eng" but not available, should pick first from priority
        selected = selector.select(tracks, file_path, sample_metadata_eng)

        # Should pick "jpn" (first available from priority list)
        assert selected is not None
        assert selected.language == "jpn"

    def test_use_priority_when_no_metadata(
        self, default_config, sample_audio_tracks, sample_metadata_none
    ):
        """Should use priority list when no metadata available."""
        selector = TrackSelector(default_config)
        file_path = Path("/media/movies/Movie.mkv")

        selected = selector.select(sample_audio_tracks, file_path, sample_metadata_none)

        # Should pick "eng" (first in global priority)
        assert selected is not None
        assert selected.language == "eng"
        assert selected.index == 0

    def test_use_path_specific_priority(self, default_config, sample_audio_tracks):
        """Should use path-specific priority for anime files."""
        selector = TrackSelector(default_config)
        file_path = Path("/media/anime/Show/S01E01.mkv")

        selected = selector.select(sample_audio_tracks, file_path, None)

        # Should pick "jpn" (first in anime priority)
        assert selected is not None
        assert selected.language == "jpn"
        assert selected.index == 1

    def test_return_none_when_no_tracks(self, default_config):
        """Should return None when no tracks available."""
        selector = TrackSelector(default_config)
        file_path = Path("/media/movies/Movie.mkv")

        selected = selector.select([], file_path, None)

        assert selected is None

    def test_return_none_when_no_matching_language(self, default_config):
        """Should return None when no matching language found."""
        # Tracks with only languages not in priority
        tracks = [
            AudioTrack(0, 1, "aac", "fre", is_default=True),
            AudioTrack(1, 2, "ac3", "ger", is_default=False),
        ]

        selector = TrackSelector(default_config)
        file_path = Path("/media/movies/Movie.mkv")

        selected = selector.select(tracks, file_path, None)

        assert selected is None

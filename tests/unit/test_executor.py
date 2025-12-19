"""Unit tests for audio track executors."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from arrtheaudio.core.executor import MP4Executor, MKVExecutor, get_executor


class TestMP4Executor:
    """Test MP4Executor class."""

    @pytest.fixture
    def mock_file(self, tmp_path):
        """Create a mock MP4 file."""
        file_path = tmp_path / "test.mp4"
        # Create a file with some content (10 MB)
        file_path.write_bytes(b"0" * (10 * 1024 * 1024))
        return file_path

    @pytest.fixture
    def executor(self):
        """Create MP4Executor instance."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            return MP4Executor(timeout_seconds=60)

    def test_init_requires_ffmpeg(self):
        """Test that MP4Executor requires ffmpeg to be available."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="ffmpeg not found"):
                MP4Executor()

    def test_get_audio_track_count_success(self, executor, mock_file):
        """Test getting audio track count."""
        mock_output = {
            "streams": [
                {"codec_type": "audio", "index": 0},
                {"codec_type": "audio", "index": 1},
            ]
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"streams": [{"codec_type": "audio"}, {"codec_type": "audio"}]}',
            )
            count = executor._get_audio_track_count(mock_file)
            assert count == 2

    def test_get_audio_track_count_failure(self, executor, mock_file):
        """Test getting audio track count when ffprobe fails."""
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffprobe")):
            count = executor._get_audio_track_count(mock_file)
            assert count == 0

    def test_check_disk_space_sufficient(self, executor, mock_file):
        """Test disk space check with sufficient space."""
        # Mock disk_usage to return plenty of space
        mock_stat = Mock()
        mock_stat.free = 100 * 1024 * 1024 * 1024  # 100 GB free

        with patch("shutil.disk_usage", return_value=mock_stat):
            assert executor._check_disk_space(mock_file) is True

    def test_check_disk_space_insufficient(self, executor, mock_file):
        """Test disk space check with insufficient space."""
        # Mock disk_usage to return insufficient space
        mock_stat = Mock()
        mock_stat.free = 5 * 1024 * 1024  # Only 5 MB free (need 20 MB for 10 MB file)

        with patch("shutil.disk_usage", return_value=mock_stat):
            assert executor._check_disk_space(mock_file) is False

    def test_build_ffmpeg_command(self, executor, tmp_path):
        """Test ffmpeg command building."""
        input_file = tmp_path / "input.mp4"
        output_file = tmp_path / "output.mp4"

        cmd = executor._build_ffmpeg_command(input_file, output_file, 1, 3)

        assert cmd[0] == "/usr/bin/ffmpeg"
        assert "-i" in cmd
        assert str(input_file) in cmd
        assert "-map" in cmd
        assert "0" in cmd
        assert "-c" in cmd
        assert "copy" in cmd
        # Check dispositions for 3 tracks
        assert "-disposition:a:0" in cmd
        assert "0" in cmd  # Track 0 not default
        assert "-disposition:a:1" in cmd
        assert "default" in cmd  # Track 1 is default
        assert "-disposition:a:2" in cmd
        assert "-movflags" in cmd
        assert "+faststart" in cmd
        assert str(output_file) in cmd

    def test_set_default_audio_success(self, executor, mock_file):
        """Test successful MP4 processing."""
        temp_file = mock_file.parent / f".{mock_file.name}.tmp"
        backup_file = mock_file.parent / f"{mock_file.name}.bak"

        # Mock ffprobe for track count
        mock_ffprobe = Mock(
            returncode=0,
            stdout='{"streams": [{"codec_type": "audio"}, {"codec_type": "audio"}]}',
        )

        # Mock ffmpeg success
        mock_ffmpeg = Mock(returncode=0, stderr="")

        # Mock disk space check
        mock_stat = Mock()
        mock_stat.free = 100 * 1024 * 1024 * 1024

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_ffprobe, mock_ffmpeg]

            with patch("shutil.disk_usage", return_value=mock_stat):
                with patch("shutil.copy2"):
                    # Create temp file to simulate ffmpeg output
                    temp_file.write_bytes(b"0" * (9 * 1024 * 1024))  # 9 MB (90% of original)

                    result = executor.set_default_audio(mock_file, 1)

                    assert result is True
                    assert not temp_file.exists()  # Cleaned up
                    assert not backup_file.exists()  # Cleaned up

    def test_set_default_audio_file_not_found(self, executor, tmp_path):
        """Test processing non-existent file."""
        non_existent = tmp_path / "nonexistent.mp4"
        result = executor.set_default_audio(non_existent, 0)
        assert result is False

    def test_set_default_audio_insufficient_disk_space(self, executor, mock_file):
        """Test processing fails with insufficient disk space."""
        mock_stat = Mock()
        mock_stat.free = 1 * 1024 * 1024  # Only 1 MB free

        with patch("shutil.disk_usage", return_value=mock_stat):
            result = executor.set_default_audio(mock_file, 0)
            assert result is False

    def test_set_default_audio_no_audio_tracks(self, executor, mock_file):
        """Test processing file with no audio tracks."""
        # Mock ffprobe returning no audio streams
        mock_ffprobe = Mock(returncode=0, stdout='{"streams": []}')

        mock_stat = Mock()
        mock_stat.free = 100 * 1024 * 1024 * 1024

        with patch("subprocess.run", return_value=mock_ffprobe):
            with patch("shutil.disk_usage", return_value=mock_stat):
                result = executor.set_default_audio(mock_file, 0)
                assert result is False

    def test_set_default_audio_track_index_out_of_range(self, executor, mock_file):
        """Test processing with invalid track index."""
        # Mock ffprobe returning 2 audio streams
        mock_ffprobe = Mock(
            returncode=0,
            stdout='{"streams": [{"codec_type": "audio"}, {"codec_type": "audio"}]}',
        )

        mock_stat = Mock()
        mock_stat.free = 100 * 1024 * 1024 * 1024

        with patch("subprocess.run", return_value=mock_ffprobe):
            with patch("shutil.disk_usage", return_value=mock_stat):
                result = executor.set_default_audio(mock_file, 5)  # Only 2 tracks
                assert result is False

    def test_set_default_audio_ffmpeg_failure(self, executor, mock_file):
        """Test processing when ffmpeg fails."""
        temp_file = mock_file.parent / f".{mock_file.name}.tmp"

        # Mock ffprobe success
        mock_ffprobe = Mock(
            returncode=0,
            stdout='{"streams": [{"codec_type": "audio"}, {"codec_type": "audio"}]}',
        )

        # Mock ffmpeg failure
        mock_ffmpeg = Mock(returncode=1, stderr="ffmpeg error")

        mock_stat = Mock()
        mock_stat.free = 100 * 1024 * 1024 * 1024

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_ffprobe, mock_ffmpeg]

            with patch("shutil.disk_usage", return_value=mock_stat):
                result = executor.set_default_audio(mock_file, 0)

                assert result is False
                assert not temp_file.exists()  # Cleaned up

    def test_set_default_audio_output_too_small(self, executor, mock_file):
        """Test processing fails when output is suspiciously small."""
        temp_file = mock_file.parent / f".{mock_file.name}.tmp"

        # Mock ffprobe success
        mock_ffprobe = Mock(
            returncode=0,
            stdout='{"streams": [{"codec_type": "audio"}, {"codec_type": "audio"}]}',
        )

        # Mock ffmpeg success
        mock_ffmpeg = Mock(returncode=0, stderr="")

        mock_stat = Mock()
        mock_stat.free = 100 * 1024 * 1024 * 1024

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_ffprobe, mock_ffmpeg]

            with patch("shutil.disk_usage", return_value=mock_stat):
                # Create temp file that's too small (< 90% of original)
                temp_file.write_bytes(b"0" * (5 * 1024 * 1024))  # 5 MB (50% of original)

                result = executor.set_default_audio(mock_file, 0)

                assert result is False
                assert not temp_file.exists()  # Cleaned up

    def test_set_default_audio_timeout(self, executor, mock_file):
        """Test processing timeout."""
        # Mock ffprobe success
        mock_ffprobe = Mock(
            returncode=0,
            stdout='{"streams": [{"codec_type": "audio"}, {"codec_type": "audio"}]}',
        )

        mock_stat = Mock()
        mock_stat.free = 100 * 1024 * 1024 * 1024

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                mock_ffprobe,
                subprocess.TimeoutExpired("ffmpeg", 60),
            ]

            with patch("shutil.disk_usage", return_value=mock_stat):
                result = executor.set_default_audio(mock_file, 0)
                assert result is False

    def test_set_default_audio_rollback_on_exception(self, executor, mock_file):
        """Test rollback when exception occurs after backup."""
        temp_file = mock_file.parent / f".{mock_file.name}.tmp"
        backup_file = mock_file.parent / f"{mock_file.name}.bak"

        # Mock ffprobe success
        mock_ffprobe = Mock(
            returncode=0,
            stdout='{"streams": [{"codec_type": "audio"}, {"codec_type": "audio"}]}',
        )

        # Mock ffmpeg success
        mock_ffmpeg = Mock(returncode=0, stderr="")

        mock_stat = Mock()
        mock_stat.free = 100 * 1024 * 1024 * 1024

        original_content = mock_file.read_bytes()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_ffprobe, mock_ffmpeg]

            with patch("shutil.disk_usage", return_value=mock_stat):
                with patch("shutil.copy2") as mock_copy:
                    # First copy2 creates backup, second would restore
                    mock_copy.side_effect = [None, None]

                    # Create temp file
                    temp_file.write_bytes(b"0" * (9 * 1024 * 1024))

                    # Create backup
                    backup_file.write_bytes(original_content)

                    # Mock replace to raise exception
                    with patch.object(Path, "replace", side_effect=Exception("Test error")):
                        result = executor.set_default_audio(mock_file, 0)

                        assert result is False
                        # Verify cleanup was attempted (files don't exist means cleanup worked)
                        assert not temp_file.exists()

    def test_cleanup_files(self, executor, tmp_path):
        """Test cleanup of temporary files."""
        temp1 = tmp_path / "temp1.tmp"
        temp2 = tmp_path / "temp2.bak"

        temp1.write_text("test")
        temp2.write_text("test")

        executor._cleanup_files([temp1, temp2])

        assert not temp1.exists()
        assert not temp2.exists()

    def test_cleanup_files_handles_missing_files(self, executor, tmp_path):
        """Test cleanup doesn't fail on missing files."""
        non_existent = tmp_path / "nonexistent.tmp"

        # Should not raise exception
        executor._cleanup_files([non_existent])


class TestMKVExecutor:
    """Test MKVExecutor class."""

    @pytest.fixture
    def executor(self):
        """Create MKVExecutor instance."""
        return MKVExecutor()

    def test_get_audio_track_count(self, executor, tmp_path):
        """Test getting audio track count for MKV."""
        mock_file = tmp_path / "test.mkv"
        mock_file.write_text("test")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"streams": [{"codec_type": "audio"}, {"codec_type": "audio"}]}',
            )

            count = executor._get_audio_track_count(mock_file)
            assert count == 2


class TestGetExecutor:
    """Test get_executor factory function."""

    def test_get_mkv_executor(self):
        """Test getting MKV executor."""
        executor = get_executor("mkv")
        assert isinstance(executor, MKVExecutor)

    def test_get_mp4_executor(self):
        """Test getting MP4 executor."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            executor = get_executor("mp4", timeout_seconds=120)
            assert isinstance(executor, MP4Executor)
            assert executor.timeout_seconds == 120

    def test_get_executor_case_insensitive(self):
        """Test executor selection is case insensitive."""
        executor1 = get_executor("MKV")
        executor2 = get_executor("Mkv")

        assert isinstance(executor1, MKVExecutor)
        assert isinstance(executor2, MKVExecutor)

    def test_get_executor_unsupported(self):
        """Test getting executor for unsupported format."""
        with pytest.raises(ValueError, match="Unsupported container type"):
            get_executor("avi")

"""Tests for video converter functionality."""
import os
import subprocess
import tempfile
from unittest.mock import patch

import pytest

from utils.video_converter import VideoConverter
from watch_tower.exceptions import VideoConversionError


@pytest.fixture(name='mock_ffmpeg_path')
def _mock_ffmpeg_path():
    """Mock ffmpeg path for testing."""
    return "/usr/bin/ffmpeg"


@pytest.fixture(name='video_converter')
def _video_converter(mock_ffmpeg_path):
    """Create a VideoConverter instance with mocked ffmpeg."""
    with patch.object(VideoConverter, '_find_ffmpeg', return_value=mock_ffmpeg_path):
        return VideoConverter()


@pytest.fixture
def sample_video_info():
    """Sample video information returned by ffprobe."""
    return {
        "format": {
            "duration": "10.5",
            "size": "1048576",
            "bit_rate": "800000"
        },
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "30/1",
                "pix_fmt": "yuv420p"
            },
            {
                "codec_type": "audio",
                "codec_name": "aac"
            }
        ]
    }


def test_find_ffmpeg_success():
    """Test successful ffmpeg detection."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.stdout = "/usr/bin/ffmpeg\n"
        mock_run.return_value.returncode = 0

        converter = VideoConverter()
        assert converter.ffmpeg_path == "/usr/bin/ffmpeg"


def test_find_ffmpeg_failure():
    """Test ffmpeg detection failure."""
    with patch('subprocess.run') as mock_run, patch('os.path.exists') as mock_exists:
        mock_run.side_effect = FileNotFoundError()
        mock_exists.return_value = False

        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            VideoConverter()


def test_get_video_info_success(video_converter):
    """Test successful video info retrieval."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.stdout = '{"format": {"duration": "10.5"}}'
        mock_run.return_value.returncode = 0

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            info = video_converter.get_video_info(temp_file.name)
            assert 'format' in info


def test_get_video_info_file_not_found(video_converter):
    """Test video info retrieval with non-existent file."""
    with pytest.raises(FileNotFoundError):
        video_converter.get_video_info("/nonexistent/file.mp4")


def test_get_video_info_ffprobe_failure(video_converter):
    """Test video info retrieval when ffprobe fails."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "ffprobe", stderr="Error")

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            with pytest.raises(RuntimeError, match="Failed to get video info"):
                video_converter.get_video_info(temp_file.name)


def create_output_file(*args, **_kwargs):
    """Helper function to create output file for mocking subprocess.run."""
    output_path = args[0][-1]
    with open(output_path, 'w', encoding='utf-8') as output_file:
        output_file.write('dummy video data')
    return subprocess.CompletedProcess(args[0], 0)


def test_convert_to_h264_success(video_converter):
    """Test successful video conversion."""
    with patch.object(video_converter, 'get_video_info') as mock_info:
        mock_info.return_value = {'codec': 'h264', 'width': 1920, 'height': 1080}

        with patch('subprocess.run', side_effect=create_output_file):
            with tempfile.NamedTemporaryFile(suffix='.mp4') as input_file:
                with tempfile.NamedTemporaryFile(suffix='.mp4') as output_file:
                    result, is_temp = video_converter.convert_to_h264(
                        input_file.name, output_file.name, overwrite=True)
                    assert result == output_file.name
                    assert not is_temp


def test_convert_to_h264_file_not_found(video_converter):
    """Test video conversion with non-existent input file."""
    with pytest.raises(FileNotFoundError):
        video_converter.convert_to_h264("/nonexistent/file.mp4")


def test_convert_to_h264_ffmpeg_failure(video_converter):
    """Test video conversion when ffmpeg fails."""
    with patch.object(video_converter, 'get_video_info') as mock_info:
        mock_info.return_value = {'codec': 'h264', 'width': 1920, 'height': 1080}

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "ffmpeg", stderr="Error")

            with tempfile.NamedTemporaryFile(suffix='.mp4') as input_file:
                with pytest.raises(VideoConversionError, match="Video conversion failed"):
                    video_converter.convert_to_h264(input_file.name)


def test_convert_to_h264_with_scaling(video_converter):
    """Test video conversion with scaling parameters."""
    with patch.object(video_converter, 'get_video_info') as mock_info:
        mock_info.return_value = {'codec': 'h264', 'width': 1920, 'height': 1080}

        with patch('subprocess.run', side_effect=create_output_file) as mock_run:
            with tempfile.NamedTemporaryFile(suffix='.mp4') as input_file:
                with tempfile.NamedTemporaryFile(suffix='.mp4') as output_file:
                    result, is_temp = video_converter.convert_to_h264(
                        input_file.name,
                        output_file.name,
                        max_width=1280,
                        max_height=720,
                        overwrite=True
                    )

                    # Check that ffmpeg was called with scaling filter
                    assert result == output_file.name
                    assert not is_temp
                    call_args = mock_run.call_args[0][0]
                    assert '-vf' in call_args
                    assert 'scale=1280:720' in ' '.join(call_args)


def test_convert_to_h264_without_audio(video_converter):
    """Test video conversion without audio."""
    with patch.object(video_converter, 'get_video_info') as mock_info:
        mock_info.return_value = {'codec': 'h264', 'width': 1920, 'height': 1080}

        with patch('subprocess.run', side_effect=create_output_file) as mock_run:
            with tempfile.NamedTemporaryFile(suffix='.mp4') as input_file:
                with tempfile.NamedTemporaryFile(suffix='.mp4') as output_file:
                    result, is_temp = video_converter.convert_to_h264(
                        input_file.name,
                        output_file.name,
                        audio_codec=None,
                        overwrite=True
                    )

                    # Check that ffmpeg was called with -an flag
                    assert result == output_file.name
                    assert not is_temp
                    call_args = mock_run.call_args[0][0]
                    assert '-an' in call_args


def test_convert_to_h264_overwrite_existing(video_converter):
    """Test video conversion with overwrite flag."""
    with patch.object(video_converter, 'get_video_info') as mock_info:
        mock_info.return_value = {'codec': 'h264', 'width': 1920, 'height': 1080}

        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0

            with tempfile.NamedTemporaryFile(suffix='.mp4') as input_file:
                with tempfile.NamedTemporaryFile(suffix='.mp4') as output_file:
                    # Create the output file to simulate existing file
                    with open(output_file.name, 'w', encoding='utf-8') as output_file_handle:
                        output_file_handle.write("existing content")

                    result, is_temp = video_converter.convert_to_h264(
                        input_file.name,
                        output_file.name,
                        overwrite=True
                    )
                    assert result == output_file.name
                    assert not is_temp


def test_convert_to_h264_existing_file_no_overwrite(video_converter):
    """Test video conversion with existing file and no overwrite."""
    with patch.object(video_converter, 'get_video_info') as mock_info:
        mock_info.return_value = {'codec': 'h264', 'width': 1920, 'height': 1080}
        with tempfile.NamedTemporaryFile(suffix='.mp4') as input_file:
            with tempfile.NamedTemporaryFile(suffix='.mp4') as output_file:
                # Create the output file to simulate existing file
                with open(output_file.name, 'w', encoding='utf-8') as output_file_handle:
                    output_file_handle.write("existing content")

                with pytest.raises(FileExistsError):
                    video_converter.convert_to_h264(
                        input_file.name, output_file.name, overwrite=False)


def test_convert_to_h264_with_temp_file(video_converter):
    """Test video conversion that creates a temporary file."""
    with patch.object(video_converter, 'get_video_info') as mock_info:
        mock_info.return_value = {'codec': 'h264', 'width': 1920, 'height': 1080}

        with patch('subprocess.run', side_effect=create_output_file):
            with tempfile.NamedTemporaryFile(suffix='.mp4') as input_file:
                result, is_temp = video_converter.convert_to_h264(input_file.name)

                # Should return a temporary file path and is_temp=True
                assert result.endswith('.mp4')
                assert is_temp

                # Clean up the temp file
                if os.path.exists(result):
                    os.remove(result)

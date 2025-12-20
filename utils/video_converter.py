"""
Video conversion utilities for Watch Tower.

This module provides functionality for converting video files to H.264 format
using ffmpeg, optimized for AWS Rekognition and general use cases.
"""
import json
import os
import subprocess
import tempfile
import uuid
from typing import Any, Dict, List, Optional, Tuple

from utils.error_handler import handle_errors
from utils.logging_config import get_logger
from utils.performance_monitor import monitor_performance
from watch_tower.config import config
from watch_tower.exceptions import VideoConversionError

LOGGER = get_logger(__name__)


class VideoConverter:
    """A library for converting video files to H.264 format using ffmpeg."""

    def __init__(self, ffmpeg_path: Optional[str] = None):
        """
        Initialize the video converter.

        Args:
            ffmpeg_path: Path to ffmpeg executable. If None, will try to find it in PATH.
        """
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        if not self.ffmpeg_path:
            raise RuntimeError(
                "ffmpeg not found. Please install ffmpeg and ensure it's in your PATH.")

        LOGGER.debug("VideoConverter initialized with ffmpeg at: %s", self.ffmpeg_path)

    @staticmethod
    def _find_ffmpeg() -> Optional[str]:
        """Find ffmpeg executable in system PATH."""
        try:
            result = subprocess.run(['which', 'ffmpeg'],
                                    capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Try common installation paths
            common_paths = [
                '/usr/bin/ffmpeg',
                '/usr/local/bin/ffmpeg',
                '/opt/homebrew/bin/ffmpeg',  # macOS Homebrew
                'C:\\ffmpeg\\bin\\ffmpeg.exe',  # Windows
            ]

            for path in common_paths:
                if os.path.exists(path):
                    return path

            return None

    def get_video_info(self, input_path: str) -> Dict[str, Any]:
        """
        Get information about a video file.

        Args:
            input_path: Path to the input video file.

        Returns:
            Dictionary containing video information.

        Raises:
            RuntimeError: If ffprobe fails or video file is invalid.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Use ffprobe to get video information
        cmd = [
            self.ffmpeg_path.replace('ffmpeg', 'ffprobe'),
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            input_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)

            # Extract relevant information
            video_info = {
                'format': info.get('format', {}),
                'streams': info.get('streams', []),
                'duration': float(info.get('format', {}).get('duration', 0)),
                'size': int(info.get('format', {}).get('size', 0)),
                'bitrate': int(info.get('format', {}).get('bit_rate', 0)),
            }

            # Find video stream
            video_stream = None
            for stream in info.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break

            if video_stream:
                video_info.update({
                    'codec': video_stream.get('codec_name'),
                    'width': int(video_stream.get('width', 0)),
                    'height': int(video_stream.get('height', 0)),
                    'fps': self._parse_frame_rate(video_stream.get('r_frame_rate', '0/1')),
                    'pixel_format': video_stream.get('pix_fmt'),
                })

            return video_info

        except subprocess.CalledProcessError as e:
            LOGGER.error("ffprobe failed: %s", e.stderr)
            raise RuntimeError(f"Failed to get video info: {e.stderr}") from e
        except (json.JSONDecodeError, FileNotFoundError) as e:
            LOGGER.error("Failed to parse ffprobe output: %s", e)
            raise RuntimeError("Failed to parse video information") from e

    @staticmethod
    def _cleanup_temp_file(is_temp_file: bool, output_path: str) -> Optional[Exception]:
        """
        Clean up a temporary file if it exists.

        Args:
            is_temp_file: Whether the file is a temporary file
            output_path: Path to the file to clean up

        Returns:
            Exception if cleanup failed, None otherwise
        """
        if is_temp_file and os.path.exists(output_path):
            try:
                os.remove(output_path)
                return None
            except Exception as cleanup_err:
                LOGGER.warning("Failed to cleanup temp file: %s", cleanup_err)
                return cleanup_err
        return None

    @staticmethod
    def _create_conversion_error(
            error_msg: str,
            original_error: Exception,
            cleanup_error: Optional[Exception]
    ) -> VideoConversionError:
        """
        Create a VideoConversionError with proper error chaining.

        Args:
            error_msg: Base error message
            original_error: The original exception that occurred
            cleanup_error: Exception from cleanup if it failed, None otherwise

        Returns:
            VideoConversionError with proper error chaining
        """
        if cleanup_error:
            error_msg += f" (cleanup also failed: {cleanup_error})"

        conversion_error = VideoConversionError(error_msg)
        # Chain both errors: original as cause, cleanup as context if it exists
        if cleanup_error:
            conversion_error.__cause__ = original_error
            conversion_error.__context__ = cleanup_error
        else:
            # Chain original error as cause when no cleanup error
            conversion_error.__cause__ = original_error
        return conversion_error

    @staticmethod
    def _parse_frame_rate(frame_rate_str: str) -> float:
        """
        Parse frame rate string (e.g., "30/1") to float.

        Args:
            frame_rate_str: Frame rate string in format "numerator/denominator"

        Returns:
            Frame rate as float
        """
        try:
            parts = frame_rate_str.split('/')
            if len(parts) == 2:
                numerator = float(parts[0])
                denominator = float(parts[1])
                return numerator / denominator if denominator != 0 else 0.0
            return float(frame_rate_str)
        except (ValueError, ZeroDivisionError):
            return 0.0

    def _build_ffmpeg_command(
            self,
            input_path: str,
            output_path: str,
            preset: str,
            crf: int,
            max_width: Optional[int],
            max_height: Optional[int],
            audio_codec: Optional[str]) -> List[str]:
        """Build the ffmpeg command for video conversion.

        Args:
            input_path: Path to input video
            output_path: Path to output video
            preset: FFmpeg preset
            crf: Constant Rate Factor
            max_width: Maximum width
            max_height: Maximum height
            audio_codec: Audio codec or None

        Returns:
            List of command arguments
        """
        cmd = [self.ffmpeg_path, '-i', input_path]

        # Build video filters
        video_filters = []
        if max_width or max_height:
            scale_filter = 'scale='
            if max_width and max_height:
                scale_filter += f'{max_width}:{max_height}'
            elif max_width:
                scale_filter += f'{max_width}:-2'
            elif max_height:
                scale_filter += f'-2:{max_height}'
            video_filters.append(scale_filter)

        if video_filters:
            cmd.extend(['-vf', ','.join(video_filters)])

        # Video codec settings
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', preset,
            '-crf', str(crf),
            '-tune', 'fastdecode',
            '-movflags', '+faststart'
        ])

        # Audio settings
        if audio_codec:
            cmd.extend(['-c:a', audio_codec])
        else:
            cmd.extend(['-an'])

        cmd.append(output_path)
        return cmd

    @staticmethod
    def _determine_output_path(
            output_path: Optional[str]) -> Tuple[str, bool]:
        """Determine the output path for conversion.

        Args:
            output_path: Optional output path

        Returns:
            Tuple of (output_path, is_temp_file)
        """
        if output_path is None:
            unique_filename = f"tmp_{uuid.uuid4().hex}.mp4"
            output_path = os.path.join(tempfile.gettempdir(), unique_filename)
            return output_path, True
        return output_path, False

    @monitor_performance("video_conversion")
    @handle_errors(RuntimeError, log_error=True, reraise=True)
    def convert_to_h264(self,
                        input_path: str,
                        output_path: Optional[str] = None,
                        preset: str = None,  # Use config default
                        crf: int = None,  # Use config default
                        max_width: Optional[int] = None,
                        max_height: Optional[int] = None,
                        audio_codec: Optional[str] = 'aac',
                        overwrite: bool = False) -> Tuple[str, bool]:
        """
        Convert a video file to H.264 format.

        Args:
            input_path: Path to the input video file.
            output_path: Path for the output file. If None, creates a temp file.
            preset: FFmpeg preset (ultrafast, superfast, veryfast, faster, fast,
                    medium, slow, slower, veryslow).
            crf: Constant Rate Factor (0-51, lower is better quality, 28 is default for speed).
            max_width: Maximum width for the output video.
            max_height: Maximum height for the output video.
            audio_codec: Audio codec to use (None to skip audio).
            overwrite: Whether to overwrite existing output file.

        Returns:
            Tuple of (path to the converted video file, is_temp_file).

        Raises:
            FileNotFoundError: If input file not found.
            FileExistsError: If output file already exists and overwrite is False.
            VideoConversionError: If conversion fails with specific error message.
        """
        # Use config defaults if not provided
        preset = preset or config.video.default_preset
        crf = crf or config.video.default_crf

        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Get input video info
        input_info = self.get_video_info(input_path)
        LOGGER.debug(
            "Converting video: %s -> H.264",
            input_info.get('codec', 'unknown')
        )

        # Determine output path
        output_path, is_temp_file = VideoConverter._determine_output_path(output_path)
        if is_temp_file:
            overwrite = True  # Always allow overwrite for temp files

        # Check if output file exists
        if os.path.exists(output_path) and not overwrite:
            raise FileExistsError(f"Output file already exists: {output_path}")

        # Build ffmpeg command
        cmd = self._build_ffmpeg_command(
            input_path, output_path, preset, crf,
            max_width, max_height, audio_codec
        )

        # Run conversion
        try:
            LOGGER.debug("Starting conversion: %s", ' '.join(cmd))
            LOGGER.debug("Input file size: %s bytes", os.path.getsize(input_path))
            LOGGER.debug("Output path: %s", output_path)

            # Use timeout and better subprocess handling
            # Don't capture stderr as FFmpeg writes progress there
            subprocess.run(
                cmd,
                capture_output=False,  # Don't capture output to avoid hanging
                text=True,
                check=True,
                timeout=config.video.ffmpeg_timeout  # Use config timeout
            )

            # Log conversion results
            if os.path.exists(output_path):
                output_size = os.path.getsize(output_path)
                LOGGER.info("Conversion completed successfully: %s", output_path)
                LOGGER.debug("Output file size: %s bytes", output_size)
            else:
                LOGGER.error("Conversion completed but output file not found")
                raise RuntimeError("Output file not created")

            return output_path, is_temp_file

        except subprocess.TimeoutExpired as e:
            cleanup_error = VideoConverter._cleanup_temp_file(is_temp_file, output_path)
            LOGGER.error(
                "FFmpeg conversion timed out after %s seconds",
                config.video.ffmpeg_timeout
            )
            raise VideoConverter._create_conversion_error(
                f"Video conversion timed out after {config.video.ffmpeg_timeout} seconds",
                e, cleanup_error
            )
        except subprocess.CalledProcessError as e:
            cleanup_error = VideoConverter._cleanup_temp_file(is_temp_file, output_path)
            LOGGER.error(
                "FFmpeg conversion failed with return code: %s",
                e.returncode
            )
            raise VideoConverter._create_conversion_error(
                f"Video conversion failed with return code: {e.returncode}",
                e, cleanup_error
            )
        finally:
            # Placeholder for future metrics
            pass

    def convert_for_rekognition(self, input_path: str,
                                output_path: Optional[str] = None) -> Tuple[str, bool]:
        """
        Convert video specifically optimized for AWS Rekognition.

        Args:
            input_path: Path to the input video file.
            output_path: Path for the output file. If None, creates a temp file.

        Returns:
            Tuple of (path to the converted video file, is_temp_file).
        """
        return self.convert_to_h264(
            input_path=input_path,
            output_path=output_path,
            preset=config.video.rekognition_preset,  # Use config preset
            crf=config.video.rekognition_crf,  # Use config CRF
            max_width=config.video.max_width,  # Use config max width
            max_height=config.video.max_height,  # Use config max height
            audio_codec=None,  # No audio needed for face detection
            overwrite=True
        )


# Create a singleton instance
VIDEO_CONVERTER = VideoConverter()

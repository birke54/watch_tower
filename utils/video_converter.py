import os
import subprocess
import tempfile
import uuid
from typing import Optional, Tuple, Dict, Any
from watch_tower.config import config
from utils.logging_config import get_logger
from utils.error_handler import handle_errors
from utils.performance_monitor import monitor_performance

logger = get_logger(__name__)


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

        logger.debug(f"VideoConverter initialized with ffmpeg at: {self.ffmpeg_path}")

    def _find_ffmpeg(self) -> Optional[str]:
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
            import json
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
                    'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                    'pixel_format': video_stream.get('pix_fmt'),
                })

            return video_info

        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe failed: {e.stderr}")
            raise RuntimeError(f"Failed to get video info: {e.stderr}")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to parse ffprobe output: {e}")
            raise RuntimeError("Failed to parse video information")

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
            RuntimeError: If conversion fails.
        """
        # Use config defaults if not provided
        preset = preset or config.video.default_preset
        crf = crf or config.video.default_crf

        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Get input video info
        input_info = self.get_video_info(input_path)
        logger.debug(f"Converting video: {input_info.get('codec', 'unknown')} -> H.264")

        # Determine output path
        is_temp_file = False
        if output_path is None:
            # Create temp file with unique name using UUID
            unique_filename = f"tmp_{uuid.uuid4().hex}.mp4"
            output_path = os.path.join(tempfile.gettempdir(), unique_filename)
            is_temp_file = True
            overwrite = True  # Always allow overwrite for temp files

        # Check if output file exists
        if os.path.exists(output_path) and not overwrite:
            raise FileExistsError(f"Output file already exists: {output_path}")

        # Build ffmpeg command
        cmd = [self.ffmpeg_path, '-i', input_path]

        # Video settings
        video_filters = []

        # Add scaling if needed
        if max_width or max_height:
            scale_filter = 'scale='
            if max_width and max_height:
                scale_filter += f'{max_width}:{max_height}'
            elif max_width:
                scale_filter += f'{max_width}:-2'
            elif max_height:
                scale_filter += f'-2:{max_height}'
            video_filters.append(scale_filter)

        # Add video filters if any
        if video_filters:
            cmd.extend(['-vf', ','.join(video_filters)])

        # Video codec settings - optimized for speed
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', preset,
            '-crf', str(crf),
            '-tune', 'fastdecode',  # Optimize for fast decoding
            '-movflags', '+faststart'  # Optimize for web streaming
        ])

        # Audio settings
        if audio_codec:
            cmd.extend(['-c:a', audio_codec])
        else:
            cmd.extend(['-an'])  # No audio

        # Output file
        cmd.append(output_path)

        # Run conversion
        try:
            logger.debug(f"Starting conversion: {' '.join(cmd)}")
            logger.debug(f"Input file size: {os.path.getsize(input_path)} bytes")
            logger.debug(f"Output path: {output_path}")

            # Use timeout and better subprocess handling
            # Don't capture stderr as FFmpeg writes progress there
            result = subprocess.run(
                cmd,
                capture_output=False,  # Don't capture output to avoid hanging
                text=True,
                check=True,
                timeout=config.video.ffmpeg_timeout  # Use config timeout
            )

            # Log conversion results
            if os.path.exists(output_path):
                output_size = os.path.getsize(output_path)
                logger.info(f"Conversion completed successfully: {output_path}")
                logger.debug(f"Output file size: {output_size} bytes")
            else:
                logger.error("Conversion completed but output file not found")
                raise RuntimeError("Output file not created")

            return output_path, is_temp_file

        except subprocess.TimeoutExpired:
            logger.error(
                f"FFmpeg conversion timed out after {config.video.ffmpeg_timeout} seconds")
            # Clean up temp file if conversion failed
            if is_temp_file and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to cleanup temp file after timeout: {cleanup_error}")
            raise RuntimeError(
                f"Video conversion timed out after {config.video.ffmpeg_timeout} seconds")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion failed with return code: {e.returncode}")
            # Clean up temp file if conversion failed
            if is_temp_file and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to cleanup temp file after conversion error: {cleanup_error}")
            raise RuntimeError(
                f"Video conversion failed with return code: {e.returncode}")

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

    def cleanup_temp_file(self, file_path: str) -> None:
        """
        Clean up a temporary file.

        Args:
            file_path: Path to the file to delete.
        """
        try:
            if os.path.exists(file_path) and file_path.startswith(
                    tempfile.gettempdir()):
                os.remove(file_path)
                logger.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")


# Create a singleton instance
video_converter = VideoConverter()

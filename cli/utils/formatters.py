"""
CLI Formatting Utilities

This module contains utility functions for formatting data for CLI output,
including timestamps, confidence scores, and JSON entries.
"""

from datetime import datetime
from typing import Any, Dict, Optional

# Constants
DEFAULT_TIMEZONE = "America/Los_Angeles"


def format_confidence_score(score: Optional[float]) -> str:
    """Format confidence score as percentage string."""
    if score is None:
        return 'Unknown'
    return f"{(score * 100):.1f}%"


def format_timestamp(
        timestamp: Optional[datetime],
        timezone_name: str = DEFAULT_TIMEZONE) -> str:
    """Format timestamp for display."""
    if timestamp is None:
        return 'Unknown'
    import pytz
    local_tz = pytz.timezone(timezone_name)
    local_time = timestamp.astimezone(local_tz)
    return local_time.isoformat(sep=' ')


def create_json_entry(entry: Any) -> Dict[str, Any]:
    """Convert database entry to JSON-serializable format."""
    return {
        'visitor_log_id': entry.visitor_log_id,
        'camera_name': entry.camera_name,
        'persons_name': entry.persons_name,
        'confidence_score': round(
            entry.confidence_score * 100,
            1) if entry.confidence_score else None,
        'visited_at': entry.visited_at.isoformat() if entry.visited_at else None,
        'created_at': entry.created_at.isoformat() if entry.created_at else None}

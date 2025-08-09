import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any
from utils.logging_config import get_logger

logger = get_logger(__name__)

# SQLite database file path
CAMERA_STATE_DB_PATH = "/tmp/camera_state.db"


def init_camera_state_db() -> None:
    """Initialize the camera state SQLite database."""
    try:
        conn = sqlite3.connect(CAMERA_STATE_DB_PATH)
        cursor = conn.cursor()

        # Create camera_states table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS camera_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                vendor TEXT NOT NULL,
                status TEXT NOT NULL,
                last_polled TEXT,
                status_last_updated TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, vendor)
            )
        ''')

        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON camera_states(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vendor ON camera_states(vendor)')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_name_vendor ON camera_states(name, vendor)')

        conn.commit()
        conn.close()
        logger.debug("Camera state database initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize camera state database: {e}")
        raise


def save_camera_states(camera_states: List[Dict[str, Any]]) -> None:
    """Save camera states to SQLite database."""
    try:
        conn = sqlite3.connect(CAMERA_STATE_DB_PATH)
        cursor = conn.cursor()

        # Clear existing states
        cursor.execute('DELETE FROM camera_states')

        # Insert current states
        for camera_state in camera_states:
            cursor.execute('''
                INSERT OR REPLACE INTO camera_states
                (name, vendor, status, last_polled, status_last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                camera_state['name'],
                camera_state['vendor'],
                camera_state['status'],
                camera_state['last_polled'],
                camera_state['status_last_updated']
            ))

        conn.commit()
        conn.close()
        logger.debug(f"Saved {len(camera_states)} camera states to database")

    except Exception as e:
        logger.error(f"Failed to save camera states to database: {e}")
        raise


def load_camera_states() -> List[Dict[str, Any]]:
    """Load camera states from SQLite database."""
    try:
        if not os.path.exists(CAMERA_STATE_DB_PATH):
            logger.debug("Camera state database does not exist, returning empty list")
            return []

        conn = sqlite3.connect(CAMERA_STATE_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT name, vendor, status, last_polled, status_last_updated
            FROM camera_states
            ORDER BY name
        ''')
        rows = cursor.fetchall()

        camera_states = []
        for row in rows:
            camera_states.append({
                'name': row[0],
                'vendor': row[1],
                'status': row[2],
                'last_polled': row[3],
                'status_last_updated': row[4]
            })

        conn.close()
        logger.debug(f"Loaded {len(camera_states)} camera states from database")
        return camera_states

    except Exception as e:
        logger.error(f"Failed to load camera states from database: {e}")
        return []


def get_camera_state(camera_name: str, vendor: str) -> Dict[str, Any]:
    """Get a specific camera state from the database."""
    try:
        conn = sqlite3.connect(CAMERA_STATE_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT name, vendor, status, last_polled, status_last_updated
            FROM camera_states
            WHERE name = ? AND vendor = ?
        ''', (camera_name, vendor))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'name': row[0],
                'vendor': row[1],
                'status': row[2],
                'last_polled': row[3],
                'status_last_updated': row[4]
            }
        else:
            return {}

    except Exception as e:
        logger.error(f"Failed to get camera state for {camera_name}: {e}")
        return {}


def update_camera_status(camera_name: str, vendor: str, status: str) -> None:
    """Update the status of a specific camera."""
    try:
        conn = sqlite3.connect(CAMERA_STATE_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE camera_states
            SET status = ?, status_last_updated = ?
            WHERE name = ? AND vendor = ?
        ''', (status, datetime.now().isoformat(), camera_name, vendor))

        conn.commit()
        conn.close()
        logger.debug(f"Updated camera {camera_name} status to {status}")

    except Exception as e:
        logger.error(f"Failed to update camera status for {camera_name}: {e}")
        raise

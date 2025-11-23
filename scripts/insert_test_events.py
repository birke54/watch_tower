import sys
import os
import datetime
import json
from sqlalchemy import text
from connection_managers.plugin_type import PluginType

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_database_connection


def insert_test_events():
    engine, session_factory = get_database_connection()

    with session_factory() as session:
        # Delete all existing entries
        delete_query = text("DELETE FROM motion_events")
        session.execute(delete_query)
        session.commit()
        print("Deleted existing entries from motion_events table")

        # Create a future date for unprocessed events
        now = datetime.datetime.now(datetime.timezone.utc)
        future_date = datetime.datetime(9998, 12, 31, 23, 59, 59, tzinfo=now.tzinfo)

        # Insert test events
        insert_query = text("""
            INSERT INTO motion_events
            (camera_name, motion_detected, uploaded_to_s3, facial_recognition_processed, s3_url, created_at, updated_at, event_metadata)
            VALUES
            (:camera_name, :motion_detected, :uploaded_to_s3, :facial_recognition_processed, :s3_url, :created_at, :updated_at, :event_metadata)
        """)

        # Test event 1: Unprocessed event
        session.execute(insert_query, {
            "camera_name": "Front Door",
            "motion_detected": now - datetime.timedelta(minutes=5),
            "uploaded_to_s3": future_date,
            "facial_recognition_processed": future_date,
            "s3_url": "",
            "created_at": now,
            "updated_at": now,
            "event_metadata": json.dumps({
                "event_id": 7513330516411329940,
                "camera_vendor": PluginType.RING.value
            })
        })

        session.execute(insert_query, {
            "camera_name": "Front Door",
            "motion_detected": now - datetime.timedelta(minutes=5),
            "uploaded_to_s3": future_date,
            "facial_recognition_processed": future_date,
            "s3_url": "",
            "created_at": now,
            "updated_at": now,
            "event_metadata": json.dumps({
                "event_id": 7516402075157966228,
                "camera_vendor": PluginType.RING.value
            })
        })

        # Test event 2: Partially processed event
        session.execute(insert_query, {
            "camera_name": "Front Door",
            "motion_detected": now - datetime.timedelta(minutes=10),
            "uploaded_to_s3": now - datetime.timedelta(minutes=9),
            "facial_recognition_processed": future_date,
            "s3_url": "https://example.com/video1.mp4",
            "created_at": now,
            "updated_at": now,
            "event_metadata": json.dumps({
                "event_id": 7513330516411329940,
                "camera_vendor": PluginType.RING.value
            })
        })

        # Test event 3: Fully processed event
        session.execute(insert_query, {
            "camera_name": "Front Door",
            "motion_detected": now - datetime.timedelta(minutes=15),
            "uploaded_to_s3": now - datetime.timedelta(minutes=14),
            "facial_recognition_processed": now - datetime.timedelta(minutes=13),
            "s3_url": "https://example.com/video2.mp4",
            "created_at": now,
            "updated_at": now,
            "event_metadata": json.dumps({
                "event_id": 7513330516411329940,
                "camera_vendor": PluginType.RING.value
            })
        })

        session.commit()
        print("Successfully inserted test events")


if __name__ == "__main__":
    insert_test_events()

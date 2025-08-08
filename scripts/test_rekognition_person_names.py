#!/usr/bin/env python3
"""
Test script to verify that person names are taken directly from Rekognition results.
"""

import asyncio
import sys
import os
import datetime
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aws.rekognition.rekognition_service import RekognitionService
from db.connection import get_database_connection
from db.repositories.motion_event_repository import MotionEventRepository
from db.repositories.visitor_log_repository import VisitorLogRepository

# Load environment variables
load_dotenv()

async def test_rekognition_person_names(video_s3_url: str):
    """
    Test that person names are taken directly from Rekognition results.

    Args:
        video_s3_url: S3 URL of the video to analyze
    """
    try:
        print(f"Testing Rekognition person names for video: {video_s3_url}")

        # Initialize services
        rekognition_service = RekognitionService()
        engine, session_factory = get_database_connection()

        # Start face search
        print("Starting face search...")
        face_search_results = await rekognition_service.start_face_search(video_s3_url)

        print(f"Face search results: {face_search_results}")
        print(f"Number of face matches found: {len(face_search_results)}")

        if not face_search_results:
            print("No face matches found. Cannot test person name extraction.")
            return

        # Display person names from Rekognition
        print("\nPerson names from Rekognition:")
        for i, match in enumerate(face_search_results):
            external_image_id = match.get('external_image_id')
            confidence = match.get('confidence', 0.0)
            face_id = match.get('face_id')
            timestamp = match.get('timestamp')

            print(f"  {i+1}. Person Name: '{external_image_id}'")
            print(f"     Face ID: {face_id}")
            print(f"     Confidence: {confidence:.2f}")
            print(f"     Timestamp: {timestamp}")
            print()

        # Test visitor log creation with a mock motion event
        with session_factory() as session:
            # Create a test motion event
            motion_event_repository = MotionEventRepository()
            test_event_data = {
                "camera_name": "test_camera",
                "motion_detected": datetime.datetime.now(),
                "uploaded_to_s3": datetime.datetime.now(),
                "facial_recognition_processed": datetime.datetime(9999, 12, 31, 23, 59, 59),
                "s3_url": video_s3_url,
                "event_metadata": {"test": True}
            }
            test_event = motion_event_repository.create(session, test_event_data)

            print(f"Created test motion event ID: {test_event.id}")

            # Test visitor log creation
            await create_visitor_logs_from_rekognition(
                face_search_results,
                test_event,
                session_factory
            )

            # Verify visitor logs were created
            visitor_log_repository = VisitorLogRepository()
            visitor_logs = visitor_log_repository.get_by_event(session, test_event.id)

            print(f"\nCreated {len(visitor_logs)} visitor log entries:")
            for log in visitor_logs:
                print(f"  - Person Name: '{log.persons_name}'")
                print(f"    Confidence: {log.confidence_score:.2f}")
                print(f"    Visited: {log.visited_at}")
                print()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

async def create_visitor_logs_from_rekognition(
    face_search_results: list,
    db_event: any,
    session_factory: any
) -> None:
    """Create visitor log entries using person names directly from Rekognition"""
    try:
        with session_factory() as session:
            visitor_log_repository = VisitorLogRepository()

            for match in face_search_results:
                external_image_id = match.get('external_image_id')
                confidence_score = match.get('confidence', 0.95)

                # Use external_image_id directly as the person name from Rekognition
                person_name = external_image_id

                # Create visitor log entry using the person name directly
                visitor_log_data = {
                    "camera_name": db_event.camera_name,
                    "persons_name": person_name,  # Store the person name directly
                    "confidence_score": confidence_score,
                    "visited_at": db_event.motion_detected,
                }

                visitor_log_repository.create(session, visitor_log_data)
                print(f"Created visitor log for person '{person_name}' with confidence {confidence_score}")

    except Exception as e:
        print(f"Error creating visitor logs: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function to run the test."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_rekognition_person_names.py <s3_url>")
        print("\nExample:")
        print("  python test_rekognition_person_names.py s3://my-bucket/video.mp4")
        return

    video_url = sys.argv[1]
    asyncio.run(test_rekognition_person_names(video_url))

if __name__ == "__main__":
    main()
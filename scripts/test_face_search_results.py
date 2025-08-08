#!/usr/bin/env python3
"""
Quick script to test the get_face_search_results function.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aws.rekognition.rekognition_service import RekognitionService

# Load environment variables
load_dotenv()

async def test_get_face_search_results(job_id: str):
    """
    Test the get_face_search_results function with a given job ID.

    Args:
        job_id: The Rekognition job ID to check
    """
    try:
        print(f"Testing get_face_search_results for job ID: {job_id}")

        # Initialize the Rekognition service
        rekognition_service = RekognitionService()

        # Get the face search results
        print("Calling get_face_search_results...")
        results = await rekognition_service.get_face_search_results(job_id)

        print(f"Raw results: {results}")
        print(f"Number of face matches found: {len(results)}")

        if results:
            print("\nFace matches:")
            for match_type, face_id, external_image_id in results:
                print(f"  - {match_type}: {face_id} (External ID: {external_image_id})")

            # Resolve names using AWS Rekognition ExternalImageId
            print("\nResolving names from AWS Rekognition...")
            face_to_name = rekognition_service.resolve_face_names(results)

            print("\nResolved names:")
            for face_id, name in face_to_name.items():
                print(f"  - {face_id} -> {name}")
        else:
            print("No face matches found.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

async def test_start_face_search_and_get_results(video_s3_url: str):
    """
    Test the complete flow: start face search and get results.

    Args:
        video_s3_url: S3 URL of the video to analyze
    """
    try:
        print(f"Testing complete face search flow for video: {video_s3_url}")

        # Initialize the Rekognition service
        rekognition_service = RekognitionService()

        # Start face search (this will also get results)
        print("Starting face search...")
        results = await rekognition_service.start_face_search(video_s3_url)

        print(f"Raw results: {results}")
        print(f"Number of face matches found: {len(results)}")

        if results:
            print("\nFace matches:")
            for match_type, face_id, external_image_id in results:
                print(f"  - {match_type}: {face_id} (External ID: {external_image_id})")

            # Resolve names using AWS Rekognition ExternalImageId
            print("\nResolving names from AWS Rekognition...")
            face_to_name = rekognition_service.resolve_face_names(results)

            print("\nResolved names:")
            for face_id, name in face_to_name.items():
                print(f"  - {face_id} -> {name}")
        else:
            print("No face matches found.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function to run the test."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_face_search_results.py <job_id>")
        print("  python test_face_search_results.py --video <s3_url>")
        print("\nExamples:")
        print("  python test_face_search_results.py abc123def456")
        print("  python test_face_search_results.py --video s3://my-bucket/video.mp4")
        return

    if sys.argv[1] == "--video" and len(sys.argv) >= 3:
        # Test complete flow with video URL
        video_url = sys.argv[2]
        asyncio.run(test_start_face_search_and_get_results(video_url))
    else:
        # Test just getting results for existing job
        job_id = sys.argv[1]
        asyncio.run(test_get_face_search_results(job_id))

if __name__ == "__main__":
    main()
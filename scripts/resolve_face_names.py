#!/usr/bin/env python3
"""
Simple script to resolve face names from face IDs using AWS Rekognition.
Note: This script requires the ExternalImageId from face search results.
For direct face ID resolution, you would need to call AWS Rekognition APIs.
"""

import sys
import os
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aws.rekognition.rekognition_service import RekognitionService

# Load environment variables
load_dotenv()


def resolve_face_names_from_search_results(face_matches: list):
    """
    Resolve face names from face search results.

    Args:
        face_matches: List of tuples (match_type, face_id, external_image_id)
    """
    try:
        print(f"Resolving names for face matches: {face_matches}")

        # Initialize the Rekognition service
        rekognition_service = RekognitionService()

        # Convert list to set for the method
        face_matches_set = set(face_matches)

        # Resolve names using AWS Rekognition ExternalImageId
        face_to_name = rekognition_service.resolve_face_names(face_matches_set)

        print("\nResolved names:")
        for face_id, name in face_to_name.items():
            print(f"  - {face_id} -> {name}")

        return face_to_name

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {}


def main():
    """Main function to run the name resolution."""
    if len(sys.argv) < 2:
        print("Usage:")
        print(
            "  python resolve_face_names.py <match_type> <face_id> <external_image_id> [match_type2] [face_id2] [external_image_id2] ...")
        print("\nExample:")
        print("  python resolve_face_names.py FaceId abc123def456 john_doe FaceId xyz789ghi012 jane_smith")
        print("\nNote: This script requires the ExternalImageId from face search results.")
        print("For direct face ID resolution, use the test_face_search_results.py script instead.")
        return

    # Get arguments in groups of 3 (match_type, face_id, external_image_id)
    args = sys.argv[1:]
    if len(args) % 3 != 0:
        print("Error: Arguments must be in groups of 3: match_type face_id external_image_id")
        return

    # Parse arguments into tuples
    face_matches = []
    for i in range(0, len(args), 3):
        match_type = args[i]
        face_id = args[i + 1]
        external_image_id = args[i + 2]
        face_matches.append((match_type, face_id, external_image_id))

    # Resolve names
    resolve_face_names_from_search_results(face_matches)


if __name__ == "__main__":
    main()

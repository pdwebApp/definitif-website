#!/usr/bin/env python3

import os
from pathlib import Path
from supabase import create_client


# =====================================================
# CONFIG
# =====================================================

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BUCKET_NAME = "portfolio-data"

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "output",
    "users"
)


# =====================================================
# SUPABASE CLIENT
# =====================================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)

# =====================================================
# CLEAR DATABASE
# =====================================================

def clear_bucket():

    print("\nClearing existing bucket contents...")

    try:

        existing_files = supabase.storage.from_(BUCKET_NAME).list(
                        path="",
                        options={
                            "limit": 1000,
                            "offset": 0,
                            "sortBy": {
                                "column": "name",
                                "order": "asc"
                            }
                        }
                    )

        if not existing_files:
            print("Bucket already empty")
            return

        file_paths = [
            file["name"]
            for file in existing_files
        ]

        supabase.storage.from_(BUCKET_NAME).remove(file_paths)

        print(f"Deleted {len(file_paths)} existing files")

    except Exception as e:

        print("Error clearing bucket")
        print(str(e))

# =====================================================
# MAIN
# =====================================================

def main():

    clear_bucket()

    print("=" * 60)
    print("SUPABASE STORAGE UPLOAD STARTED")
    print("=" * 60)

    folder = Path(OUTPUT_DIR)

    files = list(folder.glob("*.json"))

    print(f"JSON files found: {len(files)}")

    for file_path in files:

        filename = file_path.name

        print(f"\nUploading: {filename}")

        try:

            with open(file_path, "rb") as f:
                file_data = f.read()

            supabase.storage.from_(BUCKET_NAME).upload(
                path=filename,
                file=file_data,
                file_options={
                    "content-type": "application/json",
                    "upsert": "true"
                }
            )

            print(f"SUCCESS: {filename}")

        except Exception as e:

            print(f"FAILED: {filename}")
            print(str(e))

    print("\n" + "=" * 60)
    print("UPLOAD PROCESS COMPLETED")
    print("=" * 60)


# =====================================================
# ENTRY POINT
# =====================================================

if __name__ == "__main__":
    main()
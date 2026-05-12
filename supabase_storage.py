import os
import json
from supabase import create_client


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

BUCKET_NAME = "portfolio-data"

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


def fetch_json(filename):

    try:

        response = (
            supabase
            .storage
            .from_(BUCKET_NAME)
            .download(filename)
        )

        return json.loads(
            response.decode("utf-8")
        )

    except Exception as e:

        print(f"Storage fetch failed: {filename}")
        print(str(e))

        return None
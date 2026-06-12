import os
import json
from supabase import create_client


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

BUCKET_NAME = "portfolio-data"

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)


def fetch_json(filename):

    bucket = "portfolio-data"

    try:
        res = supabase.storage.from_(bucket).download(filename)
        return json.loads(res.decode("utf-8"))

    except Exception as e:
        print("FAILED FILE:", filename)
        print("ERROR:", str(e))
        return None
import pandas as pd
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)




def load_user_configs():

    all_rows = []
    start = 0
    batch = 1000

    while True:
        response = (
            supabase
            .table("dashboard_users")
            .select("*")
            .range(start, start + batch - 1)
            .execute()
        )

        data = response.data

        if not data:
            break

        all_rows.extend(data)

        if len(data) < batch:
            break

        start += batch

    df = pd.DataFrame(all_rows)

    # convert to list of dicts
    users = []

    for _, row in df.iterrows():

        pans = row.get("pans")
        if isinstance(pans, str):
            pans = [p.strip() for p in pans.split(",") if p.strip()]
        elif pd.isna(pans):
            pans = []
        elif not isinstance(pans, list):
            pans = [pans]

        users.append({
            "login_id": row["login_id"],
            "password": row["password"],
            "name": row["name"],
            "user_type": row["user_type"],
            "family_name": row.get("family_name"),
            "pans": pans,
            "mfu_can": row.get("mfu_can"),
            "mobile": row.get("mobile"),
            "email_connect": row.get("email_connect"),
            "dob": row.get("dob")
        })

    return users
# user_data.py
import json
from pathlib import Path

def load_user_index(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def find_user_record(user_index: dict, login_id: str) -> dict | None:
    return next((u for u in user_index.get("users", []) if u.get("login") == login_id), None)

def load_client_json(users_dir: str, file_name: str) -> dict:
    p = Path(users_dir) / file_name
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def get_recipient_email(user_record: dict) -> str:
    return (user_record.get("email_connect") or "").strip()

def get_client_name(client_json: dict) -> str:
    return client_json.get("name") or client_json.get("data", {}).get("l") or "Client"

def get_valuation_date(client_json: dict) -> str:
    return client_json.get("data", {}).get("kpi", {}).get("val_date", "")
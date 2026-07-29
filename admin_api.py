from flask import Blueprint, jsonify
from supabase import create_client
import os

admin_api = Blueprint("admin_api", __name__)

def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url:
        raise RuntimeError("SUPABASE_URL is missing")
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is missing")

    return create_client(url, key)

@admin_api.route("/api/admin/dashboard")
def get_admin_dashboard():
    supabase = get_supabase()
    response = (
        supabase
        .table("admin_dashboard")
        .select("*")
        .order("valuation_date", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        return jsonify({})

    return jsonify(response.data[0])

@admin_api.route("/api/admin/clients")
def get_admin_clients():
    supabase = get_supabase()
    response = (
        supabase
        .table("admin_clients")
        .select("""
            login_id,
            name,
            pan,
            mfu_can,
            mobile,
            email_connect,
            dob,
            portfolio_value
        """)
        .order("portfolio_value", desc=True)
        .execute()
    )

    return jsonify(response.data)
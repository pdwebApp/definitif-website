from flask import Blueprint, jsonify
from supabase import create_client
import os

admin_api = Blueprint("admin_api", __name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)


# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

@admin_api.route("/api/admin/dashboard")
def get_admin_dashboard():

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


# ==========================================================
# ADMIN CLIENTS
# ==========================================================

@admin_api.route("/api/admin/clients")
def get_admin_clients():

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
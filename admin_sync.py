import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)


# ----------------------------------------------------------
# ADMIN CLIENTS
# ----------------------------------------------------------

def sync_admin_clients(admin_clients):

    print("\nSyncing admin_clients...")

    if not admin_clients:
        print("No admin clients to sync.")
        return

    # ---------------------------------------------------
    # UPSERT latest clients
    # ---------------------------------------------------

    (
        supabase
        .table("admin_clients")
        .upsert(
            admin_clients,
            on_conflict="login_id"
        )
        .execute()
    )

    print(f"Upserted {len(admin_clients)} clients.")

    # ---------------------------------------------------
    # FETCH existing login_ids
    # ---------------------------------------------------

    response = (
        supabase
        .table("admin_clients")
        .select("login_id", count="exact")
        .execute()
    )

    print(f"Admin table now contains {response.count} clients.")

    existing = {
        row["login_id"]
        for row in response.data
        if row["login_id"]
    }

    current = {
        row["login_id"]
        for row in admin_clients
    }

    stale = sorted(existing - current)

    # ---------------------------------------------------
    # DELETE removed users
    # ---------------------------------------------------

    if stale:

        print(f"Removing {len(stale)} stale clients...")

        (
            supabase
            .table("admin_clients")
            .delete()
            .in_("login_id", stale)
            .execute()
        )

    else:

        print("No stale clients found.")

    print("admin_clients sync completed.")


# ----------------------------------------------------------
# DASHBOARD SUMMARY
# ----------------------------------------------------------

def sync_dashboard_summary(dashboard_summary):
    """
    Upsert dashboard summary.
    One row per valuation_date.
    """

    print("\nSyncing admin_dashboard...")

    if not dashboard_summary:
        print("No dashboard summary to sync.")
        return

    response = (
        supabase
        .table("admin_dashboard")
        .upsert(
            dashboard_summary,
            on_conflict="valuation_date"
        )
        .execute()
    )

    print("Dashboard summary updated.")

    return response


# ----------------------------------------------------------
# WRAPPER
# ----------------------------------------------------------

def sync_admin_portal(admin_clients, dashboard_summary):

    sync_admin_clients(admin_clients)

    sync_dashboard_summary(dashboard_summary)

    print("\nAdmin Portal Sync Complete.")
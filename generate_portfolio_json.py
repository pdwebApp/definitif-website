#!/usr/bin/env python3

import os
import sys
import traceback
from datetime import date, timedelta

# =====================================================
# PATHS
# =====================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "output",
    "users"
)

# Optional (only needed if imports fail)
sys.path.insert(0, BASE_DIR)

# =====================================================
# IMPORTS
# =====================================================

from portfolio_analytics import (
    get_effective_nav,
    load_data_from_supabase,
    build_portfolio_analytics,
    generate_portfolio_json,
)

from user_config_loader import load_user_configs


# =====================================================
# CONFIG
# =====================================================

VALUATION_DATE = date.today() - timedelta(days=1)

# =====================================================
# MAIN
# =====================================================

def main():
    import os

    print("RUN FILE:", __file__)
    print("CWD:", os.getcwd())

    failed_users = []

    try:
        print("=" * 60)
        print("PORTFOLIO JSON GENERATION STARTED")
        print("=" * 60)

        print(f"Base Directory  : {BASE_DIR}")
        print(f"Output Directory: {OUTPUT_DIR}")

        print("\nLoading data from Supabase...")
        rta_df, amfi_nav_df, isin_mapper_df = load_data_from_supabase()

        print(f"RTA rows loaded  : {len(rta_df):,}")
        print(f"NAV rows loaded  : {len(amfi_nav_df):,}")
        print(f"ISIN rows loaded : {len(isin_mapper_df):,}")

        print("\nLoading dashboard users...")
        user_configs = load_user_configs()
        print(f"Users loaded: {len(user_configs)}")

        print("\nPreparing effective NAV dataset...")
        effective_nav_df = get_effective_nav(amfi_nav_df, VALUATION_DATE)
        print(f"Effective NAV rows: {len(effective_nav_df):,}")

        print("\nBuilding portfolio analytics...")
        results = build_portfolio_analytics(
            rta_df,
            effective_nav_df,
            isin_mapper_df,
            VALUATION_DATE
        )
        print("Portfolio analytics completed.")

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        print("\nGenerating JSON files...")
        portal_result = generate_portfolio_json(
            results,
            user_configs,
            OUTPUT_DIR
        )

        print("portal_result type:", type(portal_result))
        print("portal_result value:", portal_result)

        if not isinstance(portal_result, dict):
            raise TypeError(f"portal_result is not dict: {type(portal_result)}")

        failed_users = portal_result.get("failed_users", [])

        print("\nUploading Summary to Supabase...")
        from admin_sync import sync_admin_portal
        sync_admin_portal(
            portal_result["admin_clients"],
            portal_result["dashboard_summary"]
        )

        print("\n" + "=" * 60)
        print("JSON GENERATION COMPLETED SUCCESSFULLY")
        print("=" * 60)

        print(f"Files written to:\n{OUTPUT_DIR}")

        print("\nGenerated Files:")
        for file in os.listdir(OUTPUT_DIR):
            print(f" - {file}")

        summary_path = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write("## Portfolio generation summary\n\n")
                f.write(f"- Commit: {os.getenv('GITHUB_SHA', 'unknown')}\n")
                f.write(f"- Branch: {os.getenv('GITHUB_REF_NAME', 'unknown')}\n")
                f.write(f"- Users processed: {len(user_configs)}\n")
                f.write(f"- Failed users: {len(failed_users)}\n\n")
                if failed_users:
                    f.write("### Failed users\n")
                    for item in failed_users:
                        f.write(f"- {item['login']} -> {item['file']} -> {item['error']}\n")

        return 0

    except Exception as e:
        print("\n" + "=" * 60)
        print("ERROR DURING JSON GENERATION")
        print("=" * 60)
        print(str(e))
        print("\nTRACEBACK:\n")
        traceback.print_exc()

        summary_path = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write("## Portfolio generation failed\n\n")
                f.write(f"- Error: `{str(e)}`\n")
                if failed_users:
                    f.write(f"- Failed users logged: {len(failed_users)}\n")
                    f.write("\n### Failed users\n")
                    for item in failed_users:
                        f.write(f"- {item['login']} -> {item['file']} -> {item['error']}\n")

        return 1

# =====================================================
# ENTRY POINT
# =====================================================

if __name__ == "__main__":
    sys.exit(main())
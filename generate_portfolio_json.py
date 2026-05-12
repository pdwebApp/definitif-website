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

    try:

        print("=" * 60)
        print("PORTFOLIO JSON GENERATION STARTED")
        print("=" * 60)

        print(f"Base Directory  : {BASE_DIR}")
        print(f"Output Directory: {OUTPUT_DIR}")

        # -------------------------------------------------
        # LOAD DATA
        # -------------------------------------------------

        print("\nLoading data from Supabase...")

        (
            rta_df,
            amfi_nav_df,
            isin_mapper_df
        ) = load_data_from_supabase()

        print(f"RTA rows loaded  : {len(rta_df):,}")
        print(f"NAV rows loaded  : {len(amfi_nav_df):,}")
        print(f"ISIN rows loaded : {len(isin_mapper_df):,}")

        # -------------------------------------------------
        # LOAD USERS
        # -------------------------------------------------

        print("\nLoading dashboard users...")

        USER_CONFIGS = load_user_configs()

        print(f"Users loaded: {len(USER_CONFIGS)}")

        # -------------------------------------------------
        # EFFECTIVE NAV
        # -------------------------------------------------

        print("\nPreparing effective NAV dataset...")

        effective_nav_df = get_effective_nav(
            amfi_nav_df,
            VALUATION_DATE
        )

        print(f"Effective NAV rows: {len(effective_nav_df):,}")

        # -------------------------------------------------
        # BUILD ANALYTICS
        # -------------------------------------------------

        print("\nBuilding portfolio analytics...")

        results = build_portfolio_analytics(
            rta_df,
            effective_nav_df,
            isin_mapper_df,
            VALUATION_DATE
        )

        print("Portfolio analytics completed.")

        # -------------------------------------------------
        # CREATE OUTPUT DIRECTORY
        # -------------------------------------------------

        os.makedirs(
            OUTPUT_DIR,
            exist_ok=True
        )

        # -------------------------------------------------
        # GENERATE JSON FILES
        # -------------------------------------------------

        print("\nGenerating JSON files...")

        generate_portfolio_json(
            results,
            USER_CONFIGS,
            OUTPUT_DIR,
        )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        print("\n" + "=" * 60)
        print("JSON GENERATION COMPLETED SUCCESSFULLY")
        print("=" * 60)

        print(f"Files written to:\n{OUTPUT_DIR}")

        # Optional debug
        print("\nGenerated Files:")

        for file in os.listdir(OUTPUT_DIR):
            print(f" - {file}")

    except Exception as e:

        print("\n" + "=" * 60)
        print("ERROR DURING JSON GENERATION")
        print("=" * 60)

        print(str(e))
        print("\nTRACEBACK:\n")

        traceback.print_exc()


# =====================================================
# ENTRY POINT
# =====================================================

if __name__ == "__main__":
    main()
from collections import deque
import pandas as pd
import numpy as np


# ---------------------------------
# classify BUY / SELL
# ---------------------------------
def _classify(row):

    code = str(row.get("txn_code", "")).upper()

    if code == "P":
        return "BUY"

    if code == "R":
        return "SELL"

    # fallback to old logic (optional safety)
    t = (row.get("transaction_type") or "").upper()

    if "PURCHASE" in t or "SIP" in t:
        return "BUY"

    if "REDEMPTION" in t or "SELL" in t:
        return "SELL"

    return "BUY"

def format_folio(x):
    if pd.isna(x):
        return ""
    if isinstance(x, (int, np.integer)):
        return str(x)
    if isinstance(x, float):
        return f"{x:.0f}"
    return str(x)


# ---------------------------------
# BUILD OPEN LOTS
# ---------------------------------
def build_transaction_view(rta_df, nav_df, isin_mapper):

    df = rta_df.copy()

    df["traddate"] = pd.to_datetime(df["traddate"])
    rta_df["folio_no"] = rta_df["folio_no"].astype(str)

    for col in ["units", "amount", "purprice"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # IMPORTANT
    df["direction"] = df.apply(_classify, axis=1)

    df = df.reset_index(drop=True)
    df["txn_id"] = df.index

    df = df.sort_values(
        ["pan", "folio_no", "isin", "traddate", "direction"],
        ascending=[True, True, True, True, False]
    )

    open_lots = []

    # ---------------------------------
    # FIFO ENGINE
    # ---------------------------------
    for (pan, folio, isin), grp in df.groupby(
        ["pan", "folio_no", "isin"]
    ):

        queue = deque()

        for _, row in grp.iterrows():

            units = abs(row["units"])

            nav = (
                row["purprice"]
                if row["purprice"] > 0
                else abs(row["amount"]) / units if units else 0
            )

            # ---------------- BUY ----------------
            if row["direction"] == "BUY":

                queue.append({
                    "pan": pan,
                    "folio_no": folio,
                    "transaction_type": row.get("transaction_type"),
                    "isin": isin,
                    "fund": None,
                    "purchase_date": row["traddate"],
                    "units_remaining": units,
                    "original_units": units,
                    "purchase_nav": nav
                })

            # ---------------- SELL ----------------
            else:

                redeem = units

                while redeem > 1e-6 and queue:

                    lot = queue[0]

                    used = min(lot["units_remaining"], redeem)

                    lot["units_remaining"] -= used
                    redeem -= used

                    if lot["units_remaining"] < 1e-6:
                        queue.popleft()

        # ONLY OPEN LOTS
        for lot in queue:
            if lot["units_remaining"] > 1e-6:
                open_lots.append(lot)

    lots = pd.DataFrame(open_lots)

    if lots.empty or "units_remaining" not in lots.columns:
        return pd.DataFrame()

    lots["units"] = lots["units_remaining"]

    # ---------------------------------
    # LATEST NAV ONLY
    # ---------------------------------
    nav_df["nav_date"] = pd.to_datetime(nav_df["nav_date"])

    latest_nav = (
        nav_df
        .sort_values("nav_date")
        .groupby("isin")
        .tail(1)[["isin", "nav"]]
        .rename(columns={"nav": "cmv"})
    )

    lots = lots.merge(latest_nav, on="isin", how="left")

    # ---------------------------------
    # STRATEGY
    # ---------------------------------
    lots = lots.merge(
        isin_mapper[
            [
                "isin",
                "global_broad_category_group",
                "fund_name"
            ]
        ],
        on="isin",
        how="left"
)

    lots = lots.rename(columns={
        "global_broad_category_group": "strategy",
        "fund_name": "fund"
    })

    # ---------------------------------
    # CALCULATIONS
    # ---------------------------------
    lots["cost"] = lots["units"] * lots["purchase_nav"]

    lots["investment"] = lots["cost"]

    lots["current_value"] = lots["units"] * lots["cmv"]

    lots["gain"] = lots["current_value"] - lots["cost"]

    lots["return_pct"] = (
        lots["gain"] / lots["cost"] * 100
    )

    # ---------------------------------
    # ROUNDING
    # ---------------------------------
    lots["units"] = lots["units"].round(3)
    lots["purchase_nav"] = lots["purchase_nav"].round(3)
    lots["cmv"] = lots["cmv"].round(3)

    lots["cost"] = lots["cost"].round(0)
    lots["investment"] = lots["investment"].round(0)
    lots["current_value"] = lots["current_value"].round(0)
    lots["gain"] = lots["gain"].round(0)
    lots["return_pct"] = lots["return_pct"].round(1)

    # ---------------------------------
    # SORT
    # ---------------------------------
    lots = lots.sort_values(
        [
            "pan",
            "strategy",
            "folio_no",
            "isin",
            "purchase_date"
        ]
    )
    
    lots["purchase_date"] = lots["purchase_date"].dt.strftime("%Y-%m-%d")

    # ---------------------------------
    # COLUMN ORDER (UNCHANGED + cmv)
    # ---------------------------------
    # ---------------------------------
    # RENAME FOR UI COMPATIBILITY
    # ---------------------------------
    lots = lots.rename(columns={
        "folio_no": "folio"
    })

    # prevent scientific notation for folio
    lots["folio"] = lots["folio"].apply(format_folio)

    lots = lots[
        [
            "pan",
            "strategy",
            "folio",
            "transaction_type",
            "isin",
            "fund",
            "purchase_date",
            "units",
            "purchase_nav",
            "cost",
            "cmv",
            "investment",
            "current_value",
            "gain",
            "return_pct"
        ]
    ]

    return lots
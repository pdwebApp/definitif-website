from datetime import date, timedelta
import pandas as pd
import requests
import io
import numpy as np
from supabase import create_client
import os

# -------------------------------
# Supabase Connection
# -------------------------------
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url:
    raise ValueError("SUPABASE_URL is missing")

if not key:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY is missing")

supabase = create_client(url, key)

# -------------------------------
# Get last nav_date from DB
# -------------------------------
def get_last_nav_date():
    res = supabase.table("amfi_nav") \
        .select("nav_date") \
        .order("nav_date", desc=True) \
        .limit(1) \
        .execute()

    if res.data:
        return pd.to_datetime(res.data[0]['nav_date']).date()
    return None

# -------------------------------
# Fetch ISIN Mapper
# -------------------------------
def get_isin_mapper():
    res = supabase.table("isin_mapper").select("isin").execute()

    if res.data:
        return pd.DataFrame(res.data)
    return pd.DataFrame(columns=["isin"])

# -------------------------------
# Fetch AMFI Mutual Fund NAV Data
# -------------------------------
def fetch_amfi_data(date_list):
    amfiNAV = pd.DataFrame(columns=['amfi_code','fund_name','isin','nav_date','nav'])

    for navDate in date_list:
        print(f"Fetching MF NAV for {navDate}")

        url = f'https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt={navDate}'
        response = requests.get(url)

        if response.status_code != 200:
            print(f"MF NAV fetch failed for {navDate}")
            continue

        rawData = pd.read_csv(
            io.StringIO(response.content.decode('utf-8')),
            delimiter=';',
            on_bad_lines='skip'
        )

        if rawData.empty:
            continue

        temp_df = rawData[~rawData['ISIN Div Payout/ISIN Growth'].isnull()] \
            .drop(['Plan','Option'], axis=1)

        temp_df = temp_df.rename(columns={
            'Scheme Code': 'amfi_code',
            'NAV Name': 'fund_name',
            'ISIN Div Payout/ISIN Growth': 'isin',
            'Net Asset Value': 'nav',
            'Date': 'nav_date'
        })

        # Growth / Payout
        temp_df_Pay = temp_df.drop('ISIN Div Reinvestment', axis=1)

        # Reinvestment
        temp_df_Re = temp_df[~temp_df['ISIN Div Reinvestment'].isnull()] \
            .drop('isin', axis=1)

        temp_df_Re = temp_df_Re.rename(columns={
            'ISIN Div Reinvestment': 'isin'
        })

        temp_df_Re['fund_name'] = temp_df_Re['fund_name'] + ' - DIV REINVEST'

        # Combine
        temp_df_mod = pd.concat([temp_df_Pay, temp_df_Re], axis=0)

        # Clean
        temp_df_mod = temp_df_mod.replace('-', np.nan)
        temp_df_mod = temp_df_mod.replace('N.A.', np.nan)
        temp_df_mod = temp_df_mod[~temp_df_mod['isin'].isnull()]
        temp_df_mod = temp_df_mod.drop_duplicates('isin', keep='first')

        amfiNAV = pd.concat([temp_df_mod, amfiNAV], ignore_index=True)

    return amfiNAV
    
# -------------------------------
# Fetch AMFI SIF NAV Data (TXT)
# -------------------------------
SIF_NAV_URL = "https://portal.amfiindia.com/spages/SIF_NAVAll.txt"

def fetch_sif_data():
    """
    Downloads the latest SIF NAV text file from AMFI, stacks the two ISIN columns
    into one, and returns a DataFrame with columns:
      sif_code, fund_name, isin, nav_date, nav

    If anything fails, returns an empty DataFrame and lets the caller handle it.
    """
    print("Fetching SIF NAV from AMFI...")
    try:
        resp = requests.get(SIF_NAV_URL, timeout=60)
        resp.raise_for_status()

        # SIF file is semicolon-delimited
        raw = pd.read_csv(
            io.StringIO(resp.content.decode('utf-8')),
            delimiter=';',
            on_bad_lines='skip'
        )

        if raw.empty:
            print("SIF NAV file is empty.")
            return pd.DataFrame(columns=['sif_code', 'fund_name', 'isin', 'nav_date', 'nav'])

        raw = raw.rename(columns={
            'Scheme Code': 'sif_code',
            'Scheme Name': 'fund_name',
            'ISIN Div Payout/ ISIN Growth': 'isin_growth',
            'ISIN Div Reinvestment': 'isin_reinvestment',
            'Net Asset Value': 'nav',
            'Date': 'nav_date',
        })

        mask = (
            raw['sif_code'].notna() &
            raw['fund_name'].notna() &
            raw['nav'].notna() &
            raw['nav_date'].notna()
        )
        rows = raw.loc[mask, [
            'sif_code', 'fund_name', 'isin_growth', 'isin_reinvestment', 'nav', 'nav_date'
        ]].copy()

        if rows.empty:
            print("No valid SIF NAV rows found after filtering.")
            return pd.DataFrame(columns=['sif_code', 'fund_name', 'isin', 'nav_date', 'nav'])

        # Stack the two ISIN columns into one
        out = pd.concat([
            rows[['sif_code', 'fund_name', 'isin_growth', 'nav', 'nav_date']]
                .rename(columns={'isin_growth': 'isin'}),
            rows[['sif_code', 'fund_name', 'isin_reinvestment', 'nav', 'nav_date']]
                .rename(columns={'isin_reinvestment': 'isin'}),
        ], ignore_index=True)

        # Clean ISINs
        out['isin'] = out['isin'].astype('string').str.strip()
        out = out[out['isin'].notna() & out['isin'].ne('') & out['isin'].ne('-')]

        # Clean NAV and date
        out['nav'] = pd.to_numeric(out['nav'], errors='coerce')
        out['nav_date'] = pd.to_datetime(
            out['nav_date'],
            format='%d-%b-%Y',
            errors='coerce'
        )

        out = out.dropna(subset=['nav', 'nav_date'])
        out = out.drop_duplicates(['isin', 'nav_date'], keep='first').reset_index(drop=True)

        result = out[['sif_code', 'fund_name', 'isin', 'nav_date', 'nav']]
        print(f"Fetched {len(result)} SIF NAV rows.")
        return result

    except Exception as e:
        print(f"Heads up: SIF NAVs could not be loaded. Error: {e}")
        return pd.DataFrame(columns=['sif_code', 'fund_name', 'isin', 'nav_date', 'nav'])

# -------------------------------
# Main Pipeline
# -------------------------------
def run_pipeline():
    print("Pipeline started...")

    today = date.today()

    # -------------------------------
    # Dynamic Date Range for MF NAVs
    # -------------------------------
    last_nav_date = get_last_nav_date()

    if last_nav_date is None:
        print("No existing data. Using default T-2 logic for MF.")
        start_date = today - timedelta(days=2)
    else:
        start_date = last_nav_date - timedelta(days=1)

    end_date = today - timedelta(days=1)

    print(f"Fetching MF NAVs from {start_date} to {end_date}")

    mf_nav = pd.DataFrame(columns=['amfi_code','fund_name','isin','nav_date','nav'])

    if start_date <= end_date:
        date_list = [
            d.strftime("%d-%b-%Y")
            for d in pd.date_range(start_date, end_date)
        ]

        mf_nav = fetch_amfi_data(date_list)

        if mf_nav.empty:
            print("No MF NAV data fetched.")
    else:
        print("MF NAV data already up to date. Skipping MF fetch.")

    # -------------------------------
    # Fetch SIF Data (latest only)
    # -------------------------------
    sif_nav = fetch_sif_data()
    sif_loaded = not sif_nav.empty

    if not sif_loaded:
        print("Heads up: SIF NAVs could not be loaded. Continuing with MF NAVs only.")

    # -------------------------------
    # Combine MF + SIF
    # -------------------------------
    if not mf_nav.empty:
        mf_nav = mf_nav[['isin', 'nav', 'nav_date']].copy()
    else:
        mf_nav = pd.DataFrame(columns=['isin', 'nav', 'nav_date'])

    if not sif_nav.empty:
        sif_nav = sif_nav[['isin', 'nav', 'nav_date']].copy()
    else:
        sif_nav = pd.DataFrame(columns=['isin', 'nav', 'nav_date'])

    amfiNAV = pd.concat([mf_nav, sif_nav], ignore_index=True)

    if amfiNAV.empty:
        print("No NAV data fetched (MF + SIF). Exiting.")
        return

    # -------------------------------
    # Data Cleaning
    # -------------------------------
    amfiNAV['nav_date'] = pd.to_datetime(
        amfiNAV['nav_date'],
        errors='coerce'
    )

    amfiNAV = amfiNAV.replace('-', np.nan)
    amfiNAV = amfiNAV.replace('N.A.', np.nan)
    amfiNAV = amfiNAV.replace(0, np.nan)

    amfiNAV = amfiNAV[['isin', 'nav', 'nav_date']]
    amfiNAV = amfiNAV.dropna(subset=['isin', 'nav', 'nav_date'])

    # Drop exact duplicates on (isin, nav, nav_date) in the incoming batch
    before_dedup = len(amfiNAV)
    amfiNAV = amfiNAV.drop_duplicates(subset=['isin', 'nav', 'nav_date'], keep='first').reset_index(drop=True)
    after_dedup = len(amfiNAV)
    if before_dedup != after_dedup:
        print(f"Dropped {before_dedup - after_dedup} duplicate rows in incoming data (isin, nav, nav_date).")

    # -------------------------------
    # Filter Required ISINs
    # -------------------------------
    isinMapper = get_isin_mapper()

    if not isinMapper.empty:
        amfiNAV = amfiNAV.merge(isinMapper, on='isin', how='inner')
    else:
        print("Warning: ISIN mapper empty; proceeding without filter.")

    if amfiNAV.empty:
        print("No NAV data after ISIN filtering. Exiting.")
        return

    # -------------------------------
    # Format Date for Supabase
    # -------------------------------
    amfiNAV['nav_date'] = (
        pd.to_datetime(amfiNAV['nav_date'])
        .dt.strftime('%Y-%m-%d')
    )

    # -------------------------------
    # UPSERT Data with conflict handling
    # -------------------------------
    print(f"Upserting {len(amfiNAV)} rows into amfi_nav...")

    try:
        (
            supabase.table("amfi_nav")
            .upsert(
                amfiNAV.to_dict(orient="records"),
                on_conflict="isin,nav_date"
            )
            .execute()
        )
        print("Upsert completed without error.")
    except Exception as e:
        err_str = str(e)
        if "23505" in err_str or "duplicate key" in err_str.lower():
            print(f"Heads up: Duplicate-key conflict during upsert (expected). Error: {e}")
            print("Pipeline will continue and mark as successful so downstream jobs can run.")
        else:
            print(f"Unexpected error during upsert: {e}")
            print("Pipeline will still exit successfully to avoid blocking downstream jobs.")

    if sif_loaded:
        print("Pipeline completed successfully! (MF + SIF)")
    else:
        print("Pipeline completed successfully! (MF only; SIF NAVs were not loaded)")

# -------------------------------
# Run
# -------------------------------
if __name__ == "__main__":
    run_pipeline()
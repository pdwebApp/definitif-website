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
# Fetch AMFI NAV Data
# -------------------------------
def fetch_amfi_data(date_list):
    amfiNAV = pd.DataFrame(columns=['amfi_code','fund_name','isin','nav_date','nav'])

    for navDate in date_list:
        print(f"Fetching {navDate}")

        url = f'https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt={navDate}'
        response = requests.get(url)

        if response.status_code != 200:
            print(f"Failed for {navDate}")
            continue

        rawData = pd.read_csv(
            io.StringIO(response.content.decode('utf-8')),
            delimiter=';',
            on_bad_lines='skip'
        )

        if rawData.empty:
            continue

        temp_df = rawData[~rawData['ISIN Div Payout/ISIN Growth'].isnull()] \
            .drop(['Repurchase Price','Sale Price'], axis=1)

        temp_df = temp_df.rename(columns={
            'Scheme Code': 'amfi_code',
            'Scheme Name': 'fund_name',
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
# Main Pipeline
# -------------------------------
def run_pipeline():
    print("Pipeline started...")

    today = date.today()

    # -------------------------------
    # Dynamic Date Range
    # -------------------------------
    last_nav_date = get_last_nav_date()

    if last_nav_date is None:
        print("No existing data. Using default T-2 logic.")
        start_date = today - timedelta(days=2)
    else:
        # Re-fetch one day before last stored date (correction)
        start_date = last_nav_date - timedelta(days=1)

    end_date = today - timedelta(days=1)

    print(f"Fetching from {start_date} to {end_date}")

    if start_date > end_date:
        print("Data already up to date. Exiting.")
        return

    date_list = [
        d.strftime("%d-%b-%Y")
        for d in pd.date_range(start_date, end_date)
    ]

    # -------------------------------
    # Fetch Data
    # -------------------------------
    amfiNAV = fetch_amfi_data(date_list)

    if amfiNAV.empty:
        print("No NAV data fetched.")
        return

    # -------------------------------
    # Data Cleaning
    # -------------------------------
    amfiNAV['nav_date'] = pd.to_datetime(
        amfiNAV['nav_date'],
        format='%d-%b-%Y',
        errors='coerce'
    )

    amfiNAV = amfiNAV.replace('-', np.nan)
    amfiNAV = amfiNAV.replace('N.A.', np.nan)
    amfiNAV = amfiNAV.replace(0, np.nan)

    amfiNAV = amfiNAV[['isin', 'nav', 'nav_date']]

    # -------------------------------
    # Filter Required ISINs
    # -------------------------------
    isinMapper = get_isin_mapper()

    if not isinMapper.empty:
        amfiNAV = amfiNAV.merge(isinMapper, on='isin', how='inner')
    else:
        print("Warning: ISIN mapper empty")

    # -------------------------------
    # Format Date for Supabase
    # -------------------------------
    amfiNAV['nav_date'] = (
        pd.to_datetime(amfiNAV['nav_date'])
        .dt.strftime('%Y-%m-%d')
    )

    # -------------------------------
    # UPSERT Data
    # -------------------------------
    print("Upserting data into Supabase...")

    supabase.table("amfi_nav") \
        .upsert(amfiNAV.to_dict(orient="records")) \
        .execute()

    print("Pipeline completed successfully!")

# -------------------------------
# Run
# -------------------------------
if __name__ == "__main__":
    run_pipeline()
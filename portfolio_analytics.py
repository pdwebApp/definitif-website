#!/usr/bin/env python3

import os
import json
import warnings
from datetime import date, timedelta
from collections import deque

import numpy as np
import pandas as pd
from scipy.optimize import brentq

warnings.filterwarnings("ignore")

BUY_CODES = {
    'P','PI','SI','SIP','SWI','SWITCH IN','NFO','PUR',
    'PURCHASE','BUYIN','BUY','SWITCH_IN','ISIP','PSIP'
}
SELL_CODES = {
    'R','RED','REDEEM','REDEMPTION','SWO','SWITCH OUT',
    'SWITCH_OUT','SWPOUT','SWP','FUL','FULL RED','SELL'
}


def load_data_from_csv(data_folder="."):
    rta_df = pd.read_csv(os.path.join(data_folder, "trData.csv"), low_memory=False)
    amfi_nav_df = pd.read_csv(os.path.join(data_folder, "nav_data.csv"), low_memory=False)
    isin_mapper_df = pd.read_csv(os.path.join(data_folder, "isinMapper.csv"), low_memory=False)
    return rta_df, amfi_nav_df, isin_mapper_df


def fetch_data_sqlalchemy(db_url: str):
    from sqlalchemy import create_engine
    engine = create_engine(db_url, connect_args={"sslmode": "require"})
    with engine.connect() as conn:
        rta_df = pd.read_sql("SELECT * FROM rta_transactions", conn)
        amfi_nav_df = pd.read_sql("SELECT * FROM amfi_nav", conn)
        isin_mapper_df = pd.read_sql("SELECT * FROM isin_mapper", conn)
    return rta_df, amfi_nav_df, isin_mapper_df


def fetch_data_supabase_py(supabase_url: str, supabase_key: str, page_size: int = 1000):
    from supabase import create_client
    client = create_client(supabase_url, supabase_key)

    import time

    def fetch_all(table_name, page_size=1000, retries=3):
        offset = 0
        all_rows = []

        for attempt in range(retries):
            try:
                while True:
                    resp = (
                        client.table(table_name)
                        .select("*")
                        .range(offset, offset + page_size - 1)
                        .execute()
                    )

                    data = resp.data
                    if not data:
                        break

                    all_rows.extend(data)

                    if len(data) < page_size:
                        break

                    offset += page_size

                return pd.DataFrame(all_rows)

            except Exception as e:
                print(f"{table_name} fetch failed, retry {attempt+1}/{retries}")
                time.sleep(2)

        raise RuntimeError(f"Failed fetching {table_name}")

    rta_df = fetch_all("rta_transactions")
    # get only required ISINs first
    # isin_list = rta_df["isin"].dropna().unique().tolist()

    # amfi_nav_df = (
    #     client.table("amfi_nav")
    #     .select("*")
    #     .in_("isin", isin_list)
    #     .execute()
    # amfi_nav_df = pd.DataFrame(amfi_nav_df.data)

    amfi_nav_df = fetch_all("amfi_nav")
    isin_mapper_df = fetch_all("isin_mapper")
    # Clean Morningstar category
    isin_mapper_df["morningstar_category"] = (
        isin_mapper_df["morningstar_category"]
        .str.replace(r"^India Fund\s*", "", regex=True)
    )

    # Build consistent fund display name
    # normalize purchase_mode
    pm = isin_mapper_df["purchase_mode"].fillna("").str.strip()

    pm = np.where(
        pm.str.lower() == "regular", "",
        np.where(
            pm.str.lower() == "direct", "Dir",
            pm
        )
    )

    # normalize option
    opt = isin_mapper_df["option"].fillna("").str.strip()

    opt = np.where(
        opt.str.lower() == "growth",
        "G",
        opt
    )

    # Build consistent fund display name
    isin_mapper_df["fund_display"] = (
        isin_mapper_df["fund_name"].fillna("")
        + " - "
        + pd.Series(pm)
        + " - "
        + pd.Series(opt)
    )

    # remove trailing separators
    isin_mapper_df["fund_display"] = (
        isin_mapper_df["fund_display"]
        .str.replace(r"\s+\-\s+$", "", regex=True)
        .str.replace(r"\-\s+\-", "-", regex=True)
        .str.replace(r"\-\s*\-", "-", regex=True)
        .str.strip()
    )
    return rta_df, amfi_nav_df, isin_mapper_df


def load_data_from_supabase():
    db_url = os.environ.get("SUPABASE_DB_URL")
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if db_url:
        return fetch_data_sqlalchemy(db_url)

    if supabase_url and supabase_key:
        return fetch_data_supabase_py(supabase_url, supabase_key)

    raise ValueError(
        "Missing Supabase credentials. Set SUPABASE_DB_URL or SUPABASE_URL and SUPABASE_KEY."
    )

def get_financial_year(d):
            if pd.isna(d):
                return None
            d = pd.to_datetime(d)
            if d.month > 3:
                return f"FY{str(d.year+1)[-2:]}"
            else:
                return f"FY{str(d.year)[-2:]}"
            
def _classify(row):
    c = str(row.get('txn_code', '')).strip().upper()
    t = str(row.get('transaction_type', '')).strip().upper()
    if c in BUY_CODES or t in BUY_CODES:
        return 'BUY'
    if c in SELL_CODES or t in SELL_CODES:
        return 'SELL'
    return 'BUY' if row.get('units', 0) >= 0 else 'SELL'


def run_fifo(txn_df: pd.DataFrame):
    df = txn_df.copy()
    df['traddate'] = pd.to_datetime(df['traddate'])
    for col in ('units', 'amount', 'purprice'):
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['direction'] = df.apply(_classify, axis=1)
    df = df.sort_values(
        ['pan', 'folio_no', 'isin', 'traddate', 'direction'],
        ascending=[True, True, True, True, False]
    ).reset_index(drop=True)

    open_lots, realized = [], []

    for (pan, folio, isin), grp in df.groupby(['pan', 'folio_no', 'isin'], sort=False):
        queue = deque()

        for _, row in grp.iterrows():
            units = abs(float(row['units']))
            nav = float(row['purprice']) if float(row['purprice']) > 0 else (
                abs(float(row['amount'])) / units if units > 0 else 0
            )
            amt = abs(float(row['amount']))

            if row['direction'] == 'BUY':
                queue.append({
                    'pan': pan,
                    'folio_no': folio,
                    'isin': isin,
                    'buy_date': row['traddate'],
                    'buy_nav': nav,
                    'buy_amount': amt,
                    'units_remaining': units,
                    'original_units': units,
                    'buy_txn_id': row['txn_id'],   # ADD THIS LINE
                })
            else:
                to_sell = units
                while to_sell > 1e-6 and queue:
                    lot = queue[0]
                    matched = min(lot['units_remaining'], to_sell)

                    realized.append({
                                    'pan': pan,
                                    'folio_no': folio,
                                    'isin': isin,
                                    'buy_date': lot['buy_date'],
                                    'sell_date': row['traddate'],
                                    'buy_txn_id': lot['buy_txn_id'],
                                    'sell_txn_id': row['txn_id'],   # ADD THIS
                                    'holding_days': (row['traddate'] - lot['buy_date']).days,
                                    'units': matched,
                                    'buy_nav': lot['buy_nav'],
                                    'sell_nav': nav,
                                    'cost': matched * lot['buy_nav'],
                                    'proceeds': matched * nav,
                                    'gain_loss': matched * (nav - lot['buy_nav']),
                                })

                    lot['units_remaining'] -= matched
                    to_sell -= matched

                    if lot['units_remaining'] < 1e-6:
                        queue.popleft()

        for lot in queue:
            if lot['units_remaining'] > 1e-6:
                open_lots.append(lot)

    return pd.DataFrame(open_lots), pd.DataFrame(realized)


def xirr(cashflows: list, max_irr=0.6):
    """
    max_irr = 0.6  → 60%
    """

    if len(cashflows) < 2:
        return None
    cashflows = sorted(cashflows, key=lambda x: x[0])
    dates, amounts = zip(*cashflows)
    # must have both signs
    if not (any(a < 0 for a in amounts) and any(a > 0 for a in amounts)):
        return None
    t0 = dates[0]
    days = [(d - t0).days for d in dates]
    def npv(r):
        return sum(cf / (1 + r) ** (d / 365.0) for cf, d in zip(amounts, days))
    try:
        irr = brentq(npv, -0.9999, max_irr, maxiter=500)
        # numerical guardrails
        if irr is None:
            return None
        # reject absurd IRR
        if irr > max_irr:
            return None
        # reject ultra short holding crazy IRR
        if max(days) < 30 and irr > 0.5:
            return None
        return irr
    except Exception:
        return None


def classify_gain(category: str, holding_days: int) -> str:
    cat = str(category).strip().lower()
    if any(x in cat for x in ['fixed income', 'capital preservation', 'money market', 'bond']):
        return 'STCG'
    if any(x in cat for x in ['equity', 'arbitrage', 'allocation']):
        return 'LTCG' if holding_days >= 366 else 'STCG'
    return 'LTCG' if holding_days >= 731 else 'STCG'

def get_effective_nav(amfi_nav_df, valuation_date):
    # ensure date type
    amfi_nav_df["nav_date"] = pd.to_datetime(amfi_nav_df["nav_date"]).dt.date
    # get nav for valuation date
    nav_today = amfi_nav_df[amfi_nav_df["nav_date"] == valuation_date]
    # fallback: last nav per isin
    last_nav = (
        amfi_nav_df
        .sort_values("nav_date")
        .groupby("isin")
        .tail(1)
    )
    # merge logic
    final_nav = pd.concat([nav_today, last_nav])
    final_nav = final_nav.drop_duplicates("isin", keep="first")
    return final_nav

def build_portfolio_analytics(rta_df, amfi_nav_df, isin_mapper_df, valuation_date=None):
    if valuation_date is None:
        valuation_date = date.today() - timedelta(days=1)

    val_ts = pd.Timestamp(valuation_date)

    if 'trxnstat' in rta_df.columns:
        rta_df = rta_df[rta_df['trxnstat'].isin(['Processed', 'Y', 'y'])].copy()

    isin_meta = isin_mapper_df[
        ['isin', 'global_broad_category_group', 'morningstar_category',
         'fund_display', 'asset_alloc_equity', 'asset_alloc_bond', 'asset_alloc_cash',
       'asset_alloc_other', 'large_cap', 'mid_cap', 'small_cap', 'micro_cap']
    ].drop_duplicates('isin')

    cat_map = isin_meta[['isin', 'global_broad_category_group']].drop_duplicates('isin')

    rta_enr = rta_df.merge(cat_map, on='isin', how='left')
    # standardize investor name
    rta_enr["inv_name"] = (
        rta_enr["inv_name"]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    # take first name per PAN and title case
    name_map = (
        rta_enr
        .dropna(subset=["pan"])
        .groupby("pan", as_index=False)
        .first()[["pan","inv_name"]]
    )

    name_map["inv_name"] = name_map["inv_name"].str.title()

    # merge back
    rta_enr = rta_enr.drop(columns=["inv_name"], errors="ignore") \
                    .merge(name_map, on="pan", how="left")
    
    for col in ('units', 'amount', 'purprice'):
        rta_enr[col] = pd.to_numeric(rta_enr[col], errors='coerce').fillna(0)
    rta_enr['traddate'] = pd.to_datetime(rta_enr['traddate'])

    def cf_sign(row):
        c = str(row.get('txn_code', '')).strip().upper()
        t = str(row.get('transaction_type', '')).strip().upper()
        if c in BUY_CODES or t in BUY_CODES:
            return -1
        if c in SELL_CODES or t in SELL_CODES:
            return 1
        return -1 if row.get('units', 0) >= 0 else 1

    rta_enr['cf_sign'] = rta_enr.apply(cf_sign, axis=1)
    rta_enr['cashflow'] = rta_enr['cf_sign'] * abs(rta_enr['amount'])

    rta_enr = rta_enr.reset_index(drop=True)
    rta_enr["txn_id"] = rta_enr.index

    holdings_df, realized_df = run_fifo(rta_enr)

    # enrich realized data
    realized_df = realized_df.merge(
        rta_enr[
            ['txn_id','transaction_type','txn_code','purchase_mode','option']
        ],
        left_on="sell_txn_id",
        right_on="txn_id",
        how="left"
    )

    # Add gain % to profit booking
    realized_df['gain_loss_pct'] = np.where(
    realized_df['cost'] != 0,
    realized_df['gain_loss'] / realized_df['cost'] * 100,
    None
    )

    # classify STCG / LTCG
    realized_df['gain_type'] = realized_df.apply(
        lambda r: classify_gain(
            r.get('global_broad_category_group',''),
            r['holding_days']
        ),
        axis=1
)

    if holdings_df.empty:
        return {
            'holdings': holdings_df,
            'realized': realized_df,
            'performance_all': {},
            'profit_booking': pd.DataFrame(),
            'investor_summary': pd.DataFrame(),
            'rta_enr': rta_enr,
            'isin_meta': isin_meta,
            'val_ts': val_ts,
        }

    amfi_nav_df['nav_date'] = pd.to_datetime(amfi_nav_df['nav_date'])
    amfi_nav_df['nav'] = pd.to_numeric(amfi_nav_df['nav'], errors='coerce')

    latest_nav = (
        amfi_nav_df[amfi_nav_df['nav_date'] <= val_ts]
        .sort_values('nav_date')
        .groupby('isin', as_index=False)
        .last()[['isin', 'nav', 'nav_date']]
        .rename(columns={'nav': 'current_nav', 'nav_date': 'nav_as_of'})
    )

    nav_meta = {
    "requested_date": val_ts.strftime("%Y-%m-%d"),
    "max_nav_date": latest_nav["nav_as_of"].max().strftime("%Y-%m-%d")
}

    drop_existing = [c for c in holdings_df.columns if c in isin_meta.columns and c != 'isin']
    holdings_df = holdings_df.drop(columns=drop_existing, errors='ignore')
    holdings_df = holdings_df.merge(latest_nav, on='isin', how='left').merge(isin_meta, on='isin', how='left')

    holdings_df['current_value'] = holdings_df['units_remaining'] * holdings_df['current_nav']
    holdings_df['cost_value'] = holdings_df['units_remaining'] * holdings_df['buy_nav']
    holdings_df['unrealised_gl'] = holdings_df['current_value'] - holdings_df['cost_value']
    holdings_df['unrealised_gl_pct'] = np.where(
        holdings_df['cost_value'] != 0,
        holdings_df['unrealised_gl'] / holdings_df['cost_value'] * 100,
        np.nan
    )
    holdings_df['holding_days'] = (val_ts - holdings_df['buy_date']).dt.days

    def terminal_cf(key_dict):
        mask = pd.Series([True] * len(holdings_df))
        for k, v in key_dict.items():
            if k in holdings_df.columns:
                mask &= (holdings_df[k] == v)
        cv = holdings_df[mask]['current_value'].sum()
        return [(val_ts, cv)] if cv > 0 else []

    def compute_perf(group_keys):
        rows = []
        for keys, grp in rta_enr.groupby(group_keys):
            kd = dict(zip(group_keys, keys if isinstance(keys, tuple) else [keys]))
            cfs = list(zip(grp['traddate'], grp['cashflow'])) + terminal_cf(kd)
            xi = xirr(cfs)

            mask = pd.Series([True] * len(holdings_df))
            for k, v in kd.items():
                if k in holdings_df.columns:
                    mask &= (holdings_df[k] == v)

            h = holdings_df[mask]
            tc = h['cost_value'].sum()
            cv = h['current_value'].sum()
            ug = h['unrealised_gl'].sum()

            rows.append({
                **kd,
                'invested': round(tc, 2),
                'current_value': round(cv, 2),
                'unrealised_gl': round(ug, 2),
                'abs_return_pct': round(ug / tc * 100, 2) if tc else None,
                'xirr_existing': round(xi * 100, 2) if xi else None,
                'xirr_entire': round(xi * 100, 2) if xi else None
            })
        return pd.DataFrame(rows)

    perf_all = {
        'pan': compute_perf(['pan']),
        'folio': compute_perf(['pan', 'folio_no']),
        'isin': compute_perf(['pan', 'folio_no', 'isin']),
        'category': compute_perf(['pan','global_broad_category_group']),
    }

    if not realized_df.empty:
        drop_r = [c for c in realized_df.columns if c in isin_meta.columns and c != 'isin']
        realized_df = realized_df.drop(columns=drop_r, errors='ignore')
        realized_df = realized_df.merge(isin_meta, on='isin', how='left')
        realized_df['gain_type'] = realized_df.apply(
            lambda r: classify_gain(r.get('global_broad_category_group', ''), r['holding_days']),
            axis=1
        )

        pb_frames = []
        for lvl in [['pan'], ['pan', 'folio_no'], ['pan', 'folio_no', 'isin'],
                    ['pan', 'folio_no', 'isin', 'global_broad_category_group']]:
            agg = realized_df.groupby(lvl + ['gain_type'], as_index=False).agg(
                total_units=('units', 'sum'),
                total_cost=('cost', 'sum'),
                total_proceeds=('proceeds', 'sum'),
                total_gain_loss=('gain_loss', 'sum')
            )
            agg['level'] = ' > '.join(lvl)
            pb_frames.append(agg)

        profit_booking_df = pd.concat(pb_frames, ignore_index=True)
        profit_booking_df['gain_loss_pct'] = np.where(
            profit_booking_df['total_cost'] != 0,
            profit_booking_df['total_gain_loss'] / profit_booking_df['total_cost'] * 100,
            np.nan
        )
        profit_booking_df = profit_booking_df.round(2)
    else:
        profit_booking_df = pd.DataFrame()

    inv_map = (
        rta_enr[['pan', 'inv_name']].drop_duplicates('pan')
        if 'inv_name' in rta_enr.columns else pd.DataFrame(columns=['pan', 'inv_name'])
    )

    total_inv = (
        rta_enr[rta_enr['cf_sign'] == -1]
        .groupby('pan')['amount']
        .apply(lambda x: abs(x).sum())
        .reset_index()
        .rename(columns={'amount': 'total_invested_ever'})
    )

    total_red = (
        rta_enr[rta_enr['cf_sign'] == 1]
        .groupby('pan')['amount']
        .apply(lambda x: abs(x).sum())
        .reset_index()
        .rename(columns={'amount': 'total_redeemed'})
    )

    real_pan = (
        realized_df.groupby('pan').agg(realized_gl=('gain_loss', 'sum')).reset_index().round(2)
        if not realized_df.empty else pd.DataFrame(columns=['pan', 'realized_gl'])
    )

    cat_exp = (
        holdings_df.groupby(['pan', 'global_broad_category_group'])['current_value']
        .sum().unstack(fill_value=0).reset_index()
    )
    cat_exp.columns = ['pan'] + [f'exp_{c}' for c in cat_exp.columns[1:]]

    inv_summary = (
        perf_all['pan']
        .merge(inv_map, on='pan', how='left')
        .merge(total_inv, on='pan', how='left')
        .merge(total_red, on='pan', how='left')
        .merge(real_pan, on='pan', how='left')
        .merge(cat_exp, on='pan', how='left')
    ).round(2)

    return {
        'holdings': holdings_df,
        'realized': realized_df,
        'performance_all': perf_all,
        'profit_booking': profit_booking_df,
        'investor_summary': inv_summary,
        'rta_enr': rta_enr,
        'isin_meta': isin_meta,
        'val_ts': val_ts,
        'nav_meta': nav_meta,
    }


def df_to_records(df):
    if df is None or df.empty:
        return []

    df2 = df.copy()
    for col in df2.select_dtypes(include=['datetime64[ns]', 'datetime64[ns, UTC]']).columns:
        df2[col] = df2[col].dt.strftime('%Y-%m-%d')

    df2 = df2.replace([np.inf, -np.inf], np.nan)
    records = df2.to_dict(orient='records')

    return [
        {k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in r.items()}
        for r in records
    ]

def build_fund_performance_view(
    rta_user: pd.DataFrame,
    h: pd.DataFrame,
    val_ts: pd.Timestamp
    ) -> pd.DataFrame:
    """
    Build fund-level performance with separate XIRR for:
      1. existing portfolio (open lots only)
      2. entire fund history (all cash flows for that fund)
    """

    if h is None or h.empty:
        return pd.DataFrame(columns=[
            'pan',
            'isin',
            'fund_display',
            'global_broad_category_group',
            'morningstar_category',
            'invested',
            'current_value',
            'unrealised_gl',
            'abs_return_pct',
            'xirr_existing',
            'xirr_entire'
        ])

    rows = []

    for (pan, isin), h_isin in h.groupby(['pan', 'isin']):

        tx_isin = rta_user[
            (rta_user['pan'] == pan) &
            (rta_user['isin'] == isin)
        ].copy()

        # -----------------------------
        # FUND DISPLAY
        # -----------------------------
        fund_display = None
        if 'fund_display' in h_isin.columns:
            vals = h_isin['fund_display'].dropna().unique()
            if len(vals) > 0:
                fund_display = vals[0]

        if not fund_display:
            fund_display = isin

        # -----------------------------
        # STRATEGY
        # -----------------------------
        category = (
            h_isin['global_broad_category_group'].dropna().iloc[0]
            if 'global_broad_category_group' in h_isin.columns
            and not h_isin['global_broad_category_group'].dropna().empty
            else None
        )

        # -----------------------------
        # SUB CATEGORY
        # -----------------------------
        subcategory = (
            h_isin['morningstar_category'].dropna().iloc[0]
            if 'morningstar_category' in h_isin.columns
            and not h_isin['morningstar_category'].dropna().empty
            else None
        )

        # -----------------------------
        # VALUES
        # -----------------------------
        invested = h_isin['cost_value'].sum()
        current_value = h_isin['current_value'].sum()
        unrealised_gl = h_isin['unrealised_gl'].sum()

        abs_return_pct = (
            round(unrealised_gl / invested * 100, 2)
            if invested else None
        )

        # -----------------------------
        # XIRR
        # -----------------------------
        xi_entire = compute_xirr_entire(
            tx_isin,
            current_value,
            val_ts
        )

        xi_existing = compute_xirr_existing(
            h_isin,
            val_ts
        )

        rows.append({
            'pan': pan,
            'isin': isin,
            'fund_display': fund_display,
            'global_broad_category_group': category,
            'morningstar_category': subcategory,
            'invested': round(invested, 2),
            'current_value': round(current_value, 2),
            'unrealised_gl': round(unrealised_gl, 2),
            'abs_return_pct': abs_return_pct,
            'xirr_existing':
                round(xi_existing * 100, 2)
                if xi_existing is not None else None,
            'xirr_entire':
                round(xi_entire * 100, 2)
                if xi_entire is not None else None,
        })

    out = pd.DataFrame(rows)

    if not out.empty:
        out = out.sort_values(
            ['current_value', 'fund_display'],
            ascending=[False, True]
        ).reset_index(drop=True)

    return out

def compute_xirr_entire(rta_subset, current_value, val_ts):
    if rta_subset.empty and current_value <= 0:
        return None
    cfs = list(zip(rta_subset['traddate'], rta_subset['cashflow']))
    if current_value > 0:
        cfs.append((val_ts, current_value))
    if len(cfs) < 2:
        return None
    return xirr(cfs)

def compute_xirr_existing(holdings_subset, val_ts):

    if holdings_subset.empty:
        return None
    cfs = []
    # each open lot = investment
    for _, r in holdings_subset.iterrows():
        cost = r["cost_value"]
        dt   = r["buy_date"]

        if cost > 0:
            cfs.append((dt, -cost))

    # terminal value
    total_current = holdings_subset["current_value"].sum()
    if total_current > 0:
        cfs.append((val_ts, total_current))
    if len(cfs) < 2:
        return None
    return xirr(cfs)

def build_user_json(results, pans, label, user_type='individual'):
    nav_meta = results.get("nav_meta", {})
    holdings_df = results['holdings']
    # perf_all = results['performance_all']
    profit_booking_df = results['profit_booking']
    rta_enr = results['rta_enr']
    isin_meta = results['isin_meta']
    val_ts = results.get('val_ts', pd.Timestamp(date.today()))

    # ensure pans is list
    if not isinstance(pans, (list, tuple, set)):
        pans = [pans] if pans else []
    h = holdings_df[holdings_df['pan'].isin(pans)].copy()

    meta_cols = [c for c in isin_meta.columns if c != "isin"]
    meta_cols.insert(0, "isin")
    drop_h = [c for c in h.columns if c in meta_cols and c != 'isin']
    h = h.drop(columns=drop_h, errors='ignore')
    h = h.merge(isin_meta[meta_cols].drop_duplicates('isin'), on='isin', how='left')

    total_cv = h['current_value'].sum()
    total_cost = h['cost_value'].sum()
    total_ugl = h['unrealised_gl'].sum()
    abs_ret = round(total_ugl / total_cost * 100, 2) if total_cost else 0

    realized = results["realized"]
    realized_user = realized[realized["pan"].isin(pans)]

    total_realized = realized_user["gain_loss"].sum() if not realized_user.empty else 0

    rta_user = rta_enr[rta_enr['pan'].isin(pans)].copy()

    # XIRR - since inception
    xi_all = compute_xirr_entire(rta_user,total_cv,val_ts)
    # XIRR - current holdings   
    xi_exist = compute_xirr_existing(h, val_ts)

    kpi = {
        'label': label,
        'user_type': user_type,
        'portfolio_value': round(total_cv, 2),
        'invested': round(total_cost, 2),
        'unrealised_gl': round(total_ugl, 2),
        'realised_gl': round(total_realized, 2),
        'abs_return_pct': abs_ret,
        'xirr_existing': round(xi_exist * 100, 2) if xi_exist else None,
        'xirr_entire': round(xi_all * 100, 2) if xi_all else None,
        'val_date': val_ts.strftime('%d %b %Y'),
        'nav_requested_date': nav_meta.get("requested_date"),
        'nav_latest_available': nav_meta.get("max_nav_date"),
    }

    # -----------------------------
    # Asset Allocation (weighted)
    # -----------------------------

    asset_cols = [c for c in h.columns if c.startswith("asset_alloc_")]

    aa_rows = []

    for col in asset_cols:

        lbl = col.replace("asset_alloc_", "").replace("_", " ").title()

        weights = pd.to_numeric(h[col], errors="coerce").fillna(0) / 100

        value = (h["current_value"] * weights).sum()

        if value > 0:
            aa_rows.append({
                "label": lbl,
                "value": float(value)
            })

    aa = pd.DataFrame(aa_rows)

    if not aa.empty:
        total = aa["value"].sum()
        if total > 0:
            aa["value"] = aa["value"] / total * 100

        aa = aa.sort_values("value", ascending=False).round(2)
    else:
        aa = pd.DataFrame(columns=["label","value"])

    # -----------------------------
    # Market Cap (weighted)
    # -----------------------------
    cap_cols = [c for c in h.columns if c.endswith("_cap")]

    mc_rows = []

    for col in cap_cols:

        lbl = col.replace("_cap", "").replace("_", " ").title()

        weights = pd.to_numeric(h[col], errors="coerce").fillna(0) / 100

        value = (h["current_value"] * weights).sum()

        if value > 0:
            mc_rows.append({
                "label": lbl,
                "value": float(value)
            })

    mc = pd.DataFrame(mc_rows)

    if not mc.empty:
        total = mc["value"].sum()
        if total > 0:
            mc["value"] = mc["value"] / total * 100

        mc = mc.sort_values("value", ascending=False).round(2)
    else:
        mc = pd.DataFrame(columns=["label","value"])

    # -----------------------------
    # Strategy Allocation
    # -----------------------------
    strat = (
        h.groupby("global_broad_category_group")["current_value"]
        .sum()
        .reset_index()
        .rename(columns={
            "global_broad_category_group":"label",
            "current_value":"value"
        })
    )

    if not strat.empty:
        total = strat["value"].sum()
        strat["value"] = strat["value"] / total * 100
        strat = strat.sort_values("value", ascending=False).round(2)
    else:
        strat = pd.DataFrame(columns=["label","value"])

    # -----------------------------
    # Category Allocation
    # -----------------------------
    cat_alloc = (
        h.groupby([
            "global_broad_category_group",
            "morningstar_category"
        ])["current_value"]
        .sum()
        .reset_index()
    )

    cat_alloc["weight_pct"] = (
        cat_alloc["current_value"] /
        cat_alloc.groupby("global_broad_category_group")["current_value"]
        .transform("sum") * 100
    )

    cat_alloc = cat_alloc.round(2)

    # ── Performance tables (scoped) ───────────────────────────────────────
    # cat_rows = []

    # for strategy, h_cat in h.groupby("global_broad_category_group"):

    #     invested = h_cat["cost_value"].sum()
    #     current_value = h_cat["current_value"].sum()
    #     gain = h_cat["unrealised_gl"].sum()

    #     rta_cat = rta_user[
    #         rta_user["isin"].isin(h_cat["isin"].unique())
    #     ]

    #     # XIRR - since inception
    #     xi_all = compute_xirr_entire(rta_cat, current_value, val_ts)
    #     # XIRR - current holdings
    #     xi_exist = compute_xirr_existing(h_cat, val_ts)

    #     cat_rows.append({
    #         "global_broad_category_group": strategy,
    #         "invested": round(invested,2),
    #         "current_value": round(current_value,2),
    #         "unrealised_gl": round(gain,2),
    #         "abs_return_pct": round(gain/invested*100,2) if invested else None,
    #         "xirr_existing": round(xi_exist*100,2) if xi_exist else None,
    #         "xirr_entire": round(xi_all*100,2) if xi_all else None
    #     })

    # cat_summ = pd.DataFrame(cat_rows)

    inv_map = (
        rta_user[['pan', 'inv_name']].drop_duplicates('pan')
        if 'inv_name' in rta_user.columns
        else pd.DataFrame(columns=['pan', 'inv_name'])
    )

    pan_rows = []

    for pan in pans:

        rta_pan = rta_user[rta_user["pan"] == pan]
        h_pan = h[h["pan"] == pan]

        invested = h_pan["cost_value"].sum()
        current_value = h_pan["current_value"].sum()
        gain = h_pan["unrealised_gl"].sum()

        # realised gain per PAN
        realized_pan = realized_user[
            realized_user["pan"] == pan
        ]["gain_loss"].sum()

        # XIRR - since inception
        xi_all = compute_xirr_entire(rta_pan, current_value, val_ts)

        # XIRR - current holdings
        xi_exist = compute_xirr_existing(h_pan, val_ts)

        pan_rows.append({
            "pan": pan,
            "invested": round(invested,2),
            "current_value": round(current_value,2),
            "unrealised_gl": round(gain,2),
            "realised_gl": round(realized_pan,2),   # ← ADD THIS
            "abs_return_pct": round(gain/invested*100,2) if invested else None,
            "xirr_existing": round(xi_exist*100,2) if xi_exist else None,
            "xirr_entire": round(xi_all*100,2) if xi_all else None
        })

    if not pan_rows:
        pan_summ = pd.DataFrame(columns=["pan", "inv_name", "invested", "current_value", "unrealised_gl", "abs_return_pct", "xirr_existing", "xirr_entire"])
    else:
        pan_summ = pd.DataFrame(pan_rows).merge(inv_map, on="pan", how="left")


    h["fund_display"] = h["fund_display"].fillna("Unknown Fund")
    isin_summ = build_fund_performance_view(rta_user, h, val_ts)

    # Strategy level performance (for Fund Performance header)
    strat_summ = []

    for strategy, grp in isin_summ.groupby("global_broad_category_group"):

        invested = grp["invested"].sum()
        current_value = grp["current_value"].sum()
        gain = grp["unrealised_gl"].sum()

        # recompute XIRR using real cashflows
        rta_strat = rta_user[
            rta_user["isin"].isin(grp["isin"].unique())
        ]
        # XIRR - since inception
        xi_entire = compute_xirr_entire(rta_strat, current_value, val_ts)
        # XIRR - current holdings
        h_strat = h[h["isin"].isin(grp["isin"].unique())]
        xi_exist = compute_xirr_existing(h_strat, val_ts)

        strat_summ.append({
            "global_broad_category_group": strategy,
            "invested": round(invested,2),
            "current_value": round(current_value,2),
            "unrealised_gl": round(gain,2),
            "abs_return_pct":
                round(gain/invested*100,2) if invested else None,
            "xirr_existing":
                round(xi_exist*100,2) if xi_exist else None,
            "xirr_entire":
                round(xi_entire*100,2) if xi_entire else None
        })

    strat_summ = pd.DataFrame(strat_summ)

    # add strategy weight
    if not strat_summ.empty:
        total = strat_summ["current_value"].sum()
        strat_summ["weight_pct"] = (
            strat_summ["current_value"] / total * 100
        ).round(2)
    
    # ── Profit booking (scoped) ───────────────────────────────────────────
    pb = profit_booking_df[profit_booking_df['pan'].isin(pans)].copy() \
            if not profit_booking_df.empty else pd.DataFrame()

    pb_fund = pd.DataFrame()
    pb_category = pd.DataFrame()
    pb_fy = pd.DataFrame()
    pb_strategy = pd.DataFrame()

    if not pb.empty:

        # use realized data (has sell_date)
        realized = results["realized"]
        realized = realized[realized["pan"].isin(pans)].copy()

        realized["sell_date"] = pd.to_datetime(realized["sell_date"])

        # Financial Year
        realized["financial_year"] = np.where(
            realized["sell_date"].dt.month > 3,
            "FY" + (realized["sell_date"].dt.year + 1).astype(str).str[-2:],
            "FY" + (realized["sell_date"].dt.year).astype(str).str[-2:]
        )

        # FY summary
        pb_fy = (
            realized.groupby(["financial_year","gain_type"])
            .agg(
                total_cost=("cost","sum"),
                total_proceeds=("proceeds","sum"),
                total_gain_loss=("gain_loss","sum")
            )
            .reset_index()
        )

        # percentage
        pb_fy["gain_loss_pct"] = np.where(
            pb_fy["total_cost"] != 0,
            pb_fy["total_gain_loss"] / pb_fy["total_cost"] * 100,
            None
        )

        # rename for UI
        pb_fy = pb_fy.rename(columns={
            "financial_year":"fy",
            "total_cost":"investment",
            "total_proceeds":"sale",
            "total_gain_loss":"gain",
            "gain_loss_pct":"pct",
            "gain_type":"type"
        })

        # round
        pb_fy = pb_fy.round(2)

        # sort newest FY first
        pb_fy = pb_fy.sort_values(
            ["fy","type"],
            ascending=[False, True]
        ).reset_index(drop=True)

        # FY → Strategy
        pb_strategy = (
            realized.groupby([
                "financial_year",
                "global_broad_category_group"
            ])
            .agg(
                total_cost=("cost","sum"),
                total_proceeds=("proceeds","sum"),
                total_gain_loss=("gain_loss","sum")
            )
            .reset_index()
        )

        # FY → Strategy → Category
        pb_category = (
            realized.groupby([
                "financial_year",
                "global_broad_category_group",
                "morningstar_category"
            ])
            .agg(
                total_cost=("cost","sum"),
                total_proceeds=("proceeds","sum"),
                total_gain_loss=("gain_loss","sum")
            )
            .reset_index()
        )
        
        # FUND TRANSACTION LEVEL
        pb_fund = realized.copy()

        pb_fund = pb_fund.rename(columns={
            "buy_date": "dop",
            "sell_date": "dos",
            "units": "total_units",
            "cost": "total_cost",
            "proceeds": "total_proceeds",
            "gain_loss": "total_gain_loss"
        })

        pb_fund["financial_year"] = pb_fund["dos"].apply(get_financial_year)

        pb_fund["gain_loss_pct"] = np.where(
            pb_fund["total_cost"] != 0,
            pb_fund["total_gain_loss"] / pb_fund["total_cost"] * 100,
            None
        )

        inv_map = rta_enr[["pan","inv_name"]].drop_duplicates("pan")
        pb_fund = pb_fund.merge(inv_map, on="pan", how="left")

        pb_fund = pb_fund[
            [
            "pan",
            "inv_name",
            "financial_year",
            "global_broad_category_group",
            "fund_display",
            "folio_no",
            "dop",
            "dos",
            "total_units",
            "total_cost",
            "total_proceeds",
            "total_gain_loss",
            "gain_loss_pct",
            "gain_type"
            ]
        ]

        pb_fund = pb_fund.sort_values(
            ["inv_name","financial_year","dos"],
            ascending=[True,False,False]
        )

    hold_cols = [
        'pan', 'folio_no', 'isin', 'fund_display', 'global_broad_category_group',
        'morningstar_category', 'buy_date', 'buy_nav', 'units_remaining',
        'cost_value', 'current_nav', 'nav_as_of', 'current_value', 'unrealised_gl',
        'unrealised_gl_pct', 'holding_days'
    ]
    hold_out = h[[c for c in hold_cols if c in h.columns]].round(4)

    return {
        'label': label,
        'pans': pans,
        'user_type': user_type,
        'kpi': kpi,
        'assetAlloc': df_to_records(aa),
        'marketCap': df_to_records(mc),
        'strategyAlloc': df_to_records(strat),
        'categoryAlloc': df_to_records(cat_alloc),

        'panSummary': df_to_records(pan_summ.round(2)),
        'perfIsin': df_to_records(isin_summ.round(2)),
        'perfStrat': df_to_records(strat_summ.round(2)),
        # 'perfCat': df_to_records(cat_summ.round(2)),
        
        'profitBook': df_to_records(pb.round(2)) if not pb.empty else [],
        'profitBookFund': df_to_records(pb_fund.round(2)) if not pb_fund.empty else [],
        'profitBookTransactions': df_to_records(pb_fund),

        'profitBookFY': df_to_records(pb_fy),
        'profitBookStrategy': df_to_records(pb_strategy),
        'profitBookCategory': df_to_records(pb_category),

        'holdings': df_to_records(hold_out),
    }

def generate_portfolio_json(results, user_configs, user_output_dir="output/users"):
    import os
    import json
    import numpy as np

    os.makedirs(user_output_dir, exist_ok=True)

    def clean_nan(obj):
        if isinstance(obj, dict):
            return {k: clean_nan(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean_nan(v) for v in obj]
        if isinstance(obj, (np.floating, np.integer)):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return obj.item()
        if isinstance(obj, float):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return obj
        return obj

    def compress_keys(obj):
        if isinstance(obj, list):
            return [compress_keys(x) for x in obj]
        if not isinstance(obj, dict):
            return obj

        mapping = {
            "portfolio_value": "pv",
            "invested": "inv",
            "unrealised_gl": "ugl",
            "realised_gl": "rgl",
            "abs_return_pct": "ret",
            "xirr_existing": "x1",
            "xirr_entire": "x2",
            "current_value": "cv",
            "weight_pct": "w",
            "label": "l",
            "value": "v",
            "pan": "p",
            "inv_name": "n",
            "morningstar_category": "c",
            "global_broad_category_group": "g",
        }

        out = {}
        for k, v in obj.items():
            out[mapping.get(k, k)] = compress_keys(v)
        return out

    val_ts = results.get("val_ts")
    meta = {
        "requested_valuation_date": val_ts.strftime("%Y-%m-%d") if val_ts else None,
        "nav_fallback": "last_available_if_missing",
    }

    index = []

    for cfg in user_configs:
        login = cfg["login_id"]
        print(f"Building JSON for {login}")

        data = build_user_json(
            results=results,
            pans=cfg["pans"],
            label=cfg["name"],
            user_type=cfg["user_type"],
        )

        payload = clean_nan({
            "password": cfg["password"],
            "user_type": cfg["user_type"],
            "name": cfg["name"],
            "pans": cfg["pans"],
            "data": compress_keys(data),
            "_meta": meta,
        })

        file_name = f"{login}.json"
        file_path = os.path.join(user_output_dir, file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"), allow_nan=False)

        index.append(clean_nan({
            "login": login,
            "name": cfg["name"],
            "type": cfg["user_type"],
            "pans": cfg["pans"],
            "mfu_can": cfg.get("mfu_can"),
            "mobile": cfg.get("mobile"),
            "email_connect": cfg.get("email_connect"),
            "dob": cfg.get("dob"),
            "file": file_name,
        }))

        print(f"written -> {file_path}")

    index_path = os.path.join(user_output_dir, "users_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({"users": index}, f, separators=(",", ":"))

    print(f"index written -> {index_path}")
    return user_output_dir
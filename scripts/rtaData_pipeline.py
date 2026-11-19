import os
import pyzipper
import datetime
from supabase import create_client
import hashlib
import email.utils
import imaplib
import email
import socket
import pandas as pd
import numpy as np
import re
import requests
import zipfile

from bs4 import BeautifulSoup
from email import policy
from email.parser import BytesParser


socket.setdefaulttimeout(15)  # 15 seconds max


os.makedirs("./raw", exist_ok=True)


# -------------------------------
# Email Connection
# -------------------------------


EMAIL_KD = os.environ.get("EMAIL_KD")
EMAIL_KD_PASS = os.environ.get("EMAIL_KD_PASS")


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


def fetch_emails():
    print("📬 Connecting to IMAP...")


    mail = imaplib.IMAP4_SSL("imap.gmail.com")

    print("🔐 Logging in...")
    mail.login(EMAIL_KD, EMAIL_KD_PASS)


    print("📂 Selecting inbox...")
    mail.select("inbox")


    print("🔎 Searching emails...")
    status, messages = mail.search(None, 'ALL')


    print("📥 Fetching emails...")


    email_list = []
    nums = messages[0].split()


    print(f"Total messages: {len(nums)}")


    for i, num in enumerate(nums[-20:]):  # 👈 LIMIT to last 20 emails
        print(f"Fetching {i+1}/{min(20, len(nums))}")


        status, data = mail.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])
        email_list.append(msg)


    print("✅ Emails fetched")


    return email_list


def fetch_all_rows(supabase, table_name: str, batch_size: int = 1000) -> pd.DataFrame:
    """
    Fetch all rows from a Supabase table using pagination.
    """
    all_rows = []
    offset = 0


    while True:
        response = (
            supabase.table(table_name)
            .select("*")
            .range(offset, offset + batch_size - 1)
            .execute()
        )

        data = response.data
        if not data:
            break

        all_rows.extend(data)
        offset += batch_size


    df = pd.DataFrame(all_rows)
    return df


def get_pipeline_state():
    res = supabase.table("pipeline_runs") \
        .select("*") \
        .eq("status", "SUCCESS") \
        .order("run_completed_at", desc=True) \
        .limit(1) \
        .execute()


    if not res.data:
        return {
            "last_email_ts": None,
            "last_file_hash": None
        }


    row = res.data[0]


    return {
        "last_email_ts": row.get("last_email_ts"),
        "last_file_hash": row.get("last_file_hash")
    }


def get_file_hash(file_path):
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def parse_ts(ts):
    if not ts:
        return None


    if isinstance(ts, datetime.datetime):
        dt = ts
    else:
        dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


    # Normalize to UTC naive
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)


    return dt


def parse_email_date(msg):
    raw_date = msg.get("Date") or msg.get("date")
    dt = email.utils.parsedate_to_datetime(raw_date)


    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)


    return dt


def should_process(msg_date, last_email_ts):
    if not last_email_ts:
        return True

    last_ts = parse_ts(last_email_ts)
    return msg_date >= last_ts


def extract_zip_single(zip_path, extract_dir, password):
    os.makedirs(extract_dir, exist_ok=True)


    try:
        with pyzipper.AESZipFile(zip_path) as zf:
            zf.pwd = password.encode()
            zf.extractall(path=extract_dir)


        files = os.listdir(extract_dir)


        if len(files) != 1:
            raise Exception("Unexpected ZIP structure")


        extracted_file = os.path.join(extract_dir, files[0])


        print(f"✅ Extracted: {files[0]}")
        return extracted_file


    except RuntimeError:
        print("❌ Wrong password or unsupported encryption")
    except Exception as e:
        print("❌ Extraction failed:", e)


    return None


def get_extracted_file(folder):
    for file in os.listdir(folder):
        if file.endswith((".xls", ".xlsx", ".csv", ".txt")):
            return os.path.join(folder, file)

    return None


def get_rta_password(source):
    if source == "KFIN":
        return "Karvy123@"
    elif source == "CAMS":
        return "Cams123@"
    else:
        raise Exception("Unknown source for password")


def classify_email(msg):
    sender = msg.get("From", "").lower()
    subject = msg.get("Subject", "").lower()


    if "kfintech.com" in sender and any(
        x in subject for x in ["transaction report", "transaction feeds", "wbtrn"]
    ):
        return "KFIN"


    if "camsonline.com" in sender and "wbr2" in subject:
        return "CAMS"


    return None


def get_email_body(msg):
    body = ""


    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()


            if content_type == "text/html":
                body = part.get_payload(decode=True).decode(errors="ignore")
                return body


            elif content_type == "text/plain" and not body:
                body = part.get_payload(decode=True).decode(errors="ignore")


    else:
        body = msg.get_payload(decode=True).decode(errors="ignore")

    print("📧 EMAIL BODY PREVIEW:")
    print(body[:1000])

    return body


def extract_links(body, source):
    links = []
    soup = BeautifulSoup(body, "html.parser")


    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True).lower()


        if source == "CAMS":
            if "mailback_result/" in href and href.lower().endswith(".zip"):
                links.append(href)


        elif source == "KFIN":
            if "click here" in text:
                links.append(href)


    print("🔗 Links found:", links)
    return links


import re
import os
import requests
import zipfile
from bs4 import BeautifulSoup


def download_file(url, path):
    """
    Download a KFIN/CAMS report.

    If the response is HTML, inspect it for the real download URL,
    form action, JavaScript download location, or meta refresh target.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": "https://mfs.kfintech.com/",
        }

        session = requests.Session()
        session.headers.update(headers)

        response = session.get(
            url,
            allow_redirects=True,
            stream=True,
            timeout=30
        )

        content_type = (response.headers.get("Content-Type") or "").lower()
        final_url = response.url

        print("Final URL:", final_url)
        print("Content-Type:", content_type)

        # If it is already a ZIP, save and validate it
        if "zip" in content_type:
            with open(path, "wb") as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)

            if zipfile.is_zipfile(path):
                print(f"⬇️ Downloaded valid ZIP: {path}")
                return True

            print("❌ Response claimed ZIP but file is invalid")
            os.remove(path)
            return False

        # For HTML, read and inspect the page
        html = response.text

        # print("🧪 HTML response preview:")
        # print(html[:3000])

        # Save for manual inspection
        # debug_html_path = path.replace(".zip", "_debug.html")

        with open(debug_html_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"🧪 Saved HTML for inspection: {debug_html_path}")

        soup = BeautifulSoup(html, "html.parser")

        # 1. Look for direct downloadable links
        candidate_urls = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True).lower()

            if any(
                keyword in href.lower()
                for keyword in (
                    "download",
                    "report",
                    "generate",
                    "export",
                    "zip",
                    "csv",
                    "xls",
                )
            ) or any(
                keyword in text
                for keyword in ("download", "click here", "export")
            ):
                candidate_urls.append(href)

        # 2. Look for form actions
        for form in soup.find_all("form"):
            action = form.get("action")

            if action:
                candidate_urls.append(action)

        # 3. Look for JavaScript download locations
        js_matches = re.findall(
            r"(?:window\.location|location\.href|window\.open)\s*=?\s*['\"]([^'\"]+)['\"]",
            html,
            flags=re.IGNORECASE
        )

        candidate_urls.extend(js_matches)

        # 4. Look for meta refresh
        for meta in soup.find_all("meta"):
            if str(meta.get("http-equiv", "")).lower() == "refresh":
                content = meta.get("content", "")
                match = re.search(r"url=([^;]+)", content, flags=re.IGNORECASE)

                if match:
                    candidate_urls.append(match.group(1).strip())

        # Deduplicate while preserving order
        candidate_urls = list(dict.fromkeys(candidate_urls))

        print("🔍 Candidate download URLs:", candidate_urls)

        for i, candidate in enumerate(candidate_urls):
            # Resolve relative URLs
            next_url = requests.compat.urljoin(final_url, candidate)

            print(f"➡️ Trying candidate {i + 1}: {next_url}")

            next_response = session.get(
                next_url,
                allow_redirects=True,
                stream=True,
                timeout=30
            )

            next_content_type = (
                next_response.headers.get("Content-Type") or ""
            ).lower()

            print("Candidate Content-Type:", next_content_type)
            print("Candidate Final URL:", next_response.url)

            if "zip" in next_content_type:
                with open(path, "wb") as f:
                    for chunk in next_response.iter_content(8192):
                        f.write(chunk)

                if zipfile.is_zipfile(path):
                    print(f"⬇️ Downloaded valid ZIP: {path}")
                    return True

                print("❌ Candidate response was not a valid ZIP")
                os.remove(path)
                continue

            # Save candidate response for diagnosis
            candidate_debug_path = path.replace(
                ".zip",
                f"_candidate_{i}_debug.html"
            )

            with open(candidate_debug_path, "wb") as f:
                f.write(next_response.content)

            print(
                f"🧪 Saved candidate response: {candidate_debug_path}"
            )

        print("❌ No downloadable ZIP found in HTML response")
        return False

    except Exception as e:
        print("Download error:", e)

        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

        return False
    
def debug_mime_parts(msg):
    """
    Helps identify how KFIN is sending the attachment.
    """
    print("🧩 MIME parts:")

    for i, part in enumerate(msg.walk()):
        print(
            i,
            "content_type=", part.get_content_type(),
            "disposition=", part.get_content_disposition(),
            "filename=", part.get_filename(),
            "params=", part.get_params()
        )


def extract_attachment(msg, save_dir):
    """
    Robust attachment extractor.

    - Handles attachments with missing filenames
    - Handles .ZIP / .Zip / .zip extensions
    - Handles inline binary attachments
    - Detects ZIP files using the PK magic-byte signature
    """
    os.makedirs(save_dir, exist_ok=True)

    candidates = []

    for i, part in enumerate(msg.walk()):
        content_type = (part.get_content_type() or "").lower()
        disposition = part.get_content_disposition()
        filename = part.get_filename()

        # Ignore email body and multipart containers
        if content_type.startswith(("text/", "multipart/")):
            continue

        payload = part.get_payload(decode=True)

        if not payload:
            continue

        # Detect ZIP by actual file signature
        is_zip = payload[:4] == b"PK\x03\x04"

        # Accept attachment, inline binary, or unnamed binary parts
        is_candidate = (
            disposition == "attachment"
            or content_type in (
                "application/zip",
                "application/x-zip-compressed",
                "application/octet-stream",
            )
            or is_zip
        )

        if not is_candidate:
            continue

        if not filename:
            ext = ".zip" if is_zip else ".bin"
            filename = f"kfin_attachment_{i}{ext}"

        # Normalize ZIP extension and case
        root, ext = os.path.splitext(filename)

        if is_zip and ext.lower() != ".zip":
            filename = root + ".zip"

        path = os.path.join(save_dir, filename)

        # Avoid overwriting another attachment with the same name
        counter = 1
        while os.path.exists(path):
            base, extension = os.path.splitext(filename)
            path = os.path.join(save_dir, f"{base}_{counter}{extension}")
            counter += 1

        with open(path, "wb") as f:
            f.write(payload)

        print(
            f"📎 Saved candidate attachment: {path} "
            f"(content_type={content_type}, disposition={disposition})"
        )

        candidates.append(path)

    # Prefer an actual ZIP; otherwise return first binary candidate
    for path in candidates:
        if zipfile.is_zipfile(path):
            return path

    return candidates[0] if candidates else None


cams_txn_map = {
    'P': 'Purchase',
    'R': 'Redemption',
    'DR': 'Dividend Reinvestment',
    'DP': 'Dividend Payout',
    'DA': 'Dividend Adjustment',
    'JP': 'Joint Purchase',
    'JR': 'Joint Redemption',
    'SI': 'Systematic Investment',
    'SO': 'Systematic Withdrawal',
    'JS': 'Joint Switch',
    'TI': 'Transfer In',
    'TO': 'Transfer Out',
    'JT': 'Joint Transfer'
}


txn_cat_map = {
    'Initial Allotment': 'P',
    'Purchase': 'P',
    'Redemption': 'R',
    'Purchase Rejection': 'D',
    'New Purchase Pre-Rejection': 'D',
    'Additional Purchase Pre-Rejection': 'D',
    'Refund': 'D',
    'Redemption Rejection': 'D',
    'Systematic Investment': 'P',
    'Systematic Withdrawal': 'R',
    'SIP Rejection': 'R',
    'Systematic Investment Pre-Rejection': 'D',
    'Dividend Reinvestment': 'P',
    'Dividend Payout': 'R',
    'Switch Over In': 'P',
    'Switch Over Out': 'R',
    'Transfer In': 'P',
    'Transfer Out': 'R',
    'Lateral Shift In': 'P',
    'Lateral Shift Out': 'R',
    'S T P In': 'P',
    'S T P Out': 'R',
    'Transmission In': 'P',
    'Transmission Out': 'R',
    'Pledging': 'L',
    'Unpledging': 'UL',
}


def map_txn(code):
    if pd.isna(code):
        return None


    code = str(code)


    prefix2 = code[:2]

    if prefix2 in cams_txn_map:
        return cams_txn_map[prefix2]


    prefix1 = code[:1]
    return cams_txn_map.get(prefix1, 'Unknown')


def parse_date(x):
    try:
        # US format with time (CAMS often uses this)
        return pd.to_datetime(x, format="%m/%d/%Y %I:%M:%S %p")
    except Exception:
        try:
            # DD-MM-YYYY (KFIN often uses this)
            return pd.to_datetime(x, format="%d-%m-%Y")
        except Exception:
            return pd.NaT


def consolidate_transactions(df):
    # Only redemption
    final_df = df.copy()


    group_cols = ["folio_no", "trxnno", "purprice"]


    final_df = final_df.groupby(group_cols, as_index=False).agg({
        "pan": "first",
        "inv_name": "first",
        "folio_no": "first",
        "isin": "first",
        "prodcode": "first",
        "fund_name": "first",
        "purchase_mode": "first",
        "option": "first",
        "transaction_type": "first",
        "txn_code": "first",
        "trxnno": "first",
        "trxnstat": "first",
        "traddate": "min",
        "postdate": "max",
        "purprice": "first",
        "units": "sum",
        "amount": "sum",
        "brokcode": "first",
        "rev_remark": "first",
    })


    print(f"🔁 Consolidated transactions: {len(final_df)} rows")


    return final_df


def generate_txn_id(df):
    df["purprice"] = df["purprice"].round(4)

    df["txn_id"] = (
        df["folio_no"].astype(str) + "-" +
        df["trxnno"].astype(str) + "-" +
        df["purprice"].astype(str)
    )

    return df


def get_existing_txn_ids(txn_ids):
    existing = set()


    chunk_size = 500  # safer for API limits


    for i in range(0, len(txn_ids), chunk_size):
        chunk = txn_ids[i:i + chunk_size]


        res = supabase.table("rta_transactions") \
            .select("txn_id") \
            .in_("txn_id", chunk) \
            .execute()


        existing.update([r["txn_id"] for r in res.data])


    return existing


def process_rta_file(file_path, source, cams_isinMapper):
    skip_prodcodes = [
        'B211G',
        'B231G',
        'FTI400',
        'FTI309',
        '129OCGPG'
    ]

    # -------------------------------
    # LOAD FILE
    # -------------------------------
    if file_path.endswith(".csv"):
        df = pd.read_csv(
            file_path,
            engine="python",
            on_bad_lines="skip"
        )

    elif file_path.endswith((".xls", ".xlsx")):
        df = pd.read_excel(file_path)

    else:
        print("❌ Unsupported file format")
        return None


    # -------------------------------
    # SOURCE-SPECIFIC LOGIC
    # -------------------------------
    if source == "CAMS":
        df.columns = df.columns.str.strip("'")


        # Clean values in each column
        df = df.apply(
            lambda col: col.map(
                lambda x: (
                    np.nan
                    if isinstance(x, str) and x.strip() == ""
                    else x.strip("'")
                    if isinstance(x, str)
                    else x
                )
            )
        )


        # Applying lower case to all column names
        df.columns = df.columns.str.lower()


        df['transaction_type'] = df['trxntype'].apply(map_txn)
        df = df.dropna(axis=1, how='all')


        # Removing few isins which are not available (These funds are scrapped)
        df = df[~df['prodcode'].isin(skip_prodcodes)]


        # Bringing the isins from cams_isin_prodcode_mapper
        df = df.merge(cams_isinMapper, how='left', on='prodcode')


        # Cleaning up the reversed transactions whose units are negative
        mask = df['units'] < 0

        df.loc[mask, 'transaction_type'] = 'Redemption'
        df.loc[mask, 'units'] = -df.loc[mask, 'units']
        df.loc[mask, 'amount'] = -df.loc[mask, 'amount']


        req_cols = [
            'pan',
            'inv_name',
            'folio_no',
            'prodcode',
            'isin',
            'scheme',
            'transaction_type',
            'trxnno',
            'trxnstat',
            'traddate',
            'postdate',
            'purprice',
            'units',
            'amount',
            'brokcode',
            'rev_remark'
        ]


        df = df[req_cols]


    elif source == "KFIN":
        df.columns = df.columns.str.lower()


        # -------------------------------
        # FORMAT 1 (classic KFIN)
        # -------------------------------
        if 'fmcode' in df.columns:
            print("✅ KFIN Format 1 detected")


            df = df.rename(columns={
                'fmcode': 'prodcode',
                'pan1': 'pan',
                'invname': 'inv_name',
                'td_acno': 'folio_no',
                'funddesc': 'scheme',
                'td_trno': 'trxnno',
                'trnstat': 'trxnstat',
                'navdate': 'traddate',
                'td_prdt': 'postdate',
                'td_units': 'units',
                'td_nav': 'purprice',
                'td_amt': 'amount',
                'td_agent': 'brokcode',
                'trdesc': 'transaction_type',
                'remarks': 'rev_remark'
            })


            print("traddate sample:", df["traddate"].head(5))
            print("postdate sample:", df["postdate"].head(5))


            if 'divopt' in df.columns:
                df['prodcode'] = df['prodcode'].astype(str) + df['divopt'].fillna('')


            df = df.dropna(axis=1, how='all')


            # Removing few isins which are not available (These funds are scrapped)
            df = df[~df['prodcode'].isin(skip_prodcodes)]


            # Bringing the isins from isin_mapper
            df = df.merge(isinMapper, how='left', on='prodcode')


        # -------------------------------
        # FORMAT 2 (mailback report)
        # -------------------------------
        elif 'product code' in df.columns:
            print("✅ KFIN Format 2 detected")


            df = df.drop('scheme', axis=1)


            df = df.rename(columns={
                'product code': 'prodcode',
                'pan1': 'pan',
                'investor name': 'inv_name',
                'folio number': 'folio_no',
                'fund description': 'scheme',
                'transaction number': 'trxnno',
                'transaction status': 'trxnstat',
                'transaction date': 'traddate',
                'process date': 'postdate',
                'units': 'units',
                'nav': 'purprice',
                'amount': 'amount',
                'agent code': 'brokcode',
                'transaction description': 'transaction_type',
                'remarks': 'rev_remark',
            })


            # handle dividend option
            if 'dividend option' in df.columns:
                df['prodcode'] = (
                    df['prodcode'].astype(str)
                    + df['dividend option'].fillna('')
                )


        else:
            print("❌ Unknown KFIN format")
            print('KFIN dataframe columns:', list(df.columns))
            return None


        # Cleaning up the reversed transactions whose units are negative
        mask = df['units'] < 0

        df.loc[mask, 'transaction_type'] = 'Redemption'
        df.loc[mask, 'units'] = -df.loc[mask, 'units']
        df.loc[mask, 'amount'] = -df.loc[mask, 'amount']


        # -------------------------------
        # SAFE COLUMN HANDLING
        # -------------------------------
        req_cols = [
            'pan',
            'inv_name',
            'folio_no',
            'prodcode',
            'isin',
            'scheme',
            'transaction_type',
            'trxnno',
            'trxnstat',
            'traddate',
            'postdate',
            'purprice',
            'units',
            'amount',
            'brokcode',
            'rev_remark'
        ]


        missing_cols = [
            col for col in req_cols
            if col not in df.columns
        ]


        if missing_cols:
            print("❌ Missing columns after rename:", missing_cols)
            print("Available columns:", list(df.columns))
            return None


        df = df[req_cols]


    else:
        print("❌ Unknown source")
        return None


    # -------------------------------
    # COMMON PROCESSING
    # -------------------------------
    trData = df.copy()


    trData['txn_code'] = trData['transaction_type'].map(txn_cat_map)


    trData['fund_name'] = trData['scheme'].str.replace(
        r"\(.*?\)",
        "",
        regex=True
    )


    trData['purchase_mode'] = trData['fund_name'].str.contains(
        r"(?:Regular Plan|Regular|Reg)",
        case=False,
        regex=True
    ).map({True: "Regular", False: ""})


    trData['fund_name'] = trData['fund_name'].str.replace(
        r"(?:Regular Plan|Regular|Reg)",
        "",
        case=False,
        regex=True
    )


    trData['fund_name'] = trData['fund_name'].str.replace(
        r"(Ular|ular)",
        "",
        case=False,
        regex=False
    )


    def extract_option(text):
        text = str(text).lower()

        if "dividend" in text:
            return "Dividend"
        elif "growth" in text or re.search(r"\bG\b", text):
            return "Growth"

        return ""


    trData['option'] = trData['fund_name'].apply(extract_option)


    trData['fund_name'] = (
        trData['fund_name']
        .str.replace("-", " ")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.title()
    )


    # -------------------------------
    # ROBUST DATE PARSING
    # -------------------------------
    def parse_mixed_date_series(series, source=None):
        s = series.astype(str).str.strip()
        out = pd.Series(
            pd.NaT,
            index=series.index,
            dtype="datetime64[ns]"
        )


        # 1) Strict ISO: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS
        iso_mask = s.str.match(
            r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}:\d{2})?$",
            na=False
        )

        out.loc[iso_mask] = pd.to_datetime(
            s.loc[iso_mask],
            format="ISO8601",
            errors="coerce"
        )


        # 2) CAMS known format: MM/DD/YYYY HH:MM:SS AM/PM
        cams_mask = s.str.match(
            r"^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2} [APMapm]{2}$",
            na=False
        )

        out.loc[cams_mask] = pd.to_datetime(
            s.loc[cams_mask],
            format="%m/%d/%Y %I:%M:%S %p",
            errors="coerce"
        )


        # 3) Day-first dashed/slashed dates
        dmy_mask = s.str.match(
            r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}$",
            na=False
        )

        out.loc[dmy_mask] = pd.to_datetime(
            s.loc[dmy_mask],
            dayfirst=True,
            errors="coerce"
        )


        # 4) Optional fallback for anything left
        rem_mask = out.isna() & s.notna() & (s != "")

        out.loc[rem_mask] = pd.to_datetime(
            s.loc[rem_mask],
            errors="coerce"
        )


        return out


    trData['traddate'] = parse_mixed_date_series(
        trData['traddate'],
        source=source
    )

    trData['postdate'] = parse_mixed_date_series(
        trData['postdate'],
        source=source
    )


    print("🧪 Parsed traddate sample:")
    print(trData['traddate'].head())


    print("🧪 Parsed postdate sample:")
    print(trData['postdate'].head())


    # -------------------------------
    # SAFE STRING CONVERSION
    # -------------------------------
    trData['traddate'] = trData['traddate'].apply(
        lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else None
    )


    trData['postdate'] = trData['postdate'].apply(
        lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else None
    )


    # -------------------------------
    # Purchase Mode MERGE
    # -------------------------------
    trData = trData.merge(
        isinMapper[['prodcode', 'isin', 'purchase_mode', 'option']],
        on='isin',
        how='left',
        suffixes=('', '_map')
    )


    trData['purchase_mode'] = trData['purchase_mode'].fillna(
        trData['purchase_mode_map']
    )

    trData['option'] = trData['option'].fillna(
        trData['option_map']
    )


    trData = trData.drop(
        columns=['purchase_mode_map', 'option_map']
    )


    # Critical check
    missing_isin = trData[trData['isin'].isna()]


    if not missing_isin.empty:
        print("🚨 Missing ISIN detected. STOP processing.")


        missing_df = missing_isin[['prodcode', 'scheme']].drop_duplicates()

        print(missing_df)


        # Save for manual action
        missing_df.to_csv("missing_isin.csv", index=False)
        print("📁 Saved missing ISIN list → missing_isin.csv")


        return None  # HARD STOP


    print("✅ ISIN mapping complete")


    return trData


def process_email(msg, msg_date):
    source = classify_email(msg)

    if not source:
        return None


    body = get_email_body(msg)
    links = extract_links(body, source)


    zip_path = None


    if source == "KFIN":
        # 🔥 PRIORITY: Attachment
        zip_path = extract_attachment(msg, "./raw")


        if zip_path:
            print("📎 KFIN attachment used:", zip_path)

        else:
            print("⚠️ No usable attachment, trying link fallback")


            for i, link in enumerate(links):
                path = (
                    f"./raw/{source}_"
                    f"{msg_date.strftime('%Y%m%d_%H%M%S')}_{i}.zip"
                )


                if download_file(link, path):
                    zip_path = path
                    break


    elif source == "CAMS":
        # CAMS → link first
        for i, link in enumerate(links):
            path = (
                f"./raw/{source}_"
                f"{msg_date.strftime('%Y%m%d_%H%M%S')}_{i}.zip"
            )


            if download_file(link, path):
                zip_path = path
                break


        if not zip_path:
            zip_path = extract_attachment(msg, "./raw")


    print("🔗 Links found:", links)
    print(
        "Attachments available:",
        [
            part.get_filename()
            for part in msg.walk()
            if part.get_filename()
        ]
    )


    if not zip_path:
        print("❌ No ZIP found")
        return None


    # Validate ZIP
    if not zipfile.is_zipfile(zip_path):
        print("❌ Invalid ZIP file")
        return None


    # Extract
    extract_dir = zip_path.replace(".zip", "")
    password = get_rta_password(source)

    data_file = extract_zip_single(
        zip_path,
        extract_dir,
        password
    )


    if not data_file:
        return None


    # Handoff point
    return data_file


try:
    print("🔄 Fetching pipeline state...")
    state = get_pipeline_state()
    print("✅ Pipeline state loaded")

except Exception as e:
    print("⚠️ Supabase failed:", e)

    state = {
        "last_email_ts": None,
        "last_file_hash": None
    }


last_email_ts = state["last_email_ts"]
last_file_hash = state["last_file_hash"]


latest_ts = None
latest_hash = None


# -------------------------------
# LOAD ISIN MAPPERS
# -------------------------------
print("📊 Loading CAMS ISIN mapper...")


cams_isinMapper = fetch_all_rows(
    supabase,
    "cams_prodcode_isin_mapper"
)

print(f"✅ ISIN mapper loaded: {len(cams_isinMapper)} rows")


if "prodcode" in cams_isinMapper.columns:
    cams_isinMapper["prodcode"] = cams_isinMapper["prodcode"].astype(str)


print("📊 Loading Manual ISIN mapper...")


isinMapper = fetch_all_rows(
    supabase,
    "isin_mapper"
)

print(f"✅ ISIN mapper loaded: {len(isinMapper)} rows")


if "prodcode" in isinMapper.columns:
    isinMapper["prodcode"] = isinMapper["prodcode"].astype(str)


########## Main Execution Block ##############
try:
    emails = fetch_emails()
    print(len(emails))


    processed_hashes = set()


    # -------------------------------
    # START PIPELINE RUN
    # -------------------------------
    run_start_time = datetime.datetime.now(datetime.timezone.utc)


    run_log = {
        "run_started_at": run_start_time.isoformat(),
        "status": "RUNNING",
        "rows_inserted": 0,
        "files_processed": 0
    }


    res = supabase.table("pipeline_runs").insert(run_log).execute()
    run_id = res.data[0]["id"]


    total_rows_inserted = 0
    files_processed = 0


    for msg in emails[:20]:  # keep 20 for now
        source = classify_email(msg)


        print("\n------------------------")
        print("Source:", source)
        print("Subject:", msg.get("Subject"))


        if not source:
            continue


        msg_date = parse_email_date(msg)


        if not should_process(msg_date, last_email_ts):
            print("⏩ Skipped (old email)")
            continue


        # 🔍 Debug MIME structure — useful while validating KFIN emails
        # debug_mime_parts(msg)


        # 🔧 Process email
        result = process_email(msg, msg_date)


        if not result:
            print("❌ No file extracted")
            continue


        file_path = result
        print("📄 File:", file_path)


        file_hash = get_file_hash(file_path)


        # 🚫 Duplicate protection
        if file_hash == last_file_hash or file_hash in processed_hashes:
            print("⏩ Duplicate file skipped")
            continue


        processed_hashes.add(file_hash)


        # ✅ Load into your system
        print("🚀 Loading data...")
        print("📁 File path:", file_path)
        print("📦 Source:", source)


        df = process_rta_file(
            file_path,
            source,
            cams_isinMapper
        )


        if df is None:
            print("⛔ Processing stopped due to missing ISIN")
            continue


        df = consolidate_transactions(df)


        # Generate unique transaction ID
        df = generate_txn_id(df)


        txn_ids = df["txn_id"].tolist()
        existing_ids = get_existing_txn_ids(txn_ids)


        before = len(df)
        df = df[~df["txn_id"].isin(existing_ids)]
        after = len(df)


        print(f"🧹 Removed duplicates: {before - after}")
        print(f"📥 New rows to insert: {after}")


        if df.empty:
            print("⏩ Nothing new to insert")
            continue


        print("📊 Processed rows:", len(df))
        print(df.head())


        df = df.replace({np.nan: None})


        records = df.to_dict(orient="records")


        supabase.table("rta_transactions") \
            .upsert(
                records,
                on_conflict="txn_id"
            ) \
            .execute()


        print(f"✅ Inserted {len(records)} rows")


        total_rows_inserted += len(records)
        files_processed += 1


        # Track latest successful ingestion
        if not latest_ts or (msg_date >= latest_ts):
            latest_ts = msg_date
            latest_hash = file_hash


        print("✅ Processed:", msg.get("Subject"))


    # -------------------------------
    # COMPLETE PIPELINE RUN
    # -------------------------------
    run_end_time = datetime.datetime.now(datetime.timezone.utc)


    final_status = "SUCCESS" if latest_ts else "NO_DATA"


    supabase.table("pipeline_runs").update({
        "run_completed_at": run_end_time.isoformat(),
        "status": final_status,
        "last_email_ts": latest_ts.isoformat() if latest_ts else None,
        "last_file_hash": latest_hash,
        "rows_inserted": total_rows_inserted,
        "files_processed": files_processed
    }).eq("id", run_id).execute()


    print(f"✅ Run completed: {final_status}")


except Exception as e:
    error_message = str(e)

    print("❌ Pipeline failed:", error_message)

    if "run_id" in globals():
        supabase.table("pipeline_runs").update({
            "status": "FAILED",
            "run_completed_at": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            "error_message": error_message
        }).eq("id", run_id).execute()

    raise
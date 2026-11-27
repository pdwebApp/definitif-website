import ast
import hashlib
import io
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
import pdfplumber
from dotenv import load_dotenv
from flask import Blueprint, Flask, jsonify, redirect, render_template, request, url_for
from pypdf import PdfReader
from supabase import Client, create_client

load_dotenv()

cas_bp = Blueprint("cas_bp", __name__, template_folder="templates")

ISIN_REGEX = re.compile(r"\b(INF[A-Z0-9]{9})\b")

SCHEME_KEYWORDS_RE = re.compile(
    r"(?:ISIN:|Non-?Demat|Advisor:|Fund|ETF|Plan|Growth|IDCW|Dividend|Scheme|Cap|Index|Liquid|Gilt|Bond|Advantage|Opportunities|Contra|Focused|Pioneer|Mid|Small|Large|Flexi|Multi)",
    re.IGNORECASE,
)


def get_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
    return create_client(url, key)


def fetch_all_rows(supabase: Client, table_name: str, batch_size: int = 1000) -> pd.DataFrame:
    """Fetch all rows from a Supabase table using pagination."""
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

    return pd.DataFrame(all_rows)


# ---------------------------------------------------------
# 1. PDF Decryption & Text Extraction
# ---------------------------------------------------------
def extract_pages_text(file_bytes: bytes, password: str = "") -> List[str]:
    reader = PdfReader(io.BytesIO(file_bytes))
    if reader.is_encrypted:
        if not password:
            raise ValueError("This CAS PDF is password-protected. Please enter the password.")
        if reader.decrypt(password) == 0:
            raise ValueError("Incorrect PDF password. Please check and try again.")

    pages_text = []
    with pdfplumber.open(io.BytesIO(file_bytes), password=password or None) as pdf:
        for page in pdf.pages:
            pages_text.append(page.extract_text(layout=False) or "")
    return pages_text


# ---------------------------------------------------------
# 2. Normalization & Mapping Helpers
# ---------------------------------------------------------
TXN_CAT_MAP = {
    "Initial Allotment": "P",
    "Purchase": "P",
    "Redemption": "R",
    "Systematic Investment": "P",
    "Systematic Withdrawal": "R",
    "Dividend Reinvestment": "P",
    "Dividend Payout": "R",
    "Switch Over In": "P",
    "Switch Over Out": "R",
    "Transfer In": "P",
    "Transfer Out": "R",
}

DATE_PATTERN = re.compile(
    r"^(?:(\d{1,2})\s*-\s*([A-Za-z]{3})\s*-\s*(\d{4})|"
    r"([A-Za-z]{3})\s*-\s*(\d{4})\s+(\d{1,2})\s*-?|"
    r"(\d{1,2})([A-Za-z]{3})\s*--?\s*(\d{4})|"
    r"-\s*([A-Za-z]{3})\s*-\s*(\d{4})\s+(\d{1,2}))\b"
)


def parse_cas_date(raw_line: str) -> Optional[Tuple[str, str]]:
    m = DATE_PATTERN.match(raw_line.strip())
    if not m:
        return None

    g = m.groups()
    if g[0]:
        day, mon, year = g[0], g[1], g[2]
    elif g[3]:
        mon, year, day = g[3], g[4], g[5]
    elif g[6]:
        day, mon, year = g[6], g[7], g[8]
    else:
        mon, year, day = g[9], g[10], g[11]

    try:
        dt = datetime.strptime(f"{int(day):02d}-{mon.title()}-{year}", "%d-%b-%Y")
        return dt.strftime("%Y-%m-%d"), raw_line.strip()[m.end():].strip()
    except ValueError:
        return None


def parse_positive_number(token: str) -> Optional[float]:
    if not token:
        return None
    cleaned = re.sub(r"[,()$-]", "", token.strip())
    try:
        return abs(float(cleaned))
    except ValueError:
        return None


def normalize_transaction_type(raw_desc: str) -> Tuple[str, str]:
    d = raw_desc.lower()
    if "systematic withdrawal" in d or "swp" in d:
        txn_type = "Systematic Withdrawal"
    elif "systematic" in d or "sip" in d:
        txn_type = "Systematic Investment"
    elif "switch in" in d or "switch over in" in d:
        txn_type = "Switch Over In"
    elif "switch out" in d or "switch over out" in d:
        txn_type = "Switch Over Out"
    elif "redemption" in d:
        txn_type = "Redemption"
    elif "dividend reinvestment" in d or "idcw reinvestment" in d:
        txn_type = "Dividend Reinvestment"
    elif "dividend" in d or "idcw" in d:
        txn_type = "Dividend Payout"
    elif "transfer in" in d:
        txn_type = "Transfer In"
    elif "transfer out" in d:
        txn_type = "Transfer Out"
    else:
        txn_type = "Purchase"

    return txn_type, TXN_CAT_MAP.get(txn_type, "P")


def derive_trxnstat(raw_desc: str) -> str:
    d = raw_desc.lower()
    invalid_keywords = (
        "reject",
        "revers",
        "fail",
        "unsuccessful",
        "invalid",
        "bounce",
        "dishonour",
        "cancel",
    )
    if any(kw in d for kw in invalid_keywords):
        return "N"
    return "Y"


def clean_fund_metadata(raw_scheme: str, full_header: str) -> Tuple[str, str, str]:
    cleaned = re.sub(r"\(.*?\)", "", raw_scheme)

    is_regular = bool(re.search(r"(?:Regular Plan|Regular|Reg)", cleaned, flags=re.IGNORECASE))
    is_direct = "DIRECT" in full_header.upper()
    if is_regular:
        purchase_mode = "Regular"
    elif is_direct:
        purchase_mode = "Direct"
    else:
        purchase_mode = ""

    low = raw_scheme.lower()
    if "dividend" in low or "idcw" in low:
        option = "IDCW"
    elif "growth" in low or re.search(r"\bg\b", low):
        option = "Growth"
    else:
        option = ""

    cleaned = re.sub(
        r"\b(?:Regular Plan|Direct Plan|Regular|Direct|Reg|Growth Option|Growth|IDCW Option|IDCW|Dividend Option|Dividend|Option|Plan)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.replace("Ular", "").replace("ular", "")

    fund_name = re.sub(r"\s+", " ", cleaned.replace("-", " ")).strip().title()
    return fund_name, purchase_mode, option


def extract_explicit_trxnno(desc: str) -> Optional[str]:
    patterns = [
        r"Ref\.?\s*No\.?\s*[:\-]?\s*([A-Za-z0-9_]+)",
        r"Appln[:\s]+([A-Za-z0-9]+)",
        r"PAYMENT\s*-\s*([A-Za-z0-9]+)",
    ]
    for pat in patterns:
        m = re.search(pat, desc, re.IGNORECASE)
        if m and m.group(1) != "0":
            return m.group(1).strip()
    return None


def resolve_trxnno_and_txn_id(
    folio_no: str,
    raw_desc: str,
    purprice: float,
    isin: str,
    traddate: str,
    txn_code: str,
    amount: float,
    units: float,
    seq: int,
) -> Tuple[str, str]:
    explicit = extract_explicit_trxnno(raw_desc)
    if explicit:
        trxnno = explicit
    else:
        sig = f"{folio_no}|{isin}|{traddate}|{txn_code}|{amount:.2f}|{units:.4f}|{seq}"
        digest_int = int(hashlib.sha256(sig.encode("utf-8")).hexdigest()[:12], 16)
        trxnno = f"CAS{digest_int % 10**10:010d}"

    price_rounded = round(purprice, 4)
    txn_id = f"{str(folio_no).strip()}-{trxnno}-{price_rounded}"
    return trxnno, txn_id


def fetch_reference_lookups(supabase: Client) -> Tuple[Dict[str, Dict], Dict[str, str], List[Dict]]:
    isin_to_meta: Dict[str, Dict] = {}
    prodcode_to_isin: Dict[str, str] = {}
    fund_catalog: List[Dict] = []

    # 1. Primary prodcode -> isin lookup from cams_prodcode_isin_mapper
    cams_mapper_df = fetch_all_rows(supabase, "cams_prodcode_isin_mapper")
    if not cams_mapper_df.empty and {"prodcode", "isin"}.issubset(cams_mapper_df.columns):
        for _, row in cams_mapper_df.dropna(subset=["prodcode", "isin"]).iterrows():
            pcode = str(row["prodcode"]).strip().upper()
            isin_key = str(row["isin"]).strip().upper()
            if pcode and isin_key and pcode not in prodcode_to_isin:
                prodcode_to_isin[pcode] = isin_key

    # 2. Secondary metadata & fallback prodcode -> isin lookup from isin_mapper
    mapper_df = fetch_all_rows(supabase, "isin_mapper")
    if not mapper_df.empty and "isin" in mapper_df.columns:
        for _, row in mapper_df.dropna(subset=["isin"]).iterrows():
            isin_key = str(row["isin"]).strip().upper()
            if not isin_key:
                continue
            if isin_key not in isin_to_meta:
                isin_to_meta[isin_key] = row.to_dict()
            pcode = str(row.get("prodcode") or "").strip().upper()
            if pcode and pcode not in prodcode_to_isin:
                prodcode_to_isin[pcode] = isin_key

    # 3. Master catalog from fund_details for UI autocomplete fallback
    fd_df = fetch_all_rows(supabase, "fund_details")
    if not fd_df.empty and "isin" in fd_df.columns:
        name_col = next(
            (c for c in ("scheme_name", "fund_name", "scheme", "fund_desc") if c in fd_df.columns),
            None,
        )
        for _, row in fd_df.dropna(subset=["isin"]).iterrows():
            isin_key = str(row["isin"]).strip().upper()
            if isin_key:
                fund_catalog.append({
                    "isin": isin_key,
                    "name": str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else isin_key,
                })

    return isin_to_meta, prodcode_to_isin, fund_catalog


# ---------------------------------------------------------
# 3. Line Pre-Merger & Main CAS Parser
# ---------------------------------------------------------
def is_noise_or_watermark(line: str) -> bool:
    u = line.upper()
    if "CAMSCASWS" in u or "SWSCASMAC" in u or "NOISREV" in u:
        return True
    skip_prefixes = (
        "KFINTECH",
        "CONSOLIDATED ACCOUNT STATEMENT",
        "OUR MISSION... YOUR GROWTH",
        "CAMS",
        "PAGE ",
        "DATE TRANSACTION AMOUNT",
        "(INR) UNITS PRICE",
        "UNIT BALANCE",
    )
    return any(u.startswith(p) for p in skip_prefixes)


def is_valid_scheme_header_line(line: str) -> bool:
    if is_noise_or_watermark(line):
        return False
    if parse_cas_date(line):
        return False
    # Allow scheme names starting with digits (e.g. 'IFIGDG-360 ONE Focused Fund...')
    if not re.match(r"^[A-Z0-9]{3,12}-[A-Za-z0-9]", line):
        return False
    return bool(SCHEME_KEYWORDS_RE.search(line))


def preprocess_cas_lines(pages_text: List[str]) -> List[str]:
    raw_lines = []
    for page_txt in pages_text:
        for line in page_txt.splitlines():
            s = line.strip()
            if s and not is_noise_or_watermark(s):
                raw_lines.append(s)

    # Pass 1: Merge split dates and split ISINs
    merged: List[str] = []
    i = 0
    while i < len(raw_lines):
        curr = raw_lines[i]
        if i + 1 < len(raw_lines):
            nxt = raw_lines[i + 1]

            if re.match(r"^\d{1,2}-$", curr) and re.match(r"^[A-Za-z]{3}-\d{4}", nxt):
                merged.append(f"{curr}{nxt}")
                i += 2
                continue
            if re.match(r"^[A-Za-z]{3}-\d{4}$", curr) and re.match(r"^\d{1,2}-", nxt):
                merged.append(f"{curr} {nxt}")
                i += 2
                continue
            if re.match(r"^-[A-Za-z]{3}-\d{4}$", curr) and re.match(r"^\d{1,2}\b", nxt):
                merged.append(f"{curr} {nxt}")
                i += 2
                continue

            split_isin_head = re.search(r"ISIN:\s*([A-Z0-9]{0,11})$", curr, re.IGNORECASE)
            if split_isin_head:
                prefix_chars = split_isin_head.group(1)
                needed = 12 - len(prefix_chars)
                suffix_match = re.match(rf"^([A-Z0-9]{{{needed}}})(.*)$", nxt, re.IGNORECASE)
                if suffix_match:
                    full_isin = (prefix_chars + suffix_match.group(1)).upper()
                    rebuilt_curr = re.sub(
                        r"ISIN:\s*[A-Z0-9]{0,11}$",
                        f"ISIN: {full_isin}{suffix_match.group(2)}",
                        curr,
                        flags=re.IGNORECASE,
                    )
                    merged.append(rebuilt_curr)
                    i += 2
                    continue

        merged.append(curr)
        i += 1

    # Pass 2: Merge multi-line scheme headers
    final_lines: List[str] = []
    i = 0
    while i < len(merged):
        curr = merged[i]
        if is_valid_scheme_header_line(curr) and "ISIN:" not in curr:
            combined = curr
            j = i + 1
            while j < len(merged) and j <= i + 3:
                nxt = merged[j]
                if parse_cas_date(nxt) or nxt.startswith("Opening") or nxt.startswith("Nominee"):
                    break
                combined += " " + nxt
                j += 1
                if "ISIN:" in nxt:
                    break
            final_lines.append(combined)
            i = j
            continue

        final_lines.append(curr)
        i += 1

    return final_lines


def parse_cas_to_records(
    pages_text: List[str],
    isin_mapper: Optional[Dict[str, Dict]] = None,
    prodcode_to_isin: Optional[Dict[str, str]] = None,
) -> List[Dict]:
    isin_mapper = isin_mapper or {}
    prodcode_to_isin = prodcode_to_isin or {}
    merged_lines = preprocess_cas_lines(pages_text)

    records: List[Dict] = []
    ctx = {
        "pan": None,
        "folio_no": None,
        "inv_name": None,
        "prodcode": None,
        "fund_name": None,
        "isin": None,
        "purchase_mode": None,
        "option": None,
        "brokcode": None,
    }
    in_scheme_section = False
    scheme_start_record_idx = 0
    occurrence_counter: Dict[str, int] = {}

    def apply_scheme_header(header_text: str) -> None:
        nonlocal in_scheme_section, scheme_start_record_idx
        isin_match = re.search(r"ISIN:\s*([A-Z0-9]{12})", header_text, re.IGNORECASE) or ISIN_REGEX.search(header_text)
        scheme_match = re.match(
            r"^([A-Z0-9]{3,12})-(.+?)(?:\s*\(Non-?Demat\)|\s*-?\s*ISIN:|$)",
            header_text,
            re.IGNORECASE,
        )

        raw_prodcode = scheme_match.group(1).strip().upper() if scheme_match else (ctx["prodcode"] or "")
        raw_scheme_name = scheme_match.group(2).strip(" -") if scheme_match else header_text
        fund_name, purchase_mode, option = clean_fund_metadata(raw_scheme_name, header_text)

        isin_val = isin_match.group(1).strip().upper() if isin_match else None
        if not isin_val and raw_prodcode in prodcode_to_isin:
            isin_val = prodcode_to_isin[raw_prodcode]

        mapped = isin_mapper.get(isin_val, {}) if isin_val else {}

        ctx["isin"] = isin_val
        ctx["prodcode"] = str(mapped.get("prodcode") or raw_prodcode or "")
        ctx["fund_name"] = fund_name
        ctx["purchase_mode"] = mapped.get("purchase_mode") or purchase_mode
        ctx["option"] = mapped.get("option") or option

        adv_match = re.search(r"Advisor:\s*([A-Za-z0-9\-]+)", header_text)
        ctx["brokcode"] = adv_match.group(1) if adv_match else ("DIRECT" if ctx["purchase_mode"] == "Direct" else None)

        in_scheme_section = True
        scheme_start_record_idx = len(records)

    for idx, line in enumerate(merged_lines):
        folio_match = re.search(r"Folio No:\s*([A-Za-z0-9/]+)", line)
        pan_match = re.search(r"PAN:\s*([A-Z]{5}[0-9]{4}[A-Z])", line)

        if folio_match:
            in_scheme_section = False
            ctx["isin"] = None
            ctx["prodcode"] = None
            ctx["fund_name"] = None
            ctx["purchase_mode"] = None
            ctx["option"] = None
            ctx["brokcode"] = None

            ctx["folio_no"] = folio_match.group(1).strip()
            if pan_match:
                ctx["pan"] = pan_match.group(1).strip()
            else:
                for offset in (-1, 1, 2):
                    if 0 <= idx + offset < len(merged_lines):
                        pm = re.search(r"PAN:\s*([A-Z]{5}[0-9]{4}[A-Z])", merged_lines[idx + offset])
                        if pm:
                            ctx["pan"] = pm.group(1).strip()
                            break

            if idx + 1 < len(merged_lines):
                cand_name = merged_lines[idx + 1]
                if not is_valid_scheme_header_line(cand_name) and "ISIN:" not in cand_name:
                    ctx["inv_name"] = re.sub(r"\s+", " ", cand_name).strip()

        if is_valid_scheme_header_line(line):
            apply_scheme_header(line)
            continue

        # Handle delayed ISIN line (e.g., Mahindra Manulife where ISIN appears after transactions)
        has_isin_tag = "ISIN:" in line or bool(ISIN_REGEX.search(line))
        if has_isin_tag and in_scheme_section and not ctx["isin"]:
            isin_m = re.search(r"ISIN:\s*([A-Z0-9]{12})", line, re.IGNORECASE) or ISIN_REGEX.search(line)
            if isin_m:
                delayed_isin = isin_m.group(1).strip().upper()
                ctx["isin"] = delayed_isin
                mapped = isin_mapper.get(delayed_isin, {})
                if mapped.get("purchase_mode"):
                    ctx["purchase_mode"] = mapped["purchase_mode"]
                if mapped.get("option"):
                    ctx["option"] = mapped["option"]

                for r_idx in range(scheme_start_record_idx, len(records)):
                    rec = records[r_idx]
                    rec["isin"] = delayed_isin
                    if mapped.get("purchase_mode"):
                        rec["purchase_mode"] = mapped["purchase_mode"]
                    if mapped.get("option"):
                        rec["option"] = mapped["option"]
                    new_trxnno, new_txn_id = resolve_trxnno_and_txn_id(
                        folio_no=rec["folio_no"],
                        raw_desc=rec["_raw_desc"],
                        purprice=rec["purprice"],
                        isin=delayed_isin,
                        traddate=rec["traddate"],
                        txn_code=rec["txn_code"],
                        amount=rec["amount"],
                        units=rec["units"],
                        seq=rec["_seq"],
                    )
                    rec["trxnno"] = new_trxnno
                    rec["txn_id"] = new_txn_id
            continue

        if line.startswith("Closing Unit Balance:"):
            in_scheme_section = False
            continue

        if in_scheme_section:
            parsed_date = parse_cas_date(line)
            if not parsed_date:
                continue

            traddate, rest = parsed_date

            if (
                "Stamp Duty" in rest
                or "STT Paid" in rest
                or rest.startswith("***")
                or rest.startswith("*Stamp")
                or "Consolidation In" in rest
            ):
                continue

            num_tokens = re.findall(r"\(?[\d,]+\.\d+\)?(?:\(\))?", rest)
            if len(num_tokens) < 3:
                continue

            first_num_pos = rest.find(num_tokens[0])
            raw_desc = rest[:first_num_pos].strip(" |-")

            amount_val = parse_positive_number(num_tokens[0])
            units_val = parse_positive_number(num_tokens[1])
            price_val = round(parse_positive_number(num_tokens[2]) or 0.0, 4)

            if amount_val is None or units_val is None:
                continue

            txn_type, txn_code = normalize_transaction_type(raw_desc)
            trxnstat = derive_trxnstat(raw_desc)

            if "reversal" in raw_desc.lower() or "reversed" in raw_desc.lower():
                rev_remark = raw_desc
            else:
                rev_remark = "Remark: Source-CAS"

            isin_for_sig = ctx["isin"] or f"MISSING_{ctx['prodcode'] or ctx['folio_no']}"
            base_sig = f"{ctx['folio_no']}|{isin_for_sig}|{traddate}|{txn_code}|{amount_val:.2f}|{units_val:.4f}"
            seq = occurrence_counter.get(base_sig, 0) + 1
            occurrence_counter[base_sig] = seq

            trxnno, txn_id = resolve_trxnno_and_txn_id(
                folio_no=ctx["folio_no"],
                raw_desc=raw_desc,
                purprice=price_val,
                isin=isin_for_sig,
                traddate=traddate,
                txn_code=txn_code,
                amount=amount_val,
                units=units_val,
                seq=seq,
            )

            records.append(
                {
                    "pan": ctx["pan"],
                    "inv_name": ctx["inv_name"],
                    "folio_no": ctx["folio_no"],
                    "isin": ctx["isin"] or "",
                    "prodcode": ctx["prodcode"],
                    "fund_name": ctx["fund_name"],
                    "purchase_mode": ctx["purchase_mode"],
                    "option": ctx["option"],
                    "transaction_type": txn_type,
                    "txn_code": txn_code,
                    "trxnno": trxnno,
                    "trxnstat": trxnstat,
                    "traddate": traddate,
                    "postdate": traddate,
                    "purprice": price_val,
                    "units": units_val,
                    "amount": amount_val,
                    "brokcode": ctx["brokcode"],
                    "rev_remark": rev_remark,
                    "txn_id": txn_id,
                    "_raw_desc": raw_desc,
                    "_seq": seq,
                }
            )

    cleaned_records: List[Dict] = []
    seen_ids: Set[str] = set()
    for r in records:
        r.pop("_raw_desc", None)
        r.pop("_seq", None)
        if r["txn_id"] not in seen_ids:
            seen_ids.add(r["txn_id"])
            cleaned_records.append(r)

    # Apply the client name (inv_name) from the latest transaction per PAN to all rows for that PAN
    latest_name_by_pan: Dict[str, Tuple[str, int, str]] = {}
    for idx, r in enumerate(cleaned_records):
        pan = r.get("pan")
        name = (r.get("inv_name") or "").strip()
        tdate = r.get("traddate") or ""
        if pan and name:
            current_best = latest_name_by_pan.get(pan)
            if current_best is None or (tdate, idx) > (current_best[0], current_best[1]):
                latest_name_by_pan[pan] = (tdate, idx, name)

    for r in cleaned_records:
        pan = r.get("pan")
        if pan in latest_name_by_pan:
            r["inv_name"] = latest_name_by_pan[pan][2]

    return cleaned_records


# ---------------------------------------------------------
# 4. Step 2: Cross-Source Deduplicated Insert to rta_transactions
# ---------------------------------------------------------
def make_logical_fingerprint(folio_no: str, isin: str, traddate: str, txn_code: str, units: float, amount: float) -> str:
    return f"{str(folio_no).strip()}|{str(isin).strip()}|{traddate}|{txn_code}|{round(float(units), 3)}|{round(float(amount), 2)}"


def insert_new_transactions(supabase: Client, records: List[Dict]) -> Dict[str, int]:
    if not records:
        return {"parsed": 0, "inserted": 0, "duplicates_skipped": 0}

    invalid_rows = [
        r for r in records if not re.match(r"^INF[A-Z0-9]{9}$", str(r.get("isin") or "").strip().upper())
    ]
    if invalid_rows:
        sample_funds = sorted({r.get("fund_name") or r.get("folio_no") or "Unknown" for r in invalid_rows})
        raise ValueError(
            f"{len(invalid_rows)} transactions are missing a valid 12-character ISIN "
            f"({', '.join(sample_funds)}). Please fill in the ISIN in the table before uploading."
        )

    for r in records:
        r["isin"] = str(r["isin"]).strip().upper()
        if str(r.get("trxnno", "")).startswith("CAS"):
            r["txn_id"] = f"{str(r['folio_no']).strip()}-{r['trxnno']}-{round(float(r['purprice']), 4)}"

    folios = list({r["folio_no"] for r in records if r.get("folio_no")})

    existing_txn_ids: Set[str] = set()
    existing_fingerprints: Set[str] = set()

    for i in range(0, len(folios), 50):
        folio_chunk = folios[i : i + 50]
        offset = 0
        while True:
            resp = (
                supabase.table("rta_transactions")
                .select("txn_id,folio_no,isin,traddate,txn_code,units,amount")
                .in_("folio_no", folio_chunk)
                .range(offset, offset + 999)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                break
            for row in rows:
                existing_txn_ids.add(row["txn_id"])
                if all(row.get(k) is not None for k in ("folio_no", "isin", "traddate", "txn_code", "units", "amount")):
                    existing_fingerprints.add(
                        make_logical_fingerprint(
                            row["folio_no"],
                            row["isin"],
                            row["traddate"],
                            row["txn_code"],
                            row["units"],
                            row["amount"],
                        )
                    )
            offset += 1000

    new_records = []
    for r in records:
        fp = make_logical_fingerprint(
            r["folio_no"], r["isin"], r["traddate"], r["txn_code"], r["units"], r["amount"]
        )
        if r["txn_id"] in existing_txn_ids or fp in existing_fingerprints:
            continue
        new_records.append(r)
        existing_txn_ids.add(r["txn_id"])
        existing_fingerprints.add(fp)

    chunk_size = 200
    for i in range(0, len(new_records), chunk_size):
        batch = new_records[i : i + chunk_size]
        supabase.table("rta_transactions").upsert(
            batch, on_conflict="txn_id", ignore_duplicates=True
        ).execute()

    return {
        "parsed": len(records),
        "inserted": len(new_records),
        "duplicates_skipped": len(records) - len(new_records),
    }


# ---------------------------------------------------------
# 5. Step 3: Automatic isin_mapper Refresh Pipeline
# ---------------------------------------------------------
def clean_manager_names(x: Any) -> List[str]:
    if isinstance(x, list):
        return [d["value"] for d in x if isinstance(d, dict) and "value" in d]
    elif isinstance(x, str):
        try:
            parsed = ast.literal_eval(x)
            return [d["value"] for d in parsed if isinstance(d, dict) and "value" in d]
        except Exception:
            return [x] if x.strip() else []
    return []


def refresh_isin_mapper(supabase: Client) -> Dict[str, Any]:
    rtaTXN = fetch_all_rows(supabase, "rta_transactions")
    if rtaTXN.empty or "isin" not in rtaTXN.columns:
        return {"mapper_rows_updated": 0, "missing_in_fund_details": []}

    fundDetails = fetch_all_rows(supabase, "fund_details")

    mapData = rtaTXN[["prodcode", "isin"]].dropna(subset=["isin"]).copy()
    mapData["isin"] = mapData["isin"].astype(str).str.strip()
    mapData = mapData[mapData["isin"] != ""]
    mapData = mapData.drop_duplicates(["prodcode", "isin"], keep="first")

    if fundDetails.empty:
        df = mapData.copy()
        missing_isins = sorted(df["isin"].unique().tolist())
    else:
        fundDetails = fundDetails.copy()
        fundDetails["isin"] = fundDetails["isin"].astype(str).str.strip()
        fundDetails = fundDetails.drop_duplicates(["isin"], keep="first")

        known_fd_isins = set(fundDetails["isin"].dropna())
        missing_isins = sorted([i for i in mapData["isin"].unique() if i not in known_fd_isins])

        df = mapData.merge(fundDetails, on="isin", how="left")

    if "manager_name" in df.columns:
        df["manager_name"] = df["manager_name"].apply(clean_manager_names)

    if "purchase_mode" in df.columns:
        df["purchase_mode"] = df["purchase_mode"].replace({
            "Direct Mode": "Direct",
            "Distributor Mode": "Regular",
        })

    if "option" in df.columns:
        df["option"] = df["option"].replace({
            "Acc": "Growth",
            "Inc": "IDCW",
        })

    df = df.replace({np.nan: None})
    records = df.to_dict(orient="records")

    supabase.table("isin_mapper").delete().neq("isin", "").execute()

    chunk_size = 200
    for i in range(0, len(records), chunk_size):
        batch = records[i : i + chunk_size]
        supabase.table("isin_mapper").insert(batch).execute()

    return {
        "mapper_rows_updated": len(records),
        "missing_in_fund_details": missing_isins,
    }


# ---------------------------------------------------------
# 6. Flask Routes
# ---------------------------------------------------------

@cas_bp.route("/cas-upload/preview", methods=["POST"])
def cas_preview():
    if "cas_file" not in request.files:
        return jsonify({"error": "No PDF file uploaded."}), 400

    pdf_file = request.files["cas_file"]
    password = request.form.get("password", "")

    if not pdf_file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Please upload a valid PDF file."}), 400

    try:
        pages = extract_pages_text(pdf_file.read(), password)
        try:
            sb = get_supabase_client()
            mapper, prodcode_map, fund_catalog = fetch_reference_lookups(sb)
        except Exception:
            mapper, prodcode_map, fund_catalog = {}, {}, []

        records = parse_cas_to_records(pages, isin_mapper=mapper, prodcode_to_isin=prodcode_map)
        if not records:
            return jsonify({"error": "No transactions found. Ensure this is a detailed CAS."}), 400

        missing_isin_count = sum(
            1 for r in records if not re.match(r"^INF[A-Z0-9]{9}$", str(r.get("isin") or ""))
        )

        return jsonify({
            "count": len(records),
            "missing_isin_count": missing_isin_count,
            "fund_catalog": fund_catalog,
            "records": records,
        })
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to parse CAS PDF: {str(e)}"}), 500


@cas_bp.route("/cas-upload/commit", methods=["POST"])
def cas_commit():
    payload = request.get_json(silent=True)
    if not payload or "records" not in payload:
        return jsonify({"error": "Invalid request payload."}), 400

    try:
        supabase = get_supabase_client()
        records = payload["records"]

        # Step 1 & 2: Validate ISINs & deduplicated insert into rta_transactions
        rta_stats = insert_new_transactions(supabase, records)

        # Step 3: Refresh isin_mapper from rta_transactions + fund_details
        mapper_stats = refresh_isin_mapper(supabase)

        return jsonify({
            "status": "success",
            "stats": rta_stats,
            "isin_mapper_stats": mapper_stats,
        })
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": f"Database operation failed: {str(e)}"}), 500


# ---------------------------------------------------------
# 7. Standalone Entrypoint
# ---------------------------------------------------------
if __name__ == "__main__":
    standalone_app = Flask(__name__)
    standalone_app.register_blueprint(cas_bp)

    @standalone_app.route("/")
    def index():
        return redirect(url_for("cas_bp.cas_upload_page"))

    standalone_app.run(debug=True, port=5001)
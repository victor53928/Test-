"""Collects revenue / operating income for KR-listed stocks via the DART Open API.

Requires a free API key from https://opendart.fss.or.kr (set DART_API_KEY in .env).
"""

import io
import json
import xml.etree.ElementTree as ET
import zipfile

import requests

from app.config import BASE_DIR, DART_API_KEY

CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
FINANCIALS_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"

CORP_CODE_CACHE = BASE_DIR / "data" / "corp_code_cache.json"
CORP_NAME_CACHE = BASE_DIR / "data" / "corp_name_cache.json"

REPORT_CODES = {
    1: "11013",  # 1분기보고서
    2: "11012",  # 반기보고서
    3: "11014",  # 3분기보고서
    4: "11011",  # 사업보고서(연간)
}


def _download_corp_code_map() -> dict:
    resp = requests.get(CORP_CODE_URL, params={"crtfc_key": DART_API_KEY}, timeout=30)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_bytes = zf.read("CORPCODE.xml")

    root = ET.fromstring(xml_bytes)
    mapping = {}
    for item in root.iter("list"):
        stock_code = item.findtext("stock_code", "").strip()
        corp_code = item.findtext("corp_code", "").strip()
        if stock_code:
            mapping[stock_code] = corp_code
    return mapping


def get_corp_code_map() -> dict:
    """Returns {stock_code: corp_code}, using a local cache to avoid re-downloading."""
    if CORP_CODE_CACHE.exists():
        return json.loads(CORP_CODE_CACHE.read_text())

    mapping = _download_corp_code_map()
    CORP_CODE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    CORP_CODE_CACHE.write_text(json.dumps(mapping, ensure_ascii=False))
    return mapping


def _download_corp_name_map() -> dict:
    resp = requests.get(CORP_CODE_URL, params={"crtfc_key": DART_API_KEY}, timeout=30)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_bytes = zf.read("CORPCODE.xml")

    root = ET.fromstring(xml_bytes)
    mapping = {}
    for item in root.iter("list"):
        stock_code = item.findtext("stock_code", "").strip()
        corp_name = item.findtext("corp_name", "").strip()
        if stock_code and corp_name:
            mapping[corp_name] = stock_code
    return mapping


def get_corp_name_map() -> dict:
    """Returns {corp_name: stock_code} for all KRX-listed companies, so the
    watchlist/sector "add by name" flow can resolve a name without the user
    knowing the ticker. Uses a local cache to avoid re-downloading."""
    if CORP_NAME_CACHE.exists():
        return json.loads(CORP_NAME_CACHE.read_text())

    mapping = _download_corp_name_map()
    CORP_NAME_CACHE.parent.mkdir(parents=True, exist_ok=True)
    CORP_NAME_CACHE.write_text(json.dumps(mapping, ensure_ascii=False))
    return mapping


def fetch_financials(corp_code: str, year: int, quarter: int):
    """Returns (revenue, operating_income) for the given corp_code/year/quarter, or (None, None)."""
    reprt_code = REPORT_CODES[quarter]
    resp = requests.get(
        FINANCIALS_URL,
        params={
            "crtfc_key": DART_API_KEY,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": reprt_code,
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()

    if body.get("status") != "000":
        return None, None

    revenue, operating_income = None, None
    # Prefer consolidated (CFS) statements, fall back to separate (OFS).
    entries = body.get("list", [])
    for fs_div_pref in ("CFS", "OFS"):
        for entry in entries:
            if entry.get("fs_div") != fs_div_pref:
                continue
            if entry.get("sj_div") not in ("IS", "CIS"):
                continue
            amount = entry.get("thstrm_amount", "").replace(",", "")
            if not amount:
                continue
            if entry.get("account_nm") == "매출액" and revenue is None:
                revenue = float(amount)
            elif entry.get("account_nm") == "영업이익" and operating_income is None:
                operating_income = float(amount)
        if revenue is not None or operating_income is not None:
            break

    return revenue, operating_income

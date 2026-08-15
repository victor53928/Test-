"""KR stock data via Naver Finance (finance.naver.com) web scraping, used
instead of pykrx/KRX. Some networks can reach Naver but not KRX's own
data.krx.co.kr directly, so this is an alternate KR data path.

Not an official API -- if Naver changes their page/response format this
will need adjusting. Each function fails loudly (raises) rather than
silently returning wrong numbers, so a parsing break is visible instead
of showing a plausible-looking but incorrect value.

Naver doesn't publish a historical daily market-cap series, so historical
market cap is approximated as close x shares-outstanding (same approach
already used for US/JP stocks via yfinance elsewhere in this app), assuming
shares outstanding is roughly constant over the window.
"""

import ast
import datetime
import html
import re

import requests

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
_HEADERS = {"User-Agent": USER_AGENT}

SISE_JSON_URL = "https://api.finance.naver.com/siseJson.naver"
MAIN_PAGE_URL = "https://finance.naver.com/item/main.naver"


def fetch_daily_ohlcv(ticker: str, days: int) -> list:
    """Returns [(date_str, close, volume), ...] oldest first."""
    today = datetime.date.today()
    params = {
        "symbol": ticker,
        "requestType": 1,
        "startTime": (today - datetime.timedelta(days=days)).strftime("%Y%m%d"),
        "endTime": today.strftime("%Y%m%d"),
        "timeframe": "day",
    }
    resp = requests.get(SISE_JSON_URL, params=params, headers=_HEADERS, timeout=10)
    resp.raise_for_status()

    try:
        rows = ast.literal_eval(resp.text.strip())
    except (SyntaxError, ValueError) as e:
        raise ValueError(f"네이버 시세 응답을 해석하지 못했습니다 (형식이 바뀌었을 수 있음): {e}")

    if not rows or len(rows) < 2:
        return []

    header = rows[0]
    try:
        idx_date = header.index("날짜")
        idx_close = header.index("종가")
        idx_volume = header.index("거래량")
    except ValueError as e:
        raise ValueError(f"네이버 시세 응답의 컬럼 구성이 예상과 다릅니다: {header} ({e})")

    results = []
    for row in rows[1:]:
        date_raw = str(row[idx_date]).strip()
        if not date_raw or len(date_raw) != 8:
            continue
        date_str = f"{date_raw[0:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
        results.append((date_str, float(row[idx_close]), int(row[idx_volume])))
    return results


def _extract_snippet(page_html: str, label: str, window: int = 400) -> str:
    """Returns the text right after `label` (stripped of HTML tags). Starts
    *after* the label itself -- some labels (e.g. "52주최고") contain digits
    that would otherwise be mistaken for the value being looked up."""
    idx = page_html.find(label)
    if idx == -1:
        raise ValueError(f"'{label}' 항목을 페이지에서 찾지 못했습니다 (네이버 페이지 구조가 바뀌었을 수 있습니다).")
    start = idx + len(label)
    snippet = page_html[start : start + window]
    text = re.sub(r"<[^>]+>", " ", snippet)
    return html.unescape(text)


def _parse_won_amount(text: str):
    """Parses a Korean-notation amount like '424조 1,760억원' (or a plain
    억원-unit number like '1,234,567') into a won amount. Returns None if
    no number is found."""
    text = text.replace(",", "")
    jo_match = re.search(r"(\d+)\s*조", text)
    eok_match = re.search(r"(\d+)\s*억", text)
    if jo_match or eok_match:
        jo = int(jo_match.group(1)) if jo_match else 0
        eok = int(eok_match.group(1)) if eok_match else 0
        return (jo * 10_000 + eok) * 100_000_000
    num_match = re.search(r"(\d+)", text)
    if num_match:
        return int(num_match.group(1)) * 100_000_000  # bare number is already in 억원 units
    return None


def _parse_first_number(text: str):
    match = re.search(r"-?\d[\d,]*\.?\d*", text)
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def fetch_market_summary(ticker: str) -> dict:
    """Returns {"market_cap","shares_outstanding","per","pbr","eps","bps",
    "week52_high","week52_low"}. Fields that can't be parsed are None
    individually rather than failing the whole call."""
    resp = requests.get(MAIN_PAGE_URL, params={"code": ticker}, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    page = resp.text

    result = {
        "market_cap": None,
        "shares_outstanding": None,
        "per": None,
        "pbr": None,
        "eps": None,
        "bps": None,
        "dividend_yield": None,
        "dps": None,
        "week52_high": None,
        "week52_low": None,
    }

    try:
        result["market_cap"] = _parse_won_amount(_extract_snippet(page, "시가총액"))
    except Exception:
        pass

    try:
        shares_text = _extract_snippet(page, "상장주식수")
        shares = _parse_first_number(shares_text)
        result["shares_outstanding"] = int(shares) if shares else None
    except Exception:
        pass

    try:
        result["per"] = _parse_first_number(_extract_snippet(page, "PER", window=200))
    except Exception:
        pass

    try:
        result["pbr"] = _parse_first_number(_extract_snippet(page, "PBR", window=200))
    except Exception:
        pass

    try:
        result["eps"] = _parse_first_number(_extract_snippet(page, "EPS", window=200))
    except Exception:
        pass

    try:
        result["bps"] = _parse_first_number(_extract_snippet(page, "BPS", window=200))
    except Exception:
        pass

    try:
        result["dividend_yield"] = _parse_first_number(_extract_snippet(page, "배당수익률", window=200))
    except Exception:
        pass

    try:
        result["dps"] = _parse_first_number(_extract_snippet(page, "주당배당금", window=200))
    except Exception:
        pass

    # Extracted as two separate targeted lookups rather than "grab the next
    # two numbers after 52주최고" -- the "52주최저" label appearing shortly
    # after also starts with digits ("52"), which a combined scan would
    # mistake for the low value itself.
    try:
        result["week52_high"] = _parse_first_number(_extract_snippet(page, "52주최고", window=200))
    except Exception:
        pass

    try:
        result["week52_low"] = _parse_first_number(_extract_snippet(page, "52주최저", window=200))
    except Exception:
        pass

    return result

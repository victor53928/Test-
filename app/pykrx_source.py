"""KR stock data via pykrx -- pulls directly from KRX, so it's the most
accurate source for domestic price/market-cap/fundamental data. Tried first
by app/kr_data_source.py, which falls back to app/naver_finance.py (screen-
scraped, less authoritative but more resilient) if this fails. pykrx works
with an anonymous session (no KRX_ID/KRX_PW needed) -- the "KRX 로그인 실패"
message it prints at import time is informational, not a real error.

Ticker is the 6-digit KRX code (e.g. "005930"), no market suffix.
"""

import datetime

from pykrx import stock

# pykrx uses 0 (not NaN/None) to mean "not available" for these fundamental fields.
_FUNDAMENTAL_FIELDS = [
    ("PER", "per"),
    ("PBR", "pbr"),
    ("EPS", "eps"),
    ("BPS", "bps"),
    ("DIV", "dividend_yield"),
    ("DPS", "dps"),
]


def fetch_daily_ohlcv(ticker: str, days: int):
    """Returns [(date_str, close, volume), ...] for the last `days` days."""
    today = datetime.date.today()
    fromdate = (today - datetime.timedelta(days=days)).strftime("%Y%m%d")
    todate = today.strftime("%Y%m%d")
    df = stock.get_market_ohlcv_by_date(fromdate, todate, ticker)
    if df is None or df.empty:
        raise ValueError(f"{ticker}: pykrx에서 시세 데이터를 가져오지 못했습니다.")
    return [(idx.strftime("%Y-%m-%d"), float(row["종가"]), int(row["거래량"])) for idx, row in df.iterrows()]


def fetch_market_summary(ticker: str) -> dict:
    """Returns whatever of market_cap, shares_outstanding, per, pbr, eps,
    bps, dividend_yield, dps, week52_high, week52_low pykrx has -- each
    fetched independently so one failing block doesn't blank out the rest.
    Raises only if every block failed (nothing at all to return)."""
    today = datetime.date.today()
    recent_from = (today - datetime.timedelta(days=10)).strftime("%Y%m%d")
    todate = today.strftime("%Y%m%d")
    year_from = (today - datetime.timedelta(days=365)).strftime("%Y%m%d")

    result = {}

    try:
        cap_df = stock.get_market_cap_by_date(recent_from, todate, ticker)
        if cap_df is not None and not cap_df.empty:
            latest = cap_df.iloc[-1]
            result["market_cap"] = float(latest["시가총액"])
            result["shares_outstanding"] = float(latest["상장주식수"])
    except Exception:
        pass

    try:
        fund_df = stock.get_market_fundamental_by_date(recent_from, todate, ticker)
        if fund_df is not None and not fund_df.empty:
            latest = fund_df.iloc[-1]
            for field, key in _FUNDAMENTAL_FIELDS:
                value = float(latest[field])
                if value:
                    result[key] = value
    except Exception:
        pass

    try:
        year_df = stock.get_market_ohlcv_by_date(year_from, todate, ticker)
        if year_df is not None and not year_df.empty:
            result["week52_high"] = float(year_df["고가"].max())
            result["week52_low"] = float(year_df["저가"].min())
    except Exception:
        pass

    if not result:
        raise ValueError(f"{ticker}: pykrx에서 데이터를 가져오지 못했습니다.")
    return result

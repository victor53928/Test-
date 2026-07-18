"""Collects market cap, close price and trading volume for KR-listed stocks
via Naver Finance (see app/naver_finance.py), used instead of pykrx/KRX."""

import datetime

from app import naver_finance


def fetch_market_data(ticker: str, fromdate: str, todate: str):
    """Returns a list of (date, close, market_cap, volume) tuples for one ticker.

    fromdate/todate are 'YYYYMMDD' strings; only their span (todate - fromdate)
    is used, since Naver's daily-price endpoint is queried by day count.
    Close/volume and market cap are fetched independently: if the market-cap
    lookup fails, that day's close/volume is still kept (with market_cap
    approximated from shares outstanding, or None) instead of the whole
    ticker being dropped.
    """
    days = (
        datetime.datetime.strptime(todate, "%Y%m%d") - datetime.datetime.strptime(fromdate, "%Y%m%d")
    ).days + 1
    rows = naver_finance.fetch_daily_ohlcv(ticker, days)
    if not rows:
        return []

    shares = None
    try:
        summary = naver_finance.fetch_market_summary(ticker)
        shares = summary.get("shares_outstanding")
    except Exception:
        pass  # market cap is a nice-to-have; close/volume below still work without it

    return [
        (date_str, close, (close * shares) if shares else None, volume)
        for date_str, close, volume in rows
    ]

"""Single entry point for KR stock price/fundamental data: tries pykrx
(app/pykrx_source.py -- pulls directly from KRX, most accurate) first, and
falls back to Naver Finance scraping (app/naver_finance.py) only if pykrx
fails for some reason. live_price.py, fundamentals.py, and
collectors/krx_collector.py all go through this module instead of importing
pykrx_source/naver_finance directly, so there's exactly one fallback policy
to reason about.
"""

from app import naver_finance, pykrx_source


def fetch_daily_ohlcv(ticker: str, days: int):
    try:
        rows = pykrx_source.fetch_daily_ohlcv(ticker, days)
        if rows:
            return rows
    except Exception:
        pass
    return naver_finance.fetch_daily_ohlcv(ticker, days)


def fetch_market_summary(ticker: str) -> dict:
    try:
        summary = pykrx_source.fetch_market_summary(ticker)
        if summary:
            return summary
    except Exception:
        pass
    return naver_finance.fetch_market_summary(ticker)

"""Entrypoint: populate the local DB with KR + US stock market data and financials.

Usage:
    python -m app.collectors.run_collection
"""

import datetime
import time

from app.collectors import dart_collector, krx_collector, price_collector, us_collector
from app.config import DART_API_KEY
from app.db import (
    get_all_sector_stocks,
    get_conn,
    init_db,
    seed_sector_stocks_if_empty,
    upsert_financials,
    upsert_market_data,
    upsert_price,
    upsert_stock,
)
from app.sectors import BONDS, COMMODITIES, SECTORS

# 10 years, to cover the longest selectable chart period (10년) in the dashboard.
MARKET_DATA_LOOKBACK_DAYS = 3650


def _tickers_by_market(conn, market):
    """Reads sector membership from the (UI-editable) sector_stocks table rather
    than the static sectors.py defaults, so stocks added/removed via the
    산업군별 page are picked up by the next batch collection run too."""
    return [
        (row["ticker"], row["name"], row["sector_key"])
        for row in get_all_sector_stocks(conn)
        if row["market"] == market
    ]


def collect_kr_market_data():
    today = datetime.date.today()
    fromdate = (today - datetime.timedelta(days=MARKET_DATA_LOOKBACK_DAYS)).strftime("%Y%m%d")
    todate = today.strftime("%Y%m%d")

    with get_conn() as conn:
        for ticker, name, sector_key in _tickers_by_market(conn, "KR"):
            try:
                upsert_stock(conn, ticker, name, sector_key, "KR")
                rows = krx_collector.fetch_market_data(ticker, fromdate, todate)
            except Exception as e:
                print(f"[kr market_data] {ticker} {name}: failed ({e})")
                continue
            for date, close, market_cap, volume in rows:
                upsert_market_data(conn, ticker, date, close, market_cap, volume)
            print(f"[kr market_data] {ticker} {name}: {len(rows)} rows")
            time.sleep(0.2)  # be polite to KRX


def collect_kr_financials():
    if not DART_API_KEY:
        print("[kr financials] DART_API_KEY not set in .env, skipping.")
        return

    corp_map = dart_collector.get_corp_code_map()
    current_year = datetime.date.today().year

    with get_conn() as conn:
        for ticker, name, sector_key in _tickers_by_market(conn, "KR"):
            corp_code = corp_map.get(ticker)
            if not corp_code:
                print(f"[kr financials] {ticker} {name}: no DART corp_code found")
                continue
            for year in (current_year - 1, current_year):
                for quarter in (1, 2, 3, 4):
                    revenue, operating_income = dart_collector.fetch_financials(corp_code, year, quarter)
                    if revenue is not None or operating_income is not None:
                        upsert_financials(conn, ticker, year, quarter, revenue, operating_income)
                        print(f"[kr financials] {ticker} {name} {year}Q{quarter}: revenue={revenue}, op_income={operating_income}")
                    time.sleep(0.2)


def collect_us_market_data():
    with get_conn() as conn:
        for ticker, name, sector_key in _tickers_by_market(conn, "US"):
            try:
                upsert_stock(conn, ticker, name, sector_key, "US")
                rows = us_collector.fetch_market_data(ticker, period=f"{MARKET_DATA_LOOKBACK_DAYS}d")
            except Exception as e:
                print(f"[us market_data] {ticker} {name}: failed ({e})")
                continue
            for date, close, market_cap, volume in rows:
                upsert_market_data(conn, ticker, date, close, market_cap, volume)
            print(f"[us market_data] {ticker} {name}: {len(rows)} rows")


def collect_us_financials():
    with get_conn() as conn:
        for ticker, name, sector_key in _tickers_by_market(conn, "US"):
            try:
                results = us_collector.fetch_financials(ticker)
            except Exception as e:
                print(f"[us financials] {ticker} {name}: failed ({e})")
                continue
            for year, quarter, revenue, operating_income in results:
                upsert_financials(conn, ticker, year, quarter, revenue, operating_income)
            print(f"[us financials] {ticker} {name}: {len(results)} quarters")


def collect_jp_market_data():
    # Japan tickers (e.g. 7203.T) are plain yfinance tickers, so the generic
    # us_collector fetch logic (yfinance-based, nothing US-specific in it)
    # works unchanged here.
    with get_conn() as conn:
        for ticker, name, sector_key in _tickers_by_market(conn, "JP"):
            try:
                upsert_stock(conn, ticker, name, sector_key, "JP")
                rows = us_collector.fetch_market_data(ticker, period=f"{MARKET_DATA_LOOKBACK_DAYS}d")
            except Exception as e:
                print(f"[jp market_data] {ticker} {name}: failed ({e})")
                continue
            for date, close, market_cap, volume in rows:
                upsert_market_data(conn, ticker, date, close, market_cap, volume)
            print(f"[jp market_data] {ticker} {name}: {len(rows)} rows")


def collect_jp_financials():
    with get_conn() as conn:
        for ticker, name, sector_key in _tickers_by_market(conn, "JP"):
            try:
                results = us_collector.fetch_financials(ticker)
            except Exception as e:
                print(f"[jp financials] {ticker} {name}: failed ({e})")
                continue
            for year, quarter, revenue, operating_income in results:
                upsert_financials(conn, ticker, year, quarter, revenue, operating_income)
            print(f"[jp financials] {ticker} {name}: {len(results)} quarters")


def collect_commodities():
    with get_conn() as conn:
        for symbol, name in COMMODITIES:
            try:
                rows = price_collector.fetch_price_history(symbol, period=f"{MARKET_DATA_LOOKBACK_DAYS}d")
            except Exception as e:
                print(f"[commodities] {symbol} {name}: failed ({e})")
                continue
            for date, close in rows:
                upsert_price(conn, "commodity_prices", symbol, date, close)
            print(f"[commodities] {symbol} {name}: {len(rows)} rows")


def collect_bonds():
    with get_conn() as conn:
        for symbol, name in BONDS:
            try:
                rows = price_collector.fetch_price_history(symbol, period=f"{MARKET_DATA_LOOKBACK_DAYS}d")
            except Exception as e:
                print(f"[bonds] {symbol} {name}: failed ({e})")
                continue
            for date, close in rows:
                upsert_price(conn, "bond_prices", symbol, date, close)
            print(f"[bonds] {symbol} {name}: {len(rows)} rows")


if __name__ == "__main__":
    init_db()
    with get_conn() as conn:
        seed_sector_stocks_if_empty(conn, SECTORS)
    collect_kr_market_data()
    collect_kr_financials()
    collect_us_market_data()
    collect_us_financials()
    collect_jp_market_data()
    collect_jp_financials()
    collect_commodities()
    collect_bonds()

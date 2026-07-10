"""Phase 1 entrypoint: populate the local DB with KR stock market data and financials.

Usage:
    python -m app.collectors.run_collection
"""

import datetime
import time

from app.collectors import dart_collector, krx_collector
from app.config import DART_API_KEY
from app.db import get_conn, init_db, upsert_financials, upsert_market_data, upsert_stock
from app.sectors import all_kr_tickers

MARKET_DATA_LOOKBACK_DAYS = 90


def collect_market_data():
    today = datetime.date.today()
    fromdate = (today - datetime.timedelta(days=MARKET_DATA_LOOKBACK_DAYS)).strftime("%Y%m%d")
    todate = today.strftime("%Y%m%d")

    with get_conn() as conn:
        for ticker, name, sector_key in all_kr_tickers():
            upsert_stock(conn, ticker, name, sector_key, "KR")
            try:
                rows = krx_collector.fetch_market_data(ticker, fromdate, todate)
            except Exception as e:
                print(f"[market_data] {ticker} {name}: failed ({e})")
                continue
            for date, close, market_cap, volume in rows:
                upsert_market_data(conn, ticker, date, close, market_cap, volume)
            print(f"[market_data] {ticker} {name}: {len(rows)} rows")
            time.sleep(0.2)  # be polite to KRX


def collect_financials():
    if not DART_API_KEY:
        print("[financials] DART_API_KEY not set in .env, skipping.")
        return

    corp_map = dart_collector.get_corp_code_map()
    current_year = datetime.date.today().year

    with get_conn() as conn:
        for ticker, name, sector_key in all_kr_tickers():
            corp_code = corp_map.get(ticker)
            if not corp_code:
                print(f"[financials] {ticker} {name}: no DART corp_code found")
                continue
            for year in (current_year - 1, current_year):
                for quarter in (1, 2, 3, 4):
                    revenue, operating_income = dart_collector.fetch_financials(corp_code, year, quarter)
                    if revenue is not None or operating_income is not None:
                        upsert_financials(conn, ticker, year, quarter, revenue, operating_income)
                        print(f"[financials] {ticker} {name} {year}Q{quarter}: revenue={revenue}, op_income={operating_income}")
                    time.sleep(0.2)


if __name__ == "__main__":
    init_db()
    collect_market_data()
    collect_financials()

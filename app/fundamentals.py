"""PER/PBR valuation and multi-year revenue/operating income trend for watchlist entries.

KR data comes from pykrx (PER/PBR) and DART (revenue/operating income, up to
10 years of annual reports, requires DART_API_KEY). US/JP data comes from
yfinance; free-tier annual financials there typically only go back ~4 years,
which is a data-source limitation, not a bug.
"""

import datetime
import time

import pandas as pd
import yfinance as yf
from pykrx import stock

from app.collectors import dart_collector
from app.config import DART_API_KEY

MAX_TREND_YEARS = 10


def get_valuation(ticker: str, market: str) -> dict:
    """Returns {"per": float|None, "pbr": float|None}."""
    if market in ("KOSPI", "KOSDAQ"):
        return _get_kr_valuation(ticker)
    return _get_yf_valuation(ticker)


def _get_kr_valuation(ticker: str) -> dict:
    today = datetime.date.today()
    fromdate = (today - datetime.timedelta(days=14)).strftime("%Y%m%d")
    todate = today.strftime("%Y%m%d")

    df = stock.get_market_fundamental_by_date(fromdate, todate, ticker)
    if df.empty:
        return {"per": None, "pbr": None}

    latest = df.iloc[-1]
    per = float(latest["PER"]) if latest.get("PER") else None
    pbr = float(latest["PBR"]) if latest.get("PBR") else None
    return {"per": per, "pbr": pbr}


def _get_yf_valuation(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return {"per": None, "pbr": None}
    return {"per": info.get("trailingPE"), "pbr": info.get("priceToBook")}


def get_financial_trend(ticker: str, market: str) -> list:
    """Returns up to MAX_TREND_YEARS of {"year", "revenue", "operating_income"}, oldest first."""
    if market in ("KOSPI", "KOSDAQ"):
        return _get_kr_financial_trend(ticker)
    return _get_yf_financial_trend(ticker)


def _get_kr_financial_trend(ticker: str) -> list:
    if not DART_API_KEY:
        return []

    corp_map = dart_collector.get_corp_code_map()
    corp_code = corp_map.get(ticker)
    if not corp_code:
        return []

    current_year = datetime.date.today().year
    results = []
    for year in range(current_year - MAX_TREND_YEARS + 1, current_year + 1):
        revenue, operating_income = dart_collector.fetch_financials(corp_code, year, 4)  # 4 -> annual report
        if revenue is not None or operating_income is not None:
            results.append({"year": year, "revenue": revenue, "operating_income": operating_income})
        time.sleep(0.2)  # be polite to DART
    return results


def _get_yf_financial_trend(ticker: str) -> list:
    t = yf.Ticker(ticker)
    stmt = t.financials  # annual income statement, columns = fiscal year-end dates
    if stmt is None or stmt.empty:
        return []

    results = []
    for col in stmt.columns:
        revenue = stmt.loc["Total Revenue", col] if "Total Revenue" in stmt.index else None
        operating_income = stmt.loc["Operating Income", col] if "Operating Income" in stmt.index else None
        revenue = float(revenue) if pd.notna(revenue) else None
        operating_income = float(operating_income) if pd.notna(operating_income) else None
        results.append({"year": col.year, "revenue": revenue, "operating_income": operating_income})
    return sorted(results, key=lambda r: r["year"])

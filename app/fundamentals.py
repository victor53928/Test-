"""Valuation (Yahoo-Finance-style detail) and multi-year revenue/operating
income trend for watchlist entries.

KR data comes from pykrx (valuation) and DART (revenue/operating income, up
to 10 years of annual reports, requires DART_API_KEY). US/JP data comes from
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

_EMPTY_VALUATION = {
    "market_cap": None,
    "per": None,
    "pbr": None,
    "eps": None,
    "bps": None,
    "dividend_yield": None,
    "dps": None,
    "week52_high": None,
    "week52_low": None,
    "avg_volume": None,
    "beta": None,
    "roe": None,
}


def get_valuation(ticker: str, market: str) -> dict:
    """Returns a Yahoo-Finance-style set of valuation metrics (see
    _EMPTY_VALUATION for the full key list). Each field is fetched
    independently, so one missing/failed field doesn't blank out the rest."""
    if market in ("KOSPI", "KOSDAQ"):
        return _get_kr_valuation(ticker)
    return _get_yf_valuation(ticker)


def _get_kr_valuation(ticker: str) -> dict:
    result = dict(_EMPTY_VALUATION)
    today = datetime.date.today()

    # PER/PBR/EPS/BPS/배당수익률/주당배당금 all come from one pykrx call.
    try:
        fromdate = (today - datetime.timedelta(days=14)).strftime("%Y%m%d")
        todate = today.strftime("%Y%m%d")
        df = stock.get_market_fundamental_by_date(fromdate, todate, ticker)
        if not df.empty:
            latest = df.iloc[-1]
            result["per"] = float(latest["PER"]) if latest.get("PER") else None
            result["pbr"] = float(latest["PBR"]) if latest.get("PBR") else None
            result["eps"] = float(latest["EPS"]) if latest.get("EPS") else None
            result["bps"] = float(latest["BPS"]) if latest.get("BPS") else None
            result["dividend_yield"] = float(latest["DIV"]) if latest.get("DIV") else None
            result["dps"] = float(latest["DPS"]) if latest.get("DPS") else None
            if result["eps"] and result["bps"]:
                result["roe"] = result["eps"] / result["bps"] * 100
    except Exception:
        pass

    # Market cap fetched independently -- must not depend on the fundamental
    # call above succeeding (KR stocks without published PER/PBR, e.g. due to
    # negative earnings, otherwise ended up with no market cap either).
    try:
        fromdate14 = (today - datetime.timedelta(days=14)).strftime("%Y%m%d")
        todate = today.strftime("%Y%m%d")
        cap_df = stock.get_market_cap_by_date(fromdate14, todate, ticker)
        if not cap_df.empty:
            result["market_cap"] = float(cap_df["시가총액"].iloc[-1])
    except Exception:
        pass

    # 52-week high/low + average volume, from a separate 1-year OHLCV pull.
    try:
        fromdate365 = (today - datetime.timedelta(days=365)).strftime("%Y%m%d")
        todate = today.strftime("%Y%m%d")
        ohlcv = stock.get_market_ohlcv_by_date(fromdate365, todate, ticker)
        if not ohlcv.empty:
            result["week52_high"] = float(ohlcv["고가"].max())
            result["week52_low"] = float(ohlcv["저가"].min())
            result["avg_volume"] = float(ohlcv["거래량"].mean())
    except Exception:
        pass

    return result


def _get_yf_valuation(ticker: str) -> dict:
    result = dict(_EMPTY_VALUATION)
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return result

    result["market_cap"] = info.get("marketCap")
    result["per"] = info.get("trailingPE")
    result["pbr"] = info.get("priceToBook")
    result["eps"] = info.get("trailingEps")
    result["bps"] = info.get("bookValue")
    result["dps"] = info.get("dividendRate")
    result["week52_high"] = info.get("fiftyTwoWeekHigh")
    result["week52_low"] = info.get("fiftyTwoWeekLow")
    result["avg_volume"] = info.get("averageVolume")
    result["beta"] = info.get("beta")

    raw_div_yield = info.get("dividendYield")
    if raw_div_yield is not None:
        result["dividend_yield"] = raw_div_yield * 100 if raw_div_yield < 1 else raw_div_yield

    raw_roe = info.get("returnOnEquity")
    if raw_roe is not None:
        result["roe"] = raw_roe * 100 if abs(raw_roe) < 1 else raw_roe

    return result


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

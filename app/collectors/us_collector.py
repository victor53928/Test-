"""Collects market cap, close price, volume and quarterly financials for US-listed
representative stocks via yfinance.

Note: yfinance does not expose historical market cap directly, so it is
approximated as close * current shares outstanding. This is a reasonable
approximation for tracking trend, but not exact for periods with major
buybacks/issuances.
"""

import pandas as pd
import yfinance as yf


def fetch_market_data(ticker: str, period: str = "90d"):
    """Returns a list of (date, close, market_cap, volume) tuples for one ticker."""
    t = yf.Ticker(ticker)
    hist = t.history(period=period)
    if hist.empty:
        return []

    try:
        shares = t.fast_info.get("shares")
    except Exception:
        shares = None

    rows = []
    for date, row in hist.iterrows():
        close = float(row["Close"])
        volume = int(row["Volume"])
        market_cap = close * shares if shares else None
        rows.append((date.strftime("%Y-%m-%d"), close, market_cap, volume))
    return rows


def fetch_financials(ticker: str):
    """Returns a list of (year, quarter, revenue, operating_income) from quarterly filings."""
    t = yf.Ticker(ticker)
    stmt = t.quarterly_income_stmt
    if stmt is None or stmt.empty:
        return []

    results = []
    for col in stmt.columns:
        year = col.year
        quarter = (col.month - 1) // 3 + 1
        revenue = stmt.loc["Total Revenue", col] if "Total Revenue" in stmt.index else None
        operating_income = stmt.loc["Operating Income", col] if "Operating Income" in stmt.index else None
        revenue = float(revenue) if pd.notna(revenue) else None
        operating_income = float(operating_income) if pd.notna(operating_income) else None
        results.append((year, quarter, revenue, operating_income))
    return results

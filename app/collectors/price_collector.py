"""Generic close-price history collector for commodities and bond proxies via yfinance."""

import yfinance as yf


def fetch_price_history(symbol: str, period: str = "90d"):
    """Returns a list of (date, close) tuples for one symbol."""
    hist = yf.Ticker(symbol).history(period=period)
    if hist.empty:
        return []
    return [(date.strftime("%Y-%m-%d"), float(row["Close"])) for date, row in hist.iterrows()]


def fetch_price_history_with_volume(symbol: str, period: str = "90d"):
    """Returns a list of (date, close, volume) tuples for one symbol. Some
    index tickers (e.g. ^KS11, ^N225) don't report meaningful volume via
    Yahoo Finance -- volume comes through as 0/NaN for those, in which case
    the caller gets None rather than a misleading 0."""
    hist = yf.Ticker(symbol).history(period=period)
    if hist.empty:
        return []
    return [
        (date.strftime("%Y-%m-%d"), float(row["Close"]), int(row["Volume"]) if row["Volume"] else None)
        for date, row in hist.iterrows()
    ]

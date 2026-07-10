"""Generic close-price history collector for commodities and bond proxies via yfinance."""

import yfinance as yf


def fetch_price_history(symbol: str, period: str = "90d"):
    """Returns a list of (date, close) tuples for one symbol."""
    hist = yf.Ticker(symbol).history(period=period)
    if hist.empty:
        return []
    return [(date.strftime("%Y-%m-%d"), float(row["Close"])) for date, row in hist.iterrows()]

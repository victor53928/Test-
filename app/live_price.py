"""Latest price + recent history for watchlist entries.

KR tickers (KOSPI/KOSDAQ) go through Naver Finance (see app/naver_finance.py);
US/JP tickers go through yfinance. "Latest" here means the most recent
close/quote available from these providers (refreshed on whatever cache TTL
the caller uses), not a tick-by-tick real-time feed.
"""

import pandas as pd
import yfinance as yf

from app import naver_finance

_CURRENCY_BY_MARKET = {"KOSPI": "KRW", "KOSDAQ": "KRW", "US": "USD", "JP": "JPY"}


def get_price_data(ticker: str, market: str, days: int = 90) -> dict:
    """Returns {latest_price, prev_close, change, change_pct, currency, market_cap, history}.

    `history` is a DataFrame with date/close/volume columns. `market_cap` is the
    latest market cap (KR only for now; None for US/JP since yfinance doesn't
    expose historical market cap directly).
    """
    if market in ("KOSPI", "KOSDAQ"):
        return _get_kr_price_data(ticker, days)
    if market in ("US", "JP"):
        return _get_yf_price_data(ticker, days, _CURRENCY_BY_MARKET[market])
    raise ValueError(f"unknown market: {market}")


def _summarize(dates, closes, volumes, currency, market_cap=None) -> dict:
    history = pd.DataFrame({"date": dates, "close": closes, "volume": volumes})
    latest_price = closes[-1] if closes else None
    prev_close = closes[-2] if len(closes) >= 2 else None
    change = (latest_price - prev_close) if (latest_price is not None and prev_close is not None) else None
    change_pct = (change / prev_close * 100) if (change is not None and prev_close) else None
    return {
        "latest_price": latest_price,
        "prev_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "currency": currency,
        "market_cap": market_cap,
        "history": history,
    }


def _get_kr_price_data(ticker: str, days: int) -> dict:
    rows = naver_finance.fetch_daily_ohlcv(ticker, days)
    if not rows:
        raise ValueError(f"{ticker}: 조회된 시세 데이터가 없습니다.")

    dates = [r[0] for r in rows]
    closes = [r[1] for r in rows]
    volumes = [r[2] for r in rows]

    summary = {}
    try:
        summary = naver_finance.fetch_market_summary(ticker)
    except Exception:
        pass  # market cap is a nice-to-have; price/volume above still work without it

    result = _summarize(dates, closes, volumes, "KRW", market_cap=summary.get("market_cap"))

    # Naver doesn't publish historical daily market cap; approximate it as
    # close * shares-outstanding (same approach used for US/JP below),
    # assuming shares outstanding is roughly constant over the window.
    shares = summary.get("shares_outstanding")
    if shares:
        result["history"]["market_cap"] = result["history"]["close"] * shares

    return result


def _get_yf_price_data(ticker: str, days: int, currency: str) -> dict:
    t = yf.Ticker(ticker)
    hist = t.history(period=f"{days}d")
    if hist.empty:
        raise ValueError(f"{ticker}: 조회된 시세 데이터가 없습니다.")

    dates = [d.strftime("%Y-%m-%d") for d in hist.index]
    closes = [float(v) for v in hist["Close"]]
    volumes = [int(v) for v in hist["Volume"]]
    result = _summarize(dates, closes, volumes, currency)

    try:
        fast_info = t.fast_info
        last_price = fast_info.get("last_price")
        previous_close = fast_info.get("previous_close")
        if last_price is not None:
            result["latest_price"] = float(last_price)
        if previous_close is not None:
            result["prev_close"] = float(previous_close)
        if result["latest_price"] is not None and result["prev_close"]:
            result["change"] = result["latest_price"] - result["prev_close"]
            result["change_pct"] = result["change"] / result["prev_close"] * 100
    except Exception:
        pass  # fall back to history-derived values already in `result`

    # Approximate per-day market cap as close * current shares outstanding,
    # same approach app/collectors/us_collector.py uses for batch collection
    # (yfinance doesn't expose historical market cap directly).
    try:
        shares = t.fast_info.get("shares")
        if shares:
            result["history"]["market_cap"] = result["history"]["close"] * shares
    except Exception:
        pass

    return result

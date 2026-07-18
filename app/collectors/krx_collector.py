"""Collects market cap, close price and trading volume for KR-listed stocks via pykrx."""

from pykrx import stock


def fetch_market_data(ticker: str, fromdate: str, todate: str):
    """Returns a list of (date, close, market_cap, volume) tuples for one ticker.

    fromdate/todate must be 'YYYYMMDD' strings. Close/volume (from
    get_market_ohlcv_by_date) and market cap (from get_market_cap_by_date)
    are fetched independently: if the market-cap call fails or comes back
    empty for a given day, that day's close/volume is still kept (with
    market_cap=None) instead of the whole ticker being dropped.
    """
    ohlcv_df = stock.get_market_ohlcv_by_date(fromdate, todate, ticker)
    if ohlcv_df.empty:
        return []

    cap_by_date = {}
    try:
        cap_df = stock.get_market_cap_by_date(fromdate, todate, ticker)
        cap_by_date = {date: float(row["시가총액"]) for date, row in cap_df.iterrows()}
    except Exception:
        pass  # market cap is a nice-to-have; close/volume below still work without it

    rows = []
    for date, ohlcv_row in ohlcv_df.iterrows():
        date_str = date.strftime("%Y-%m-%d")
        rows.append(
            (
                date_str,
                float(ohlcv_row["종가"]),
                cap_by_date.get(date),
                int(ohlcv_row["거래량"]),
            )
        )
    return rows

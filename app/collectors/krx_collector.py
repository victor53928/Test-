"""Collects market cap, close price and trading volume for KR-listed stocks via pykrx."""

from pykrx import stock


def fetch_market_data(ticker: str, fromdate: str, todate: str):
    """Returns a list of (date, close, market_cap, volume) tuples for one ticker.

    fromdate/todate must be 'YYYYMMDD' strings.
    """
    cap_df = stock.get_market_cap_by_date(fromdate, todate, ticker)
    ohlcv_df = stock.get_market_ohlcv_by_date(fromdate, todate, ticker)

    if cap_df.empty:
        return []

    rows = []
    for date, cap_row in cap_df.iterrows():
        date_str = date.strftime("%Y-%m-%d")
        close = float(ohlcv_df.loc[date, "종가"]) if date in ohlcv_df.index else None
        rows.append(
            (
                date_str,
                close,
                float(cap_row["시가총액"]),
                int(cap_row["거래량"]),
            )
        )
    return rows

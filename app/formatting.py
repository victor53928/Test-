"""Currency/number formatting and chart period helpers shared across pages."""

import datetime

CURRENCY_BY_MARKET = {"KR": "KRW", "US": "USD", "JP": "JPY"}
CURRENCY_SYMBOLS = {"KRW": "₩", "USD": "$", "JPY": "¥"}

# label -> lookback in days, used to filter an already-loaded history down to
# the selected window (data itself is collected up to PERIOD_OPTIONS's max).
PERIOD_OPTIONS = {
    "1주일": 7,
    "1개월": 30,
    "3개월": 90,
    "1년": 365,
    "3년": 365 * 3,
    "5년": 365 * 5,
    "10년": 365 * 10,
}
DEFAULT_PERIOD = "1년"


def format_money(value, currency: str, decimals: int = 0) -> str:
    """e.g. format_money(1234567, "KRW") -> '₩1,234,567'"""
    if value is None:
        return "N/A"
    symbol = CURRENCY_SYMBOLS.get(currency, "")
    return f"{symbol}{value:,.{decimals}f}"


def filter_by_period(df, date_column: str, period_label: str):
    """Returns rows of `df` whose `date_column` falls within the last N days
    for the selected period label (df is unfiltered/untouched if the column
    or label isn't recognized)."""
    if df.empty or period_label not in PERIOD_OPTIONS:
        return df
    cutoff = (datetime.date.today() - datetime.timedelta(days=PERIOD_OPTIONS[period_label])).strftime("%Y-%m-%d")
    return df[df[date_column] >= cutoff]

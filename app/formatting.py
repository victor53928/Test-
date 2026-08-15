"""Currency/number formatting and chart period helpers shared across pages."""

import datetime
import html

CURRENCY_BY_MARKET = {"KR": "KRW", "US": "USD", "JP": "JPY"}
CURRENCY_SYMBOLS = {"KRW": "₩", "USD": "$", "JPY": "¥"}
# Trailing unit word for format_money_korean -- "원" attaches directly (37조원),
# while "달러"/"엔" read more naturally with a leading space (260억 달러).
CURRENCY_KOREAN_UNIT_WORD = {"KRW": "원", "USD": " 달러", "JPY": " 엔"}

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


def format_money_korean(value, currency: str) -> str:
    """e.g. format_money_korean(37_100_000_000_000, "KRW") -> '37조 1,000억원'
    format_money_korean(26_000_000_000, "USD") -> '260억 달러'

    Korean convention groups large numbers by 조(10^12)/억(10^8) rather than
    thousands, so a plain comma-separated format_money() value like
    '₩37,100,000,000,000' is hard to read at a glance -- this reads it out in
    조/억 units instead. Falls back to format_money() under 1억, where 조/억
    grouping wouldn't apply anyway.
    """
    if value is None:
        return "N/A"
    if abs(value) < 10**8:
        return format_money(value, currency)

    unit_word = CURRENCY_KOREAN_UNIT_WORD.get(currency, "")
    sign = "-" if value < 0 else ""
    remaining = round(abs(value))
    jo, remaining = divmod(remaining, 10**12)
    eok = remaining // 10**8

    parts = []
    if jo:
        parts.append(f"{jo:,}조")
    if eok:
        parts.append(f"{eok:,}억")
    return f"{sign}{' '.join(parts)}{unit_word}"


def filter_by_period(df, date_column: str, period_label: str):
    """Returns rows of `df` whose `date_column` falls within the last N days
    for the selected period label (df is unfiltered/untouched if the column
    or label isn't recognized)."""
    if df.empty or period_label not in PERIOD_OPTIONS:
        return df
    cutoff = (datetime.date.today() - datetime.timedelta(days=PERIOD_OPTIONS[period_label])).strftime("%Y-%m-%d")
    return df[df[date_column] >= cutoff]


def right_aligned_table_html(df, right_align_cols=None) -> str:
    """Returns an HTML <table> string (for st.markdown(..., unsafe_allow_html=True))
    with the given columns right-aligned -- useful for comparing numbers at a
    glance. st.dataframe left-aligns any string-formatted column (e.g. our
    "₩1,234,567" values), and that isn't controllable via column_config once
    a currency symbol/comma formatting is baked into the string, so a plain
    HTML table is used instead for tables that are mostly about comparing
    numbers. Defaults to right-aligning every column if `right_align_cols`
    isn't given.
    """
    columns = list(df.columns)
    right_align_cols = set(columns if right_align_cols is None else right_align_cols)

    header_cells = "".join(
        f"<th style='text-align:{'right' if col in right_align_cols else 'left'};"
        f"padding:4px 12px;border-bottom:1px solid rgba(128,128,128,0.4);white-space:nowrap;'>"
        f"{html.escape(str(col))}</th>"
        for col in columns
    )

    body_rows = []
    for _, row in df.iterrows():
        cells = []
        for col in columns:
            align = "right" if col in right_align_cols else "left"
            value = "" if row[col] is None else html.escape(str(row[col]))
            cells.append(
                f"<td style='text-align:{align};padding:4px 12px;"
                f"border-bottom:1px solid rgba(128,128,128,0.15);white-space:nowrap;'>{value}</td>"
            )
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    return (
        "<div style='overflow-x:auto;'><table style='width:100%;border-collapse:collapse;'>"
        f"<thead><tr>{header_cells}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>"
    )

"""Bond prices / yields (US 10Y, TLT, KR govt bond ETF), split by currency.
Price and yield are combined into one dual-axis chart where both exist
(mixing a % yield and a $ price on one shared axis flattens the yield), and
kept as single-axis charts otherwise.

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import altair as alt
import pandas as pd
import streamlit as st

from app.db import get_conn
from app.formatting import DEFAULT_PERIOD, PERIOD_OPTIONS, filter_by_period, format_money, right_aligned_table_html
from app.sectors import BONDS
from app.theme import inject_theme

st.set_page_config(page_title="채권", layout="wide")
inject_theme()
st.title("채권 가격 / 금리")

name_map = dict(BONDS)
_KRW_BOND_SYMBOLS = {"148070.KS"}
_YIELD_SYMBOLS = {"^TNX"}
CURRENCY_GROUPS = {
    "KRW": ("🇰🇷 원화 채권", [sym for sym, _ in BONDS if sym in _KRW_BOND_SYMBOLS]),
    "USD": ("🇺🇸 달러 채권", [sym for sym, _ in BONDS if sym not in _KRW_BOND_SYMBOLS]),
}


def _format_bond_value(symbol: str, close) -> str:
    if symbol in _YIELD_SYMBOLS:
        return "N/A" if pd.isna(close) else f"{close:.2f}%"
    currency = "KRW" if symbol in _KRW_BOND_SYMBOLS else "USD"
    return format_money(close, currency, decimals=2)


def _dual_axis_chart(price_df: pd.DataFrame, price_label: str, yield_df: pd.DataFrame, yield_label: str):
    """Price on the left axis, yield on an independently-scaled right axis,
    so a small % move in yield isn't flattened by a much larger $ price range."""
    price_chart = (
        alt.Chart(price_df)
        .mark_line(color="#1f77b4")
        .encode(
            x=alt.X("date:T", title="date"),
            y=alt.Y("close:Q", title=price_label, axis=alt.Axis(titleColor="#1f77b4")),
        )
    )
    yield_chart = (
        alt.Chart(yield_df)
        .mark_line(color="#ff7f0e")
        .encode(
            x="date:T",
            y=alt.Y("close:Q", title=yield_label, axis=alt.Axis(titleColor="#ff7f0e")),
        )
    )
    return alt.layer(price_chart, yield_chart).resolve_scale(y="independent")


with get_conn() as conn:
    bonds_df = pd.read_sql("SELECT * FROM bond_prices ORDER BY date", conn)

if bonds_df.empty:
    st.warning("아직 수집된 채권 데이터가 없습니다. `python -m app.collectors.run_collection`을 먼저 실행하세요.")
    st.stop()

bonds_df["name"] = bonds_df["symbol"].map(name_map)

for currency, (label, symbols) in CURRENCY_GROUPS.items():
    group_df_all = bonds_df[bonds_df["symbol"].isin(symbols)]
    if group_df_all.empty:
        continue

    st.markdown(f"### {label} ({currency})")

    # "Latest" must reflect the most recent trading day regardless of the
    # chart period filter below, so it's computed before filtering.
    latest_rows = group_df_all.sort_values("date").groupby("symbol").tail(1)
    display_df = pd.DataFrame(
        {
            "채권": latest_rows["name"],
            "티커": latest_rows["symbol"],
            "가격/금리": [_format_bond_value(row.symbol, row.close) for row in latest_rows.itertuples()],
        }
    )
    st.markdown(right_aligned_table_html(display_df, right_align_cols=["가격/금리"]), unsafe_allow_html=True)

    charts_area = st.container()
    period = st.radio(
        "기간",
        options=list(PERIOD_OPTIONS.keys()),
        index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD),
        horizontal=True,
        key=f"period_{currency}",
    )

    yield_symbols = [s for s in symbols if s in _YIELD_SYMBOLS]
    price_symbols = [s for s in symbols if s not in _YIELD_SYMBOLS]

    with charts_area:
        # Pair the first yield series with the first price series into one
        # dual-axis chart; any remaining price series get their own chart.
        if yield_symbols and price_symbols:
            yield_symbol, price_symbol = yield_symbols[0], price_symbols[0]
            yield_df = filter_by_period(group_df_all[group_df_all["symbol"] == yield_symbol], "date", period)
            price_df = filter_by_period(group_df_all[group_df_all["symbol"] == price_symbol], "date", period)
            if not yield_df.empty and not price_df.empty:
                st.markdown(f"**{name_map[price_symbol]} (가격) vs {name_map[yield_symbol]} (금리)**")
                st.altair_chart(
                    _dual_axis_chart(price_df, f"{name_map[price_symbol]} (USD)", yield_df, f"{name_map[yield_symbol]} (%)"),
                    use_container_width=True,
                )
            price_symbols = price_symbols[1:]

        for symbol in price_symbols:
            symbol_df = filter_by_period(group_df_all[group_df_all["symbol"] == symbol], "date", period)
            if symbol_df.empty:
                continue
            st.markdown(f"**{name_map[symbol]}**")
            st.line_chart(symbol_df.set_index("date")["close"])

        for symbol in yield_symbols[1:]:  # any leftover yield series with no price to pair
            symbol_df = filter_by_period(group_df_all[group_df_all["symbol"] == symbol], "date", period)
            if symbol_df.empty:
                continue
            st.markdown(f"**{name_map[symbol]}**")
            st.line_chart(symbol_df.set_index("date")["close"])

"""Sector browser: click a sector block, see KR/US/JP stocks side by side.

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd
import streamlit as st

from app.db import get_conn
from app.formatting import CURRENCY_BY_MARKET, DEFAULT_PERIOD, PERIOD_OPTIONS, filter_by_period, format_money
from app.sectors import SECTORS

st.set_page_config(page_title="산업군별 주식", layout="wide")
st.title("산업군별 주식")

SECTOR_KEYS = [s["key"] for s in SECTORS]
if "selected_sector_key" not in st.session_state:
    st.session_state["selected_sector_key"] = SECTOR_KEYS[0]

st.caption("산업군을 클릭해서 선택하세요.")
BLOCKS_PER_ROW = 5
for row_start in range(0, len(SECTORS), BLOCKS_PER_ROW):
    row_sectors = SECTORS[row_start : row_start + BLOCKS_PER_ROW]
    cols = st.columns(BLOCKS_PER_ROW)
    for col, sector in zip(cols, row_sectors):
        with col:
            is_selected = st.session_state["selected_sector_key"] == sector["key"]
            if st.button(
                sector["name_kr"],
                key=f"sector_btn_{sector['key']}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state["selected_sector_key"] = sector["key"]
                st.rerun()

selected_key = st.session_state["selected_sector_key"]
selected_sector = next(s for s in SECTORS if s["key"] == selected_key)
st.divider()
st.subheader(selected_sector["name_kr"])

period = st.radio(
    "기간", options=list(PERIOD_OPTIONS.keys()), index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD), horizontal=True
)

with get_conn() as conn:
    stocks_df = pd.read_sql("SELECT * FROM stocks WHERE sector_key = ?", conn, params=(selected_key,))

    if stocks_df.empty:
        st.warning("아직 수집된 데이터가 없습니다. `python -m app.collectors.run_collection`을 먼저 실행하세요.")
        st.stop()

    tickers = stocks_df["ticker"].tolist()
    placeholders = ",".join("?" * len(tickers))
    market_df = pd.read_sql(
        f"SELECT * FROM market_data WHERE ticker IN ({placeholders}) ORDER BY date", conn, params=tickers
    )
    financials_df = pd.read_sql(
        f"SELECT * FROM financials WHERE ticker IN ({placeholders}) ORDER BY year, quarter", conn, params=tickers
    )

name_map = dict(zip(stocks_df["ticker"], stocks_df["name"]))
market_df["name"] = market_df["ticker"].map(name_map)
market_df = filter_by_period(market_df, "date", period)

MARKET_LABELS = {"KR": "🇰🇷 한국", "US": "🇺🇸 미국", "JP": "🇯🇵 일본"}

for market_code in ("KR", "US", "JP"):
    market_stocks = stocks_df[stocks_df["market"] == market_code]
    if market_stocks.empty:
        continue

    currency = CURRENCY_BY_MARKET[market_code]
    st.markdown(f"### {MARKET_LABELS[market_code]} ({currency})")

    market_tickers = market_stocks["ticker"].tolist()
    latest_rows = (
        market_df[market_df["ticker"].isin(market_tickers)].sort_values("date").groupby("ticker").tail(1)
    )
    summary = market_stocks[["ticker", "name"]].merge(latest_rows, on=["ticker", "name"], how="left")
    display_df = pd.DataFrame(
        {
            "종목명": summary["name"],
            "티커": summary["ticker"],
            "종가": summary["close"].map(lambda v: format_money(v, currency, decimals=2)),
            "시가총액": summary["market_cap"].map(lambda v: format_money(v, currency)),
            "거래량": summary["volume"].map(lambda v: f"{v:,.0f}" if pd.notna(v) else "N/A"),
        }
    )
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    chart_df = market_df[market_df["ticker"].isin(market_tickers)]
    if not chart_df.empty:
        st.line_chart(chart_df.pivot(index="date", columns="name", values="market_cap"))

    market_financials = financials_df[financials_df["ticker"].isin(market_tickers)]
    if not market_financials.empty:
        fin_display = market_financials.copy()
        fin_display["name"] = fin_display["ticker"].map(name_map)
        fin_display["revenue"] = fin_display["revenue"].map(lambda v: format_money(v, currency))
        fin_display["operating_income"] = fin_display["operating_income"].map(lambda v: format_money(v, currency))
        with st.expander(f"{MARKET_LABELS[market_code]} 매출 / 영업이익"):
            st.dataframe(fin_display, use_container_width=True, hide_index=True)

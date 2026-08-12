"""Commodity prices (gold, silver, copper, WTI crude, iron ore) -- one chart
per instrument so each one's own price range is visible (mixing them on one
shared axis flattens the smaller-scale ones). Metals/mining ETFs (SLX, XME,
PICK) are shown in a separate section since they track mining-company stocks,
not the raw commodity price, so they move differently from the futures above.

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
from app.formatting import DEFAULT_PERIOD, PERIOD_OPTIONS, filter_by_period, format_money, right_aligned_table_html
from app.sectors import COMMODITIES, COMMODITY_ETFS

st.set_page_config(page_title="원자재", layout="wide")
st.title("원자재 가격")

ALL_SYMBOLS = COMMODITIES + COMMODITY_ETFS
name_map = dict(ALL_SYMBOLS)

with get_conn() as conn:
    all_df = pd.read_sql("SELECT * FROM commodity_prices ORDER BY date", conn)

if all_df.empty:
    st.warning("아직 수집된 원자재 데이터가 없습니다. `python -m app.collectors.run_collection`을 먼저 실행하세요.")
    st.stop()

all_df["name"] = all_df["symbol"].map(name_map)


def _render_group(title: str, items: list, price_label: str, period: str):
    symbols = [sym for sym, _ in items]
    group_df = all_df[all_df["symbol"].isin(symbols)]
    if group_df.empty:
        return

    st.subheader(title)

    # "Latest" must reflect the most recent trading day regardless of the chart
    # period filter below, so it's computed before filtering.
    latest_rows = group_df.sort_values("date").groupby("symbol").tail(1)
    display_df = pd.DataFrame(
        {
            "종목": latest_rows["name"],
            "티커": latest_rows["symbol"],
            price_label: latest_rows["close"].map(lambda v: format_money(v, "USD", decimals=2)),
        }
    )
    st.markdown(right_aligned_table_html(display_df, right_align_cols=[price_label]), unsafe_allow_html=True)

    for symbol, name in items:
        symbol_df = filter_by_period(group_df[group_df["symbol"] == symbol], "date", period)
        if symbol_df.empty:
            continue
        st.markdown(f"**{name}**")
        st.line_chart(symbol_df.set_index("date")["close"])


charts_area = st.container()
period = st.radio(
    "기간", options=list(PERIOD_OPTIONS.keys()), index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD), horizontal=True
)

with charts_area:
    _render_group("원자재 선물", COMMODITIES, "가격 (USD)", period)
    st.caption(
        "텅스텐(tungsten)은 COMEX/LME 등 주요 거래소에 표준화된 선물 계약이 없어 "
        "Yahoo Finance에서 추적 가능한 티커가 없습니다 -- 제외했습니다."
    )
    st.divider()
    _render_group("원자재 관련 ETF", COMMODITY_ETFS, "주가 (USD)", period)
    st.caption("ETF는 광업 관련 기업 주식 바스켓이라 위 원자재 선물 가격과는 다르게 움직일 수 있습니다.")

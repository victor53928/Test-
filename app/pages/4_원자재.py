"""Commodity prices (gold, silver, copper, WTI crude) -- one chart per commodity
so each instrument's own price range is visible (mixing them on one shared
axis flattens the smaller-scale ones).

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
from app.sectors import COMMODITIES

st.set_page_config(page_title="원자재", layout="wide")
st.title("원자재 가격")

name_map = dict(COMMODITIES)

with get_conn() as conn:
    commodities_df = pd.read_sql("SELECT * FROM commodity_prices ORDER BY date", conn)

if commodities_df.empty:
    st.warning("아직 수집된 원자재 데이터가 없습니다. `python -m app.collectors.run_collection`을 먼저 실행하세요.")
    st.stop()

commodities_df["name"] = commodities_df["symbol"].map(name_map)

# "Latest" must reflect the most recent trading day regardless of the chart
# period filter below, so it's computed before filtering.
latest_rows = commodities_df.sort_values("date").groupby("symbol").tail(1)
display_df = pd.DataFrame(
    {
        "원자재": latest_rows["name"],
        "티커": latest_rows["symbol"],
        "가격 (USD)": latest_rows["close"].map(lambda v: format_money(v, "USD", decimals=2)),
    }
)
st.markdown(right_aligned_table_html(display_df, right_align_cols=["가격 (USD)"]), unsafe_allow_html=True)

charts_area = st.container()
period = st.radio(
    "기간", options=list(PERIOD_OPTIONS.keys()), index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD), horizontal=True
)

with charts_area:
    st.subheader("가격 추이")
    for symbol, name in COMMODITIES:
        symbol_df = commodities_df[commodities_df["symbol"] == symbol]
        symbol_df = filter_by_period(symbol_df, "date", period)
        if symbol_df.empty:
            continue
        st.markdown(f"**{name}**")
        st.line_chart(symbol_df.set_index("date")["close"])

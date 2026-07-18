"""Commodity prices (gold, silver, copper, WTI crude).

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
from app.formatting import DEFAULT_PERIOD, PERIOD_OPTIONS, filter_by_period, format_money
from app.sectors import COMMODITIES

st.set_page_config(page_title="원자재", layout="wide")
st.title("원자재 가격")

name_map = dict(COMMODITIES)

period = st.radio(
    "기간", options=list(PERIOD_OPTIONS.keys()), index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD), horizontal=True
)

with get_conn() as conn:
    commodities_df = pd.read_sql("SELECT * FROM commodity_prices ORDER BY date", conn)

if commodities_df.empty:
    st.warning("아직 수집된 원자재 데이터가 없습니다. `python -m app.collectors.run_collection`을 먼저 실행하세요.")
    st.stop()

commodities_df["name"] = commodities_df["symbol"].map(name_map)
commodities_df = filter_by_period(commodities_df, "date", period)

latest_rows = commodities_df.sort_values("date").groupby("symbol").tail(1)
display_df = pd.DataFrame(
    {
        "원자재": latest_rows["name"],
        "티커": latest_rows["symbol"],
        "가격 (USD)": latest_rows["close"].map(lambda v: format_money(v, "USD", decimals=2)),
    }
)
st.dataframe(display_df, use_container_width=True, hide_index=True)

st.subheader("가격 추이")
st.line_chart(commodities_df.pivot(index="date", columns="name", values="close"))

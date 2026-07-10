"""Minimal Phase 1 viewer: browse collected market data / financials by sector.

Run with: streamlit run app/dashboard.py
"""

import pandas as pd
import streamlit as st

from app.db import get_conn
from app.sectors import SECTORS

st.set_page_config(page_title="포트폴리오 리밸런싱", layout="wide")
st.title("산업군별 주식 데이터")

sector_names = {s["key"]: s["name_kr"] for s in SECTORS}
selected_key = st.selectbox(
    "산업군 선택", options=list(sector_names.keys()), format_func=lambda k: sector_names[k]
)

with get_conn() as conn:
    stocks_df = pd.read_sql(
        "SELECT * FROM stocks WHERE sector_key = ?", conn, params=(selected_key,)
    )

    if stocks_df.empty:
        st.warning("아직 수집된 데이터가 없습니다. `python -m app.collectors.run_collection`을 먼저 실행하세요.")
    else:
        tickers = stocks_df["ticker"].tolist()
        placeholders = ",".join("?" * len(tickers))

        market_df = pd.read_sql(
            f"SELECT * FROM market_data WHERE ticker IN ({placeholders}) ORDER BY date",
            conn,
            params=tickers,
        )
        financials_df = pd.read_sql(
            f"SELECT * FROM financials WHERE ticker IN ({placeholders}) ORDER BY year, quarter",
            conn,
            params=tickers,
        )

st.subheader("종목")
st.dataframe(stocks_df, use_container_width=True)

if not stocks_df.empty and not market_df.empty:
    name_map = dict(zip(stocks_df["ticker"], stocks_df["name"]))
    market_df["name"] = market_df["ticker"].map(name_map)

    st.subheader("시가총액 추이")
    cap_pivot = market_df.pivot(index="date", columns="name", values="market_cap")
    st.line_chart(cap_pivot)

    st.subheader("거래량 추이")
    volume_pivot = market_df.pivot(index="date", columns="name", values="volume")
    st.line_chart(volume_pivot)

    st.subheader("매출 / 영업이익")
    if financials_df.empty:
        st.info("재무 데이터가 없습니다 (DART_API_KEY 미설정이거나 수집 전).")
    else:
        financials_df["name"] = financials_df["ticker"].map(name_map)
        st.dataframe(financials_df, use_container_width=True)

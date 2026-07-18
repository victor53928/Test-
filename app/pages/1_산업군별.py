"""Sector browser: click a sector block, see KR/US/JP stocks side by side.
Stocks per sector are editable (add/remove) via the DB-backed sector_stocks
table, seeded once from sectors.py defaults.

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import datetime
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd
import streamlit as st

from app.collectors import dart_collector, krx_collector, us_collector
from app.config import DART_API_KEY
from app.db import (
    delete_sector_stock,
    delete_stock,
    get_conn,
    get_sector_stocks,
    seed_sector_stocks_if_empty,
    upsert_financials,
    upsert_market_data,
    upsert_sector_stock,
    upsert_stock,
)
from app.formatting import CURRENCY_BY_MARKET, DEFAULT_PERIOD, PERIOD_OPTIONS, filter_by_period, format_money
from app.sectors import SECTORS

LOOKBACK_DAYS = PERIOD_OPTIONS["10년"]
MARKET_LABELS = {"KR": "🇰🇷 한국", "US": "🇺🇸 미국", "JP": "🇯🇵 일본"}

st.set_page_config(page_title="산업군별 주식", layout="wide")
st.title("산업군별 주식")

with get_conn() as conn:
    seed_sector_stocks_if_empty(conn, SECTORS)

SECTOR_KEYS = [s["key"] for s in SECTORS]
if "selected_sector_key" not in st.session_state:
    st.session_state["selected_sector_key"] = SECTOR_KEYS[0]


def _add_stock_to_sector(sector_key: str, ticker: str, name: str, market: str):
    """Fetches price history (+ a light financials pass) for a newly-added
    sector stock and stores it, so it shows up immediately instead of waiting
    for the next `python -m app.collectors.run_collection` batch run."""
    today = datetime.date.today()
    with get_conn() as conn:
        upsert_sector_stock(conn, sector_key, ticker, name, market)
        upsert_stock(conn, ticker, name, sector_key, market)

        if market == "KR":
            fromdate = (today - datetime.timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d")
            todate = today.strftime("%Y%m%d")
            rows = krx_collector.fetch_market_data(ticker, fromdate, todate)
        else:
            rows = us_collector.fetch_market_data(ticker, period=f"{LOOKBACK_DAYS}d")
        for date, close, market_cap, volume in rows:
            upsert_market_data(conn, ticker, date, close, market_cap, volume)

        if market == "KR":
            if DART_API_KEY:
                corp_code = dart_collector.get_corp_code_map().get(ticker)
                if corp_code:
                    current_year = today.year
                    for year in (current_year - 1, current_year):
                        for quarter in (1, 2, 3, 4):
                            revenue, operating_income = dart_collector.fetch_financials(corp_code, year, quarter)
                            if revenue is not None or operating_income is not None:
                                upsert_financials(conn, ticker, year, quarter, revenue, operating_income)
        else:
            for year, quarter, revenue, operating_income in us_collector.fetch_financials(ticker):
                upsert_financials(conn, ticker, year, quarter, revenue, operating_income)

    return len(rows)


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

with st.expander("종목 추가 / 삭제"):
    with st.form(f"add_sector_stock_form_{selected_key}", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            new_ticker = st.text_input("종목코드 (예: 005930, AAPL, 7203.T)")
        with col2:
            new_name = st.text_input("종목명")
        with col3:
            new_market = st.selectbox("시장", options=list(MARKET_LABELS.keys()), format_func=lambda k: MARKET_LABELS[k])
        add_submitted = st.form_submit_button("이 산업군에 추가")
        if add_submitted:
            if not new_ticker.strip() or not new_name.strip():
                st.error("종목코드와 종목명을 모두 입력해주세요.")
            else:
                try:
                    with st.spinner(f"{new_name} 시세/재무 데이터를 가져오는 중..."):
                        n_rows = _add_stock_to_sector(selected_key, new_ticker.strip(), new_name.strip(), new_market)
                    st.success(f"{new_name} ({new_ticker})를 추가했습니다 ({n_rows}일치 시세 확보).")
                    st.rerun()
                except Exception as e:
                    st.error(f"추가하지 못했습니다: {e}")

    with get_conn() as conn:
        current_sector_stocks = get_sector_stocks(conn, selected_key)

    if current_sector_stocks:
        remove_target = st.selectbox(
            "삭제할 종목",
            options=["(선택 안 함)"] + [s["ticker"] for s in current_sector_stocks],
            format_func=lambda t: t if t == "(선택 안 함)" else f"{t} ({next(s['name'] for s in current_sector_stocks if s['ticker'] == t)})",
        )
        if remove_target != "(선택 안 함)" and st.button("선택한 종목을 이 산업군에서 삭제"):
            with get_conn() as conn:
                delete_sector_stock(conn, selected_key, remove_target)
                delete_stock(conn, remove_target)
            st.rerun()

period = st.radio(
    "기간", options=list(PERIOD_OPTIONS.keys()), index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD), horizontal=True
)

with get_conn() as conn:
    sector_stocks = get_sector_stocks(conn, selected_key)

if not sector_stocks:
    st.info("이 산업군에는 아직 종목이 없습니다. 위 '종목 추가 / 삭제'에서 추가해주세요.")
    st.stop()

stocks_df = pd.DataFrame(sector_stocks)

with get_conn() as conn:
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
    if summary["close"].isna().all():
        st.caption("아직 시세 데이터가 없습니다. `python -m app.collectors.run_collection`을 실행하면 채워집니다.")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    chart_df = market_df[market_df["ticker"].isin(market_tickers)]
    if not chart_df.empty:
        st.line_chart(chart_df.pivot(index="date", columns="name", values="market_cap"))
        st.caption("거래량")
        st.bar_chart(chart_df.pivot(index="date", columns="name", values="volume"))

    market_financials = financials_df[financials_df["ticker"].isin(market_tickers)]
    if not market_financials.empty:
        fin_display = market_financials.copy()
        fin_display["name"] = fin_display["ticker"].map(name_map)
        fin_display["revenue"] = fin_display["revenue"].map(lambda v: format_money(v, currency))
        fin_display["operating_income"] = fin_display["operating_income"].map(lambda v: format_money(v, currency))
        with st.expander(f"{MARKET_LABELS[market_code]} 매출 / 영업이익"):
            st.dataframe(fin_display, use_container_width=True, hide_index=True)

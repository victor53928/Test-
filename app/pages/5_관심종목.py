"""Watchlist: per-company Naver News + latest price/chart.

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

from app.db import delete_watchlist, get_conn, get_watchlist, upsert_watchlist
from app.formatting import format_money
from app.live_price import get_price_data
from app.news import fetch_news

MARKET_LABELS = {"KOSPI": "코스피", "KOSDAQ": "코스닥", "US": "미국"}

st.title("관심종목 뉴스 & 시세")

st.subheader("관심종목 추가")
with st.form("add_watchlist_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        ticker = st.text_input("종목코드 (예: 005930, AAPL)")
    with col2:
        name = st.text_input("종목명 (예: 삼성전자)")
    with col3:
        market = st.selectbox("시장", options=list(MARKET_LABELS.keys()), format_func=lambda k: MARKET_LABELS[k])
    keyword = st.text_input("뉴스 검색 키워드 (선택)", help="비워두면 종목명으로 뉴스를 검색합니다.")
    submitted = st.form_submit_button("추가")
    if submitted and ticker and name:
        with get_conn() as conn:
            upsert_watchlist(conn, ticker.strip(), name.strip(), market, keyword.strip() or None)
        st.success(f"{name} ({ticker})를 추가했습니다.")
        st.rerun()

with get_conn() as conn:
    watchlist = get_watchlist(conn)

st.subheader("현재 관심종목")
if not watchlist:
    st.info("아직 등록된 관심종목이 없습니다. 위에서 추가해주세요.")
else:
    st.dataframe(watchlist, use_container_width=True)

    delete_target = st.selectbox("삭제할 종목", options=["(선택 안 함)"] + [w["ticker"] for w in watchlist])
    if delete_target != "(선택 안 함)" and st.button("선택한 종목 삭제"):
        with get_conn() as conn:
            delete_watchlist(conn, delete_target)
        st.rerun()

    st.divider()


@st.cache_data(ttl=60)
def _cached_price_data(ticker: str, market: str):
    return get_price_data(ticker, market)


@st.cache_data(ttl=300)
def _cached_news(keyword: str):
    return fetch_news(keyword)


for entry in watchlist:
    with st.expander(f"{entry['name']} ({entry['ticker']})", expanded=True):
        price_col, news_col = st.columns([1, 1])

        with price_col:
            st.markdown("**시세**")
            try:
                data = _cached_price_data(entry["ticker"], entry["market"])
                delta = f"{data['change_pct']:.2f}%" if data["change_pct"] is not None else None
                history = data["history"]
                latest_volume = history["volume"].iloc[-1] if not history.empty else None

                if entry["market"] in ("KOSPI", "KOSDAQ"):
                    m1, m2, m3 = st.columns(3)
                    m1.metric("종가", format_money(data["latest_price"], data["currency"]), delta=delta)
                    m2.metric("시가총액", format_money(data["market_cap"], data["currency"]))
                    m3.metric("거래량", f"{latest_volume:,.0f}" if latest_volume is not None else "N/A")
                else:
                    st.metric(
                        f"현재가 ({data['currency']})",
                        format_money(data["latest_price"], data["currency"], decimals=2),
                        delta=delta,
                    )

                price_history = history.set_index("date")
                st.line_chart(price_history["close"])
                st.caption("거래량")
                st.bar_chart(price_history["volume"])
            except Exception as e:
                st.warning(f"시세를 불러오지 못했습니다: {e}")

        with news_col:
            st.markdown("**뉴스**")
            try:
                news_items = _cached_news(entry["keyword"])
                if not news_items:
                    st.caption("관련 뉴스가 없습니다.")
                for item in news_items:
                    st.markdown(f"[{item['title']}]({item['link']})")
                    st.caption(f"{item['pubDate']} — {item['description']}")
            except Exception as e:
                st.warning(f"뉴스를 불러오지 못했습니다: {e}")

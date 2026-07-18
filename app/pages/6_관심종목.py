"""Watchlist: click a compact stock block (grouped 한국/미국/일본) to see its
price/chart, PER/PBR + revenue trend, and Naver News. Added by company name
only (no ticker code needed). The add form lives at the bottom of the page.

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd
import streamlit as st

from app.db import delete_watchlist, get_conn, get_watchlist, upsert_watchlist
from app.formatting import DEFAULT_PERIOD, PERIOD_OPTIONS, format_money
from app.fundamentals import get_financial_trend, get_valuation
from app.live_price import get_price_data
from app.news import SOURCE_DOMAINS, fetch_news
from app.ticker_lookup import DartApiKeyMissing, resolve_kr_ticker, resolve_yf_ticker

MARKET_LABELS = {"KOSPI": "코스피", "KOSDAQ": "코스닥", "US": "미국", "JP": "일본"}
CURRENCY_BY_MARKET = {"KOSPI": "KRW", "KOSDAQ": "KRW", "US": "USD", "JP": "JPY"}
GROUPS = [
    ("🇰🇷 한국 주식", ("KOSPI", "KOSDAQ")),
    ("🇺🇸 미국 주식", ("US",)),
    ("🇯🇵 일본 주식", ("JP",)),
]
BLOCKS_PER_ROW = 6

st.set_page_config(page_title="관심종목", layout="wide")
st.title("관심종목 뉴스 & 시세")

with get_conn() as conn:
    watchlist = get_watchlist(conn)

if not watchlist:
    st.info("아직 등록된 관심종목이 없습니다. 이 페이지 맨 아래에서 추가해주세요.")
else:
    if st.session_state.get("selected_watchlist_ticker") not in [w["ticker"] for w in watchlist]:
        st.session_state["selected_watchlist_ticker"] = watchlist[0]["ticker"]

    for group_label, group_markets in GROUPS:
        group_entries = [w for w in watchlist if w["market"] in group_markets]
        if not group_entries:
            continue
        st.markdown(f"**{group_label}**")
        for row_start in range(0, len(group_entries), BLOCKS_PER_ROW):
            row_entries = group_entries[row_start : row_start + BLOCKS_PER_ROW]
            cols = st.columns(BLOCKS_PER_ROW)
            for col, entry in zip(cols, row_entries):
                with col:
                    is_selected = st.session_state["selected_watchlist_ticker"] == entry["ticker"]
                    if st.button(
                        entry["name"],
                        key=f"wl_btn_{entry['ticker']}",
                        use_container_width=True,
                        type="primary" if is_selected else "secondary",
                    ):
                        st.session_state["selected_watchlist_ticker"] = entry["ticker"]
                        st.rerun()

    st.divider()

    selected_entry = next(
        (w for w in watchlist if w["ticker"] == st.session_state["selected_watchlist_ticker"]), None
    )

    @st.cache_data(ttl=60)
    def _cached_price_data(ticker: str, market: str, days: int):
        return get_price_data(ticker, market, days=days)

    @st.cache_data(ttl=3600)
    def _cached_valuation(ticker: str, market: str):
        return get_valuation(ticker, market)

    @st.cache_data(ttl=86400)
    def _cached_trend(ticker: str, market: str):
        return get_financial_trend(ticker, market)

    @st.cache_data(ttl=300)
    def _cached_news(keyword: str, filtered: bool):
        if filtered:
            return fetch_news(keyword, source_domains=list(SOURCE_DOMAINS.values()))
        return fetch_news(keyword)

    if selected_entry:
        entry = selected_entry
        title_col, delete_col = st.columns([5, 1])
        title_col.subheader(entry["name"])
        if delete_col.button("삭제", key=f"delete_{entry['ticker']}"):
            with get_conn() as conn:
                delete_watchlist(conn, entry["ticker"])
            del st.session_state["selected_watchlist_ticker"]
            st.rerun()

        st.markdown("**시세**")
        try:
            chart_area = st.container()
            entry_period = st.radio(
                "기간",
                options=list(PERIOD_OPTIONS.keys()),
                index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD),
                horizontal=True,
                key=f"period_{entry['ticker']}",
            )

            data = _cached_price_data(entry["ticker"], entry["market"], PERIOD_OPTIONS[entry_period])
            delta = f"{data['change_pct']:.2f}%" if data["change_pct"] is not None else None
            history = data["history"]
            latest_volume = history["volume"].iloc[-1] if not history.empty else None
            as_of = history["date"].iloc[-1] if not history.empty else "N/A"

            with chart_area:
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
                st.caption(f"기준일자: {as_of}")

                price_history = history.set_index("date")
                st.line_chart(price_history["close"], height=350)
                st.caption("거래량")
                st.bar_chart(price_history["volume"], height=150)
        except Exception as e:
            st.warning(f"시세를 불러오지 못했습니다: {e}")

        st.markdown("**재무 상황**")
        try:
            valuation = _cached_valuation(entry["ticker"], entry["market"])
            v1, v2, v3 = st.columns(3)
            v1.metric("시가총액", format_money(valuation["market_cap"], CURRENCY_BY_MARKET[entry["market"]]))
            v2.metric("PER", f"{valuation['per']:.2f}" if valuation["per"] else "N/A")
            v3.metric("PBR", f"{valuation['pbr']:.2f}" if valuation["pbr"] else "N/A")
        except Exception as e:
            st.warning(f"PER/PBR/시가총액을 불러오지 못했습니다: {e}")

        try:
            trend = _cached_trend(entry["ticker"], entry["market"])
            if not trend:
                st.caption(
                    "매출/영업이익 추이 데이터가 없습니다"
                    + ("" if entry["market"] in ("US", "JP") else " (.env의 DART_API_KEY 설정이 필요합니다).")
                )
            else:
                trend_df = pd.DataFrame(trend).set_index("year")
                trend_df = trend_df.rename(columns={"revenue": "매출", "operating_income": "영업이익"})
                st.caption(f"연도별 매출 / 영업이익 추이 ({len(trend)}개년)")
                st.bar_chart(trend_df[["매출", "영업이익"]])
        except Exception as e:
            st.warning(f"매출/영업이익 추이를 불러오지 못했습니다: {e}")

        st.markdown("**뉴스**")
        try:
            news_items = _cached_news(entry["keyword"], filtered=True)
            filtered_out_empty = False
            if not news_items:
                filtered_out_empty = True
                news_items = _cached_news(entry["keyword"], filtered=False)

            if not news_items:
                st.caption("관련 뉴스를 찾지 못했습니다.")
            else:
                if filtered_out_empty:
                    st.caption("매일경제/한국경제 기사가 없어 전체 뉴스로 대신 표시합니다.")
                for item in news_items:
                    source_label = f"[{item['source']}] " if item.get("source") else ""
                    st.markdown(f"{source_label}[{item['title']}]({item['link']})")
                    st.caption(f"{item['pubDate']} — {item['description']}")
        except Exception as e:
            st.warning(f"뉴스를 불러오지 못했습니다: {e}")

st.divider()
st.subheader("관심종목 추가")
st.caption("종목명만 입력하면 종목코드를 자동으로 찾아서 등록합니다.")
with st.form("add_watchlist_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("종목명 (예: 삼성전자)")
    with col2:
        market = st.selectbox("시장", options=list(MARKET_LABELS.keys()), format_func=lambda k: MARKET_LABELS[k])
    keyword = st.text_input("뉴스 검색 키워드 (선택)", help="비워두면 종목명으로 뉴스를 검색합니다.")
    submitted = st.form_submit_button("추가")
    if submitted:
        if not name.strip():
            st.error("종목명을 입력해주세요.")
        else:
            try:
                with st.spinner(f"'{name}' 종목코드를 찾는 중..."):
                    resolved_ticker = (
                        resolve_kr_ticker(name.strip())
                        if market in ("KOSPI", "KOSDAQ")
                        else resolve_yf_ticker(name.strip())
                    )
            except DartApiKeyMissing as e:
                st.error(str(e))
                resolved_ticker = None
            else:
                if not resolved_ticker:
                    st.error(f"'{name}'의 종목코드를 찾지 못했습니다. 정확한 회사명으로 다시 시도해주세요.")

            if resolved_ticker:
                try:
                    with get_conn() as conn:
                        upsert_watchlist(conn, resolved_ticker, name.strip(), market, keyword.strip() or None)
                    st.success(f"{name}를 추가했습니다.")
                    st.rerun()
                except Exception as e:
                    st.error(f"추가하지 못했습니다: {e}")

"""Keyword-based news feed (Naver News) for followed companies.

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

from app.db import add_news_keyword, get_conn, list_news_keywords, remove_news_keyword
from app.news import NaverNewsError, credentials_configured, search_news
from app.sectors import all_kr_tickers, all_us_tickers

st.title("종목 뉴스 (네이버 뉴스)")

if not credentials_configured():
    st.error(
        "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET가 설정되지 않았습니다. "
        "https://developers.naver.com/apps/#/register 에서 검색 API를 사용 설정한 앱을 등록하고 "
        ".env에 키를 채워넣으세요."
    )
    st.stop()

stock_names = sorted({name for _, name, _ in all_kr_tickers() + all_us_tickers()})

st.subheader("관심 키워드 관리")
col1, col2 = st.columns([2, 1])
with col1:
    picked = st.selectbox("추적 종목에서 선택", options=["(직접 입력)"] + stock_names)
with col2:
    custom = st.text_input("직접 입력", placeholder="예: 삼성전자, 2차전지")

if st.button("키워드 추가"):
    keyword = custom.strip() or (picked if picked != "(직접 입력)" else "")
    if keyword:
        with get_conn() as conn:
            add_news_keyword(conn, keyword)
        st.rerun()
    else:
        st.warning("추가할 키워드를 선택하거나 입력해주세요.")

with get_conn() as conn:
    saved_keywords = list_news_keywords(conn)

if not saved_keywords:
    st.info("아직 추적 중인 키워드가 없습니다. 위에서 추가해주세요.")
    st.stop()

remove_target = st.selectbox("삭제할 키워드", options=["(선택 안 함)"] + saved_keywords)
if remove_target != "(선택 안 함)" and st.button("선택한 키워드 삭제"):
    with get_conn() as conn:
        remove_news_keyword(conn, remove_target)
    st.rerun()

st.divider()
st.subheader("최신 뉴스")

sort_label = st.radio("정렬", options=["최신순", "관련도순"], horizontal=True)
sort_param = "date" if sort_label == "최신순" else "sim"

tabs = st.tabs(saved_keywords)
for tab, keyword in zip(tabs, saved_keywords):
    with tab:
        try:
            articles = search_news(keyword, display=15, sort=sort_param)
        except NaverNewsError as e:
            st.error(str(e))
            continue

        if not articles:
            st.info("검색된 뉴스가 없습니다.")
            continue

        for article in articles:
            st.markdown(f"**[{article['title']}]({article['link']})**")
            st.caption(article["pub_date"])
            st.write(article["description"])
            st.divider()

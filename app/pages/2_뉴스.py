"""Curated news: what Trump and the Fed chair have been saying, and major
company CEO interviews. Fixed topics (not user-configurable, unlike the
per-stock news on the 관심종목 page).

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

from app.news import SOURCE_DOMAINS, fetch_news

st.set_page_config(page_title="뉴스", layout="wide")
st.title("뉴스")
st.caption("매일경제·한국경제 기사를 우선 표시하고, 없으면 전체 뉴스로 대신 표시합니다.")

TOPICS = [
    {"label": "트럼프 대통령", "keyword": "트럼프 대통령"},
    {"label": "연준의장 (파월)", "keyword": "연준의장 파월"},
    {"label": "주요기업 CEO 인터뷰", "keyword": "기업 CEO 인터뷰"},
]


@st.cache_data(ttl=300)
def _cached_news(keyword: str, filtered: bool):
    if filtered:
        return fetch_news(keyword, display=10, source_domains=list(SOURCE_DOMAINS.values()))
    return fetch_news(keyword, display=10)


for topic in TOPICS:
    st.subheader(topic["label"])
    try:
        news_items = _cached_news(topic["keyword"], filtered=True)
        filtered_out_empty = False
        if not news_items:
            filtered_out_empty = True
            news_items = _cached_news(topic["keyword"], filtered=False)

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

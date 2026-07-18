"""Landing page. The actual views live in app/pages/ (sidebar navigation).

Run with: streamlit run app/dashboard.py
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

st.set_page_config(page_title="포트폴리오 리밸런싱", layout="wide")
st.title("포트폴리오 리밸런싱 대시보드")

st.markdown("왼쪽 사이드바에서 원하는 화면으로 이동하세요.")

st.page_link("pages/1_마켓정보.py", label="마켓정보", icon="🌐")
st.page_link("pages/2_뉴스.py", label="뉴스", icon="📰")
st.page_link("pages/3_산업군별.py", label="산업군별 주식", icon="📊")
st.page_link("pages/4_원자재.py", label="원자재", icon="🪙")
st.page_link("pages/5_채권.py", label="채권", icon="📄")
st.page_link("pages/6_관심종목.py", label="관심종목 뉴스 & 시세", icon="⭐")
st.page_link("pages/7_종목비교.py", label="종목 비교", icon="⚔️")
st.page_link("pages/8_포트폴리오.py", label="포트폴리오 입력 및 리밸런싱", icon="⚖️")

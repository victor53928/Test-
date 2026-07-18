"""Stock comparison: pick up to 5 stocks (any market, mixed OK) and compare
normalized price performance (% change from the period start) on one chart,
plus a side-by-side valuation metrics table.

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd
import streamlit as st

from app.formatting import DEFAULT_PERIOD, PERIOD_OPTIONS, format_money
from app.fundamentals import get_valuation
from app.live_price import get_price_data
from app.ticker_lookup import DartApiKeyMissing, resolve_kr_ticker, resolve_yf_ticker

MARKET_LABELS = {"KOSPI": "코스피", "KOSDAQ": "코스닥", "US": "미국", "JP": "일본"}
CURRENCY_BY_MARKET = {"KOSPI": "KRW", "KOSDAQ": "KRW", "US": "USD", "JP": "JPY"}
MAX_COMPARE = 5

st.set_page_config(page_title="종목 비교", layout="wide")
st.title("종목 비교")
st.caption(f"최대 {MAX_COMPARE}개 종목을 골라 가격 변화율과 주요 지표를 나란히 비교합니다.")

if "compare_list" not in st.session_state:
    st.session_state["compare_list"] = []

compare_list = st.session_state["compare_list"]

st.subheader("비교할 종목 추가")
if len(compare_list) >= MAX_COMPARE:
    st.info(f"이미 {MAX_COMPARE}개를 담았습니다. 비교하려면 아래에서 하나를 먼저 제거해주세요.")
else:
    with st.form("add_compare_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("종목명 (예: 삼성전자, SK하이닉스, Micron)")
        with col2:
            market = st.selectbox("시장", options=list(MARKET_LABELS.keys()), format_func=lambda k: MARKET_LABELS[k])
        submitted = st.form_submit_button("비교 목록에 추가")
        if submitted:
            if not name.strip():
                st.error("종목명을 입력해주세요.")
            else:
                resolved_ticker = None
                try:
                    with st.spinner(f"'{name}' 종목코드를 찾는 중..."):
                        resolved_ticker = (
                            resolve_kr_ticker(name.strip())
                            if market in ("KOSPI", "KOSDAQ")
                            else resolve_yf_ticker(name.strip())
                        )
                except DartApiKeyMissing as e:
                    st.error(str(e))
                else:
                    if not resolved_ticker:
                        st.error(f"'{name}'의 종목코드를 찾지 못했습니다. 정확한 회사명으로 다시 시도해주세요.")

                if resolved_ticker:
                    if any(c["ticker"] == resolved_ticker for c in compare_list):
                        st.warning(f"{name}는 이미 비교 목록에 있습니다.")
                    else:
                        compare_list.append({"ticker": resolved_ticker, "name": name.strip(), "market": market})
                        st.rerun()

if not compare_list:
    st.info("비교할 종목이 없습니다. 위에서 추가해주세요.")
    st.stop()

st.subheader("비교 목록")
chip_cols = st.columns(len(compare_list))
for col, item in zip(chip_cols, compare_list):
    with col:
        st.markdown(f"**{item['name']}**")
        if st.button("제거", key=f"remove_compare_{item['ticker']}"):
            st.session_state["compare_list"] = [c for c in compare_list if c["ticker"] != item["ticker"]]
            st.rerun()

st.divider()

period = st.radio(
    "기간", options=list(PERIOD_OPTIONS.keys()), index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD), horizontal=True
)


@st.cache_data(ttl=60)
def _cached_price_data(ticker: str, market: str, days: int):
    return get_price_data(ticker, market, days=days)


@st.cache_data(ttl=3600)
def _cached_valuation(ticker: str, market: str):
    return get_valuation(ticker, market)


st.subheader("가격 변화율 비교")
st.caption("각 종목의 기간 시작일 종가를 0%로 놓고 변화율을 비교합니다 (통화가 달라도 비교 가능).")

frames = []
price_errors = []
for item in compare_list:
    try:
        data = _cached_price_data(item["ticker"], item["market"], PERIOD_OPTIONS[period])
        hist = data["history"].copy()
        if hist.empty:
            raise ValueError("가격 데이터가 없습니다.")
        base = hist["close"].iloc[0]
        hist["변화율(%)"] = (hist["close"] / base - 1) * 100
        hist["종목"] = item["name"]
        frames.append(hist[["date", "변화율(%)", "종목"]])
    except Exception as e:
        price_errors.append(f"{item['name']}: {e}")

for err in price_errors:
    st.warning(f"가격 데이터를 불러오지 못했습니다: {err}")

if frames:
    combined = pd.concat(frames, ignore_index=True)
    st.line_chart(combined.pivot(index="date", columns="종목", values="변화율(%)"))
else:
    st.caption("표시할 가격 데이터가 없습니다.")

st.subheader("주요 지표 비교")

metric_rows = [
    ("시가총액", "market_cap", "money"),
    ("PER", "per", "num"),
    ("PBR", "pbr", "num"),
    ("EPS", "eps", "money2"),
    ("BPS", "bps", "money2"),
    ("배당수익률", "dividend_yield", "pct"),
    ("주당배당금", "dps", "money2"),
    ("ROE", "roe", "pct"),
    ("52주 최고", "week52_high", "money2"),
    ("52주 최저", "week52_low", "money2"),
    ("평균거래량", "avg_volume", "int"),
    ("Beta", "beta", "num"),
]


def _format_value(value, kind, currency):
    if value is None:
        return "N/A"
    if kind == "money":
        return format_money(value, currency)
    if kind == "money2":
        return format_money(value, currency, decimals=2)
    if kind == "pct":
        return f"{value:.2f}%"
    if kind == "int":
        return f"{value:,.0f}"
    return f"{value:,.2f}"


table = {"지표": [label for label, _, _ in metric_rows]}
for item in compare_list:
    try:
        valuation = _cached_valuation(item["ticker"], item["market"])
        currency = CURRENCY_BY_MARKET[item["market"]]
        table[item["name"]] = [_format_value(valuation.get(key), kind, currency) for _, key, kind in metric_rows]
    except Exception as e:
        table[item["name"]] = ["불러오기 실패"] * len(metric_rows)
        st.warning(f"{item['name']} 지표를 불러오지 못했습니다: {e}")

st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

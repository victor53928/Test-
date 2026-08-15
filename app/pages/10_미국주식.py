"""미국주식: 미국 4대 지수(S&P500/다우존스/나스닥/필라델피아 반도체지수)와
시가총액 상위 20개 종목을 한 화면에서 봅니다.

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd
import streamlit as st
import yfinance as yf

from app.formatting import (
    DEFAULT_PERIOD,
    PERIOD_OPTIONS,
    format_money,
    format_money_korean,
    right_aligned_table_html,
)
from app.fundamentals import get_valuation
from app.live_price import get_price_data
from app.sectors import INDICES, TOP20_US_STOCKS
from app.theme import colored_metric, inject_theme

st.set_page_config(page_title="미국주식", layout="wide")
inject_theme()
st.title("미국주식")
st.caption("미국 4대 지수와 시가총액 상위 20개 종목을 한눈에 봅니다.")

US_INDICES = next(g["symbols"] for g in INDICES if g["country"] == "US")


@st.cache_data(ttl=300)
def _cached_index_history(symbol: str, days: int):
    hist = yf.Ticker(symbol).history(period=f"{days}d")
    if hist.empty:
        raise ValueError(f"{symbol}: 조회된 데이터가 없습니다.")
    return pd.DataFrame(
        {"date": [d.strftime("%Y-%m-%d") for d in hist.index], "close": [float(v) for v in hist["Close"]]}
    )


# --- 4대 지수 ---
st.subheader("4대 지수")
index_cols = st.columns(len(US_INDICES))
index_errors = []
for col, (symbol, name) in zip(index_cols, US_INDICES):
    with col:
        try:
            hist = _cached_index_history(symbol, 30)
            latest = hist["close"].iloc[-1]
            prev = hist["close"].iloc[-2] if len(hist) >= 2 else None
            pct = (latest - prev) / prev * 100 if prev else None
            colored_metric(name, f"{latest:,.2f}", delta_value=pct, delta_suffix="%")
        except Exception as e:
            index_errors.append(f"{name}: {e}")
            colored_metric(name, "N/A")
for err in index_errors:
    st.warning(f"지수 조회 실패: {err}")

st.divider()

# --- 시가총액 상위 20개 종목 ---
st.subheader("시가총액 상위 종목")
st.caption("시가총액 순위는 매일 바뀌므로 대략적인 대형주 목록으로 참고해주세요.")


@st.cache_data(ttl=3600)
def _cached_valuation(ticker: str):
    return get_valuation(ticker, "US")


@st.cache_data(ttl=300)
def _cached_price_data(ticker: str, days: int):
    return get_price_data(ticker, "US", days=days)


rows = []
errors = []
for ticker, name in TOP20_US_STOCKS:
    try:
        valuation = _cached_valuation(ticker)
        rows.append({"ticker": ticker, "name": name, **valuation})
    except Exception as e:
        errors.append(f"{name} ({ticker}): {e}")

if errors:
    with st.expander(f"일부 종목 데이터를 가져오지 못했습니다 ({len(errors)}개)"):
        for err in errors:
            st.caption(err)

if not rows:
    st.warning("종목 데이터를 하나도 가져오지 못했습니다. 잠시 후 다시 시도해주세요.")
    st.stop()

stocks_df = pd.DataFrame(rows).sort_values("market_cap", ascending=False, na_position="last")

display_df = pd.DataFrame(
    {
        "종목명": stocks_df["name"],
        "티커": stocks_df["ticker"],
        "시가총액": stocks_df["market_cap"].map(lambda v: format_money_korean(v, "USD") if pd.notna(v) else "N/A"),
        "PER": stocks_df["per"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "N/A"),
        "배당수익률": stocks_df["dividend_yield"].map(lambda v: f"{v:.2f}%" if pd.notna(v) else "N/A"),
        "52주 최고": stocks_df["week52_high"].map(lambda v: format_money(v, "USD", decimals=2) if pd.notna(v) else "N/A"),
        "52주 최저": stocks_df["week52_low"].map(lambda v: format_money(v, "USD", decimals=2) if pd.notna(v) else "N/A"),
    }
)
st.markdown(
    right_aligned_table_html(display_df, right_align_cols=["시가총액", "PER", "배당수익률", "52주 최고", "52주 최저"]),
    unsafe_allow_html=True,
)

# --- 가격 추이 비교 (블록 다중 선택) ---
st.subheader("가격 추이 비교")
st.caption("그래프에 표시할 종목을 블록으로 선택하세요 (여러 개를 눌러서 동시에 선택할 수 있습니다).")

stock_names = [name for _, name in TOP20_US_STOCKS]
selected_key = "us_stocks_trend_selected"
if selected_key not in st.session_state:
    st.session_state[selected_key] = set(stock_names)
else:
    st.session_state[selected_key] &= set(stock_names)

BLOCKS_PER_ROW = 5
for row_start in range(0, len(stock_names), BLOCKS_PER_ROW):
    row_names = stock_names[row_start : row_start + BLOCKS_PER_ROW]
    cols = st.columns(BLOCKS_PER_ROW)
    for col, name in zip(cols, row_names):
        with col:
            is_selected = name in st.session_state[selected_key]
            if st.button(
                name,
                key=f"us_stock_block_{name}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                if is_selected:
                    st.session_state[selected_key].discard(name)
                else:
                    st.session_state[selected_key].add(name)
                st.rerun()

selected_names = [n for n in stock_names if n in st.session_state[selected_key]]
ticker_by_name = {name: ticker for ticker, name in TOP20_US_STOCKS}

chart_area = st.container()
period = st.radio(
    "기간", options=list(PERIOD_OPTIONS.keys()), index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD), horizontal=True
)

frames = []
price_errors = []
for name in selected_names:
    ticker = ticker_by_name[name]
    try:
        data = _cached_price_data(ticker, PERIOD_OPTIONS[period])
        hist = data["history"]
        if hist.empty:
            continue
        base = hist["close"].iloc[0]
        if not base:
            continue
        series = hist[["date", "close"]].copy()
        series["변화율(%)"] = (series["close"] / base - 1) * 100
        series["종목"] = name
        frames.append(series[["date", "변화율(%)", "종목"]])
    except Exception as e:
        price_errors.append(f"{name}: {e}")

with chart_area:
    if not selected_names:
        st.caption("표시할 종목을 선택해주세요.")
    elif not frames:
        st.caption("표시할 가격 데이터가 없습니다.")
    else:
        combined = pd.concat(frames, ignore_index=True)
        st.line_chart(combined.pivot(index="date", columns="종목", values="변화율(%)"))
for err in price_errors:
    st.warning(f"가격 데이터를 불러오지 못했습니다: {err}")

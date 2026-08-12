"""Dividend stocks: 한국/미국 주요 배당주의 배당수익률·주당배당금을 표로 비교하고,
종목을 여러 개 골라 가격 추이(%)를 겹쳐서 볼 수 있는 페이지.

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import altair as alt
import pandas as pd
import streamlit as st

from app.formatting import DEFAULT_PERIOD, PERIOD_OPTIONS, format_money, format_money_korean, right_aligned_table_html
from app.fundamentals import get_valuation
from app.live_price import get_price_data
from app.sectors import DIVIDEND_STOCKS

MARKET_LABELS = {"KR": "🇰🇷 한국 배당주", "US": "🇺🇸 미국 배당주"}
CURRENCY_BY_MARKET = {"KR": "KRW", "US": "USD"}
LIVE_MARKET_BY_MARKET = {"KR": "KOSPI", "US": "US"}
BLOCKS_PER_ROW = 4

st.set_page_config(page_title="배당금", layout="wide")
st.title("배당금")
st.caption("한국/미국 주요 배당주의 배당수익률·주당배당금을 비교하고, 가격 추이를 겹쳐서 볼 수 있습니다.")


@st.cache_data(ttl=3600)
def _cached_valuation(ticker: str, live_market: str):
    return get_valuation(ticker, live_market)


@st.cache_data(ttl=300)
def _cached_price_data(ticker: str, live_market: str, days: int):
    return get_price_data(ticker, live_market, days=days)


rows = []
errors = []
for market, stocks in DIVIDEND_STOCKS.items():
    for ticker, name in stocks:
        try:
            valuation = _cached_valuation(ticker, LIVE_MARKET_BY_MARKET[market])
            rows.append({"market": market, "ticker": ticker, "name": name, **valuation})
        except Exception as e:
            errors.append(f"{name} ({ticker}): {e}")

if errors:
    with st.expander(f"일부 종목 데이터를 가져오지 못했습니다 ({len(errors)}개)"):
        for err in errors:
            st.caption(err)

if not rows:
    st.warning("배당주 데이터를 하나도 가져오지 못했습니다. 잠시 후 다시 시도해주세요.")
    st.stop()

all_df = pd.DataFrame(rows)

# --- 배당수익률(%)은 통화와 무관하므로 한국+미국을 한 화면에서 바로 비교할 수 있습니다. ---
st.subheader("배당수익률 비교 (전체)")
yield_df = all_df.dropna(subset=["dividend_yield"]).sort_values("dividend_yield", ascending=False).copy()
if yield_df.empty:
    st.caption("배당수익률 데이터를 가져오지 못했습니다.")
else:
    yield_df["label"] = yield_df["dividend_yield"].map(lambda v: f"{v:.2f}%")
    yield_df["종목"] = yield_df["name"] + " (" + yield_df["market"].map(MARKET_LABELS) + ")"
    bar = (
        alt.Chart(yield_df)
        .mark_bar()
        .encode(
            x=alt.X("종목:N", sort=yield_df["종목"].tolist(), title=None),
            y=alt.Y("dividend_yield:Q", title="배당수익률 (%)"),
            color=alt.Color("market:N", title="시장"),
            tooltip=[alt.Tooltip("종목:N"), alt.Tooltip("label:N", title="배당수익률")],
        )
    )
    text = bar.mark_text(dy=-8, fontSize=11).encode(text="label:N")
    st.altair_chart((bar + text).properties(height=380), use_container_width=True)

st.divider()


def _render_market_section(market: str, stocks: list):
    currency = CURRENCY_BY_MARKET[market]
    live_market = LIVE_MARKET_BY_MARKET[market]
    market_df = all_df[all_df["market"] == market]
    if market_df.empty:
        return

    st.subheader(MARKET_LABELS[market])

    table_df = market_df.sort_values("dividend_yield", ascending=False, na_position="last")
    display_df = pd.DataFrame(
        {
            "종목명": table_df["name"],
            "배당수익률": table_df["dividend_yield"].map(lambda v: f"{v:.2f}%" if pd.notna(v) else "N/A"),
            "주당배당금": table_df["dps"].map(lambda v: format_money(v, currency, decimals=2) if pd.notna(v) else "N/A"),
            "PER": table_df["per"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "N/A"),
            "시가총액": table_df["market_cap"].map(lambda v: format_money_korean(v, currency) if pd.notna(v) else "N/A"),
        }
    )
    st.markdown(
        right_aligned_table_html(display_df, right_align_cols=["배당수익률", "주당배당금", "PER", "시가총액"]),
        unsafe_allow_html=True,
    )

    st.caption("가격 추이를 비교할 종목을 블록으로 선택하세요 (여러 개를 눌러서 동시에 선택할 수 있습니다).")
    stock_names = [name for _, name in stocks]
    selected_key = f"dividend_trend_selected_{market}"
    if selected_key not in st.session_state:
        st.session_state[selected_key] = set(stock_names)
    else:
        st.session_state[selected_key] &= set(stock_names)

    for row_start in range(0, len(stock_names), BLOCKS_PER_ROW):
        row_names = stock_names[row_start : row_start + BLOCKS_PER_ROW]
        cols = st.columns(BLOCKS_PER_ROW)
        for col, name in zip(cols, row_names):
            with col:
                is_selected = name in st.session_state[selected_key]
                if st.button(
                    name,
                    key=f"dividend_block_{market}_{name}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    if is_selected:
                        st.session_state[selected_key].discard(name)
                    else:
                        st.session_state[selected_key].add(name)
                    st.rerun()

    selected_names = [name for name in stock_names if name in st.session_state[selected_key]]
    ticker_by_name = {name: ticker for ticker, name in stocks}

    chart_area = st.container()
    period = st.radio(
        "기간",
        options=list(PERIOD_OPTIONS.keys()),
        index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD),
        horizontal=True,
        key=f"period_dividend_{market}",
    )

    frames = []
    price_errors = []
    for name in selected_names:
        ticker = ticker_by_name[name]
        try:
            data = _cached_price_data(ticker, live_market, PERIOD_OPTIONS[period])
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


_render_market_section("KR", DIVIDEND_STOCKS["KR"])
st.divider()
_render_market_section("US", DIVIDEND_STOCKS["US"])

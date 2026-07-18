"""Sector-vs-sector trading-value comparison: sums each sector's KR+US+JP
stocks' trading value (close x volume), converted to KRW, so sectors can be
compared head-to-head (e.g. "is more money flowing into 반도체 or 방산 today?")
even though their stocks trade in different currencies.

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import datetime
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import altair as alt
import pandas as pd
import streamlit as st

from app.db import get_all_sector_stocks, get_conn, seed_sector_stocks_if_empty
from app.formatting import DEFAULT_PERIOD, PERIOD_OPTIONS, filter_by_period, format_money, right_aligned_table_html
from app.live_price import get_price_data
from app.portfolio import to_krw
from app.sectors import SECTORS

STALE_DAYS = 5  # DB rows older than this trigger a live fallback fetch, same threshold as 산업군별
FALLBACK_DAYS = 30
MARKET_LABELS = {"KR": "🇰🇷 한국", "US": "🇺🇸 미국", "JP": "🇯🇵 일본"}
_MARKET_TO_CURRENCY = {"KR": "KRW", "US": "USD", "JP": "JPY"}
_MARKET_TO_LIVE_MARKET = {"KR": "KOSPI", "US": "US", "JP": "JP"}
SECTOR_NAME_BY_KEY = {s["key"]: s["name_kr"] for s in SECTORS}

st.set_page_config(page_title="산업군 비교", layout="wide")
st.title("산업군별 거래대금 비교")
st.caption(
    "산업군에 속한 국내/미국/일본 종목들의 거래대금(종가 × 거래량)을 원화로 환산해 합산합니다. "
    "예: 반도체 산업군과 방산 산업군 중 오늘 어디에 더 많은 돈이 들어왔는지 비교할 수 있습니다. "
    "(발행주식수가 일정하다고 가정한 근사치이며, 배치 수집을 미리 해두면 훨씬 빠르고 최대 10년치 추이까지 볼 수 있습니다 — "
    "`python -m app.collectors.run_collection`)"
)

with get_conn() as conn:
    seed_sector_stocks_if_empty(conn, SECTORS)
    all_stocks = get_all_sector_stocks(conn)

if not all_stocks:
    st.info("아직 산업군에 등록된 종목이 없습니다. '산업군별' 페이지에서 먼저 종목을 추가해주세요.")
    st.stop()

all_tickers = [s["ticker"] for s in all_stocks]
with get_conn() as conn:
    placeholders = ",".join("?" * len(all_tickers))
    db_df = pd.read_sql(
        f"SELECT * FROM market_data WHERE ticker IN ({placeholders}) ORDER BY date", conn, params=all_tickers
    )
latest_by_ticker = (
    db_df.sort_values("date").groupby("ticker").tail(1).set_index("ticker") if not db_df.empty else pd.DataFrame()
)


@st.cache_data(ttl=300)
def _live_fallback(ticker: str, market: str):
    return get_price_data(ticker, _MARKET_TO_LIVE_MARKET[market], days=FALLBACK_DAYS)


today = datetime.date.today()
history_frames = []
snapshot_rows = []
fallback_errors = []

with st.spinner(f"{len(all_stocks)}개 종목의 시세를 불러오는 중..."):
    for stock in all_stocks:
        ticker, name, market, sector_key = stock["ticker"], stock["name"], stock["market"], stock["sector_key"]
        currency = _MARKET_TO_CURRENCY[market]

        db_row = latest_by_ticker.loc[ticker] if ticker in latest_by_ticker.index else None
        is_stale = (
            db_row is None
            or pd.isna(db_row["date"])
            or (today - datetime.datetime.strptime(db_row["date"], "%Y-%m-%d").date()).days > STALE_DAYS
        )

        if db_row is not None and not is_stale and pd.notna(db_row["close"]) and pd.notna(db_row["volume"]):
            ticker_hist = db_df[db_df["ticker"] == ticker][["date", "close", "volume"]].copy()
        else:
            try:
                live = _live_fallback(ticker, market)
                hist = live["history"]
                if hist.empty:
                    raise ValueError("가격 데이터가 없습니다.")
                ticker_hist = hist[["date", "close", "volume"]].copy()
            except Exception as e:
                fallback_errors.append(f"{name} ({ticker}): {e}")
                continue

        ticker_hist = ticker_hist.dropna(subset=["close", "volume"])
        if ticker_hist.empty:
            continue
        ticker_hist["trading_value_krw"] = [
            to_krw(close * volume, currency) for close, volume in zip(ticker_hist["close"], ticker_hist["volume"])
        ]
        ticker_hist["sector_key"] = sector_key
        ticker_hist["market"] = market
        history_frames.append(ticker_hist)

        latest_row = ticker_hist.sort_values("date").iloc[-1]
        snapshot_rows.append(
            {
                "sector_key": sector_key,
                "종목명": name,
                "시장": market,
                "기준일자": latest_row["date"],
                "거래대금": latest_row["trading_value_krw"],
            }
        )

if not history_frames:
    st.warning("거래대금 데이터를 하나도 가져오지 못했습니다. 잠시 후 다시 시도해주세요.")
    st.stop()

combined_hist = pd.concat(history_frames, ignore_index=True)
combined_hist["산업군"] = combined_hist["sector_key"].map(SECTOR_NAME_BY_KEY)
snapshot_df = pd.DataFrame(snapshot_rows)
snapshot_df["산업군"] = snapshot_df["sector_key"].map(SECTOR_NAME_BY_KEY)

if fallback_errors:
    with st.expander(f"일부 종목 데이터를 가져오지 못했습니다 ({len(fallback_errors)}개)"):
        for err in fallback_errors:
            st.caption(err)

# --- 오늘 기준 산업군별 거래대금 (스냅샷) ---
st.subheader("오늘 기준 산업군별 거래대금")
sector_totals = (
    snapshot_df.groupby(["sector_key", "산업군"])
    .agg(거래대금=("거래대금", "sum"), 종목수=("종목명", "count"))
    .reset_index()
    .sort_values("거래대금", ascending=False)
)
sector_totals["label"] = sector_totals["거래대금"].map(lambda v: format_money(v, "KRW"))

bar = (
    alt.Chart(sector_totals)
    .mark_bar()
    .encode(
        x=alt.X("산업군:N", sort=sector_totals["산업군"].tolist(), title=None),
        y=alt.Y("거래대금:Q", title="거래대금 (KRW)"),
        tooltip=[alt.Tooltip("산업군:N"), alt.Tooltip("label:N", title="거래대금"), alt.Tooltip("종목수:Q", title="종목 수")],
    )
)
text = bar.mark_text(dy=-8, fontSize=11).encode(text="label:N")
st.altair_chart((bar + text).properties(height=380), use_container_width=True)

summary_display_df = sector_totals[["산업군", "거래대금", "종목수"]].copy()
summary_display_df["거래대금"] = summary_display_df["거래대금"].map(lambda v: format_money(v, "KRW"))
st.markdown(
    right_aligned_table_html(summary_display_df, right_align_cols=["거래대금", "종목수"]), unsafe_allow_html=True
)

# --- 시장별 (국내/미국/일본) 비중 ---
st.subheader("산업군별 국내 · 미국 · 일본 비중")
market_breakdown = (
    snapshot_df.groupby(["산업군", "시장"])["거래대금"].sum().reset_index()
)
market_breakdown["시장"] = market_breakdown["시장"].map(MARKET_LABELS)
breakdown_pivot = market_breakdown.pivot(index="산업군", columns="시장", values="거래대금")
breakdown_pivot = breakdown_pivot.loc[sector_totals["산업군"]]  # keep the same 거래대금-descending order
st.bar_chart(breakdown_pivot)

# --- 거래대금 추이 (기간 선택) ---
st.subheader("거래대금 추이")
chart_area = st.container()
period = st.radio(
    "기간", options=list(PERIOD_OPTIONS.keys()), index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD), horizontal=True
)

daily_by_sector = combined_hist.groupby(["date", "산업군"])["trading_value_krw"].sum().reset_index()
daily_by_sector = filter_by_period(daily_by_sector, "date", period)
with chart_area:
    if daily_by_sector.empty:
        st.caption("표시할 데이터가 없습니다.")
    else:
        st.line_chart(daily_by_sector.pivot(index="date", columns="산업군", values="trading_value_krw"))

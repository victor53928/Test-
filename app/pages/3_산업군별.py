"""Sector browser: pick a sector block, then a market block, then which
companies to chart. Stocks per sector are editable (add/remove) via the
DB-backed sector_stocks table, seeded once from sectors.py defaults. The
add/delete form lives at the bottom of the page.

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
from app.live_price import get_price_data
from app.sectors import SECTORS
from app.ticker_lookup import DartApiKeyMissing, resolve_kr_ticker, resolve_yf_ticker

LOOKBACK_DAYS = PERIOD_OPTIONS["10년"]
FALLBACK_DAYS = 30  # live-fetch window used when the batch-collected data is missing/stale
MARKET_LABELS = {"KR": "🇰🇷 한국", "US": "🇺🇸 미국", "JP": "🇯🇵 일본"}
STALE_DAYS = 5  # if the DB's latest row for a KR ticker is older than this, try a live pykrx fetch instead


def _labeled_line_chart(df: pd.DataFrame, value_col: str, value_title: str, currency: str):
    """Line chart with a formatted-value tooltip and a text label at the end
    of each line showing its latest value, so numbers are visible on the
    chart itself, not just in the table above it."""
    df = df.copy()
    df["label"] = df[value_col].map(lambda v: format_money(v, currency))

    base = alt.Chart(df).encode(
        x=alt.X("date:T", title="date"),
        y=alt.Y(f"{value_col}:Q", title=value_title),
        color=alt.Color("name:N", title="종목"),
    )
    line = base.mark_line().encode(
        tooltip=[
            alt.Tooltip("name:N", title="종목"),
            alt.Tooltip("date:T", title="날짜"),
            alt.Tooltip("label:N", title=value_title),
        ]
    )
    last_points = df.sort_values("date").groupby("name").tail(1)
    text = (
        alt.Chart(last_points)
        .mark_text(align="left", dx=6, fontSize=11)
        .encode(x="date:T", y=f"{value_col}:Q", text="label:N", color=alt.Color("name:N", legend=None))
    )
    return (line + text).properties(height=380)


@st.cache_data(ttl=300)
def _live_kr_fallback(ticker: str):
    """Best-effort live pykrx fetch, used when the batch-collected market_data
    table has no (or stale) data for a KR ticker. "KOSPI" here only routes to
    the KR code path in live_price.get_price_data -- it works the same for
    KOSDAQ tickers too, since pykrx itself doesn't need that distinction."""
    return get_price_data(ticker, "KOSPI", days=FALLBACK_DAYS)


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

with get_conn() as conn:
    sector_stocks = get_sector_stocks(conn, selected_key)

if not sector_stocks:
    st.info("이 산업군에는 아직 종목이 없습니다. 이 페이지 맨 아래에서 추가해주세요.")
else:
    stocks_df = pd.DataFrame(sector_stocks)
    available_markets = [m for m in ("KR", "US", "JP") if (stocks_df["market"] == m).any()]

    market_state_key = f"selected_market_{selected_key}"
    if st.session_state.get(market_state_key) not in available_markets:
        st.session_state[market_state_key] = available_markets[0]

    st.caption("시장을 선택하세요.")
    market_cols = st.columns(len(available_markets))
    for col, market_code in zip(market_cols, available_markets):
        with col:
            is_selected = st.session_state[market_state_key] == market_code
            if st.button(
                MARKET_LABELS[market_code],
                key=f"market_btn_{selected_key}_{market_code}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state[market_state_key] = market_code
                st.rerun()

    market_code = st.session_state[market_state_key]
    currency = CURRENCY_BY_MARKET[market_code]
    market_stocks = stocks_df[stocks_df["market"] == market_code]
    market_tickers = market_stocks["ticker"].tolist()
    name_map = dict(zip(stocks_df["ticker"], stocks_df["name"]))

    with get_conn() as conn:
        placeholders = ",".join("?" * len(market_tickers))
        market_df_all = pd.read_sql(
            f"SELECT * FROM market_data WHERE ticker IN ({placeholders}) ORDER BY date", conn, params=market_tickers
        )
        financials_df = pd.read_sql(
            f"SELECT * FROM financials WHERE ticker IN ({placeholders}) ORDER BY year, quarter",
            conn,
            params=market_tickers,
        )
    market_df_all["name"] = market_df_all["ticker"].map(name_map)

    st.markdown(f"### {MARKET_LABELS[market_code]} ({currency})")

    # "Latest" values must reflect the most recently available trading day
    # regardless of the chart period filter below (e.g. selecting "1주일" must
    # not hide today's close just because a holiday pushed it near the window
    # edge) -- computed from the unfiltered data, not the period-filtered chart data.
    latest_rows = market_df_all.sort_values("date").groupby("ticker").tail(1)
    summary = market_stocks[["ticker", "name"]].merge(latest_rows, on=["ticker", "name"], how="left")

    fallback_errors = []
    if market_code == "KR":
        # The batch collector may not have run yet (or its data is stale); when
        # the DB has nothing recent for a KR ticker, try a live pykrx fetch right
        # now instead of just showing "N/A" -- and also splice that fetch's daily
        # history into market_df_all, otherwise the chart below stays empty even
        # though the summary row above now has a value (a live-fetched *point*
        # isn't enough to draw a line; the chart needs the history rows too).
        today = datetime.date.today()
        live_history_frames = []

        def _resolve_kr_row(row):
            db_date = row["date"]
            is_stale = pd.isna(db_date) or (
                today - datetime.datetime.strptime(db_date, "%Y-%m-%d").date()
            ).days > STALE_DAYS
            if pd.notna(row["close"]) and not is_stale:
                return pd.Series(
                    {"close": row["close"], "market_cap": row["market_cap"], "volume": row["volume"], "as_of": db_date}
                )
            try:
                live = _live_kr_fallback(row["ticker"])
                hist = live["history"]
                as_of = hist["date"].iloc[-1] if not hist.empty else None
                volume = hist["volume"].iloc[-1] if not hist.empty else None
                if not hist.empty:
                    hist_for_chart = hist.copy()
                    hist_for_chart["ticker"] = row["ticker"]
                    hist_for_chart["name"] = row["name"]
                    live_history_frames.append(hist_for_chart)
                return pd.Series(
                    {"close": live["latest_price"], "market_cap": live["market_cap"], "volume": volume, "as_of": as_of}
                )
            except Exception as e:
                fallback_errors.append(f"{row['name']} ({row['ticker']}): {e}")
                return pd.Series({"close": None, "market_cap": None, "volume": None, "as_of": None})

        resolved = summary.apply(_resolve_kr_row, axis=1)
        summary[["close", "market_cap", "volume"]] = resolved[["close", "market_cap", "volume"]]
        summary["as_of"] = resolved["as_of"]

        if live_history_frames:
            # Don't duplicate rows for tickers that already have (fresh) DB data.
            fallback_tickers = pd.concat(live_history_frames)["ticker"].unique()
            market_df_all = pd.concat(
                [market_df_all[~market_df_all["ticker"].isin(fallback_tickers)], *live_history_frames],
                ignore_index=True,
            )
            st.caption(
                f"일부 종목은 배치 수집 데이터가 없어 최근 {FALLBACK_DAYS}일치를 실시간으로 가져왔습니다 "
                "(전체 10년 그래프를 보려면 `python -m app.collectors.run_collection`을 실행하세요)."
            )
    else:
        summary["as_of"] = summary["date"]

    display_df = pd.DataFrame(
        {
            "종목명": summary["name"],
            "티커": summary["ticker"],
            "기준일자": summary["as_of"].fillna("N/A"),
            "종가": summary["close"].map(lambda v: format_money(v, currency, decimals=2) if pd.notna(v) else "N/A"),
            "시가총액": summary["market_cap"].map(lambda v: format_money(v, currency) if pd.notna(v) else "N/A"),
            "거래량": summary["volume"].map(lambda v: f"{v:,.0f}" if pd.notna(v) else "N/A"),
        }
    )
    if summary["close"].isna().all():
        st.caption("아직 시세 데이터가 없습니다. `python -m app.collectors.run_collection`을 실행하면 채워집니다.")
    for err in fallback_errors:
        st.warning(f"실시간 시세 조회 실패: {err}")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    company_options = market_stocks["name"].tolist()
    selected_companies = st.multiselect(
        "그래프에 표시할 종목 선택",
        options=company_options,
        default=company_options,
        key=f"companies_{selected_key}_{market_code}",
    )

    chart_area = st.container()
    period = st.radio(
        "기간", options=list(PERIOD_OPTIONS.keys()), index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD), horizontal=True
    )

    chart_df = market_df_all[market_df_all["name"].isin(selected_companies)]
    chart_df = filter_by_period(chart_df, "date", period)
    with chart_area:
        if not selected_companies:
            st.caption("표시할 종목을 선택해주세요.")
        elif chart_df.empty:
            st.caption("표시할 데이터가 없습니다.")
        else:
            st.altair_chart(
                _labeled_line_chart(chart_df, "market_cap", f"시가총액 ({currency})", currency),
                use_container_width=True,
            )
            st.caption("거래량")
            st.bar_chart(chart_df.pivot(index="date", columns="name", values="volume"))

            st.caption("거래대금 추이 (종가 × 거래량 근사치)")
            chart_df = chart_df.copy()
            chart_df["trading_value"] = chart_df["close"] * chart_df["volume"]
            st.altair_chart(
                _labeled_line_chart(chart_df, "trading_value", f"거래대금 ({currency})", currency),
                use_container_width=True,
            )

    market_financials = financials_df[financials_df["ticker"].isin(market_tickers)]
    if not market_financials.empty:
        fin_display = market_financials.copy()
        fin_display["name"] = fin_display["ticker"].map(name_map)
        fin_display["revenue"] = fin_display["revenue"].map(lambda v: format_money(v, currency))
        fin_display["operating_income"] = fin_display["operating_income"].map(lambda v: format_money(v, currency))
        with st.expander(f"{MARKET_LABELS[market_code]} 매출 / 영업이익"):
            st.dataframe(fin_display, use_container_width=True, hide_index=True)

st.divider()
st.subheader("종목 추가 / 삭제")
st.caption("종목명만 입력하면 종목코드를 자동으로 찾습니다.")
with st.form(f"add_sector_stock_form_{selected_key}", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        new_name = st.text_input("종목명 (예: 삼성전자)")
    with col2:
        new_market = st.selectbox("시장", options=list(MARKET_LABELS.keys()), format_func=lambda k: MARKET_LABELS[k])
    add_submitted = st.form_submit_button("이 산업군에 추가")
    if add_submitted:
        if not new_name.strip():
            st.error("종목명을 입력해주세요.")
        else:
            resolved_ticker = None
            try:
                with st.spinner(f"'{new_name}' 종목코드를 찾는 중..."):
                    resolved_ticker = (
                        resolve_kr_ticker(new_name.strip()) if new_market == "KR" else resolve_yf_ticker(new_name.strip())
                    )
            except DartApiKeyMissing as e:
                st.error(str(e))
            else:
                if not resolved_ticker:
                    st.error(f"'{new_name}'의 종목코드를 찾지 못했습니다. 정확한 회사명으로 다시 시도해주세요.")

            if resolved_ticker:
                try:
                    with st.spinner(f"{new_name} 시세/재무 데이터를 가져오는 중..."):
                        n_rows = _add_stock_to_sector(selected_key, resolved_ticker, new_name.strip(), new_market)
                    st.success(f"{new_name}를 추가했습니다 ({n_rows}일치 시세 확보).")
                    st.rerun()
                except Exception as e:
                    st.error(f"추가하지 못했습니다: {e}")

with get_conn() as conn:
    current_sector_stocks = get_sector_stocks(conn, selected_key)

if current_sector_stocks:
    remove_target = st.selectbox(
        "삭제할 종목",
        options=["(선택 안 함)"] + [s["ticker"] for s in current_sector_stocks],
        format_func=lambda t: t if t == "(선택 안 함)" else next(s["name"] for s in current_sector_stocks if s["ticker"] == t),
    )
    if remove_target != "(선택 안 함)" and st.button("선택한 종목을 이 산업군에서 삭제"):
        with get_conn() as conn:
            delete_sector_stock(conn, selected_key, remove_target)
            delete_stock(conn, remove_target)
        st.rerun()

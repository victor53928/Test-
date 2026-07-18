"""Market info: major indices for Korea, Japan, Taiwan, and the US --
numbers (latest value + day change) and a chart per index.

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

from app.db import get_conn
from app.formatting import DEFAULT_PERIOD, PERIOD_OPTIONS, filter_by_period
from app.sectors import INDICES

st.set_page_config(page_title="마켓정보", layout="wide")
st.title("마켓정보")
st.caption("한국·일본·대만·미국 주요 지수")

FALLBACK_DAYS = 30


@st.cache_data(ttl=300)
def _live_index_fallback(symbol: str):
    """Best-effort live yfinance fetch, used when the batch-collected
    index_prices table has no (or stale) data for this index."""
    hist = yf.Ticker(symbol).history(period=f"{FALLBACK_DAYS}d")
    if hist.empty:
        raise ValueError(f"{symbol}: 조회된 데이터가 없습니다.")
    return pd.DataFrame(
        {"date": [d.strftime("%Y-%m-%d") for d in hist.index], "close": [float(v) for v in hist["Close"]]}
    )


name_map = {sym: name for group in INDICES for sym, name in group["symbols"]}
all_symbols = list(name_map.keys())

with get_conn() as conn:
    placeholders = ",".join("?" * len(all_symbols))
    index_df_all = pd.read_sql(
        f"SELECT * FROM index_prices WHERE symbol IN ({placeholders}) ORDER BY date", conn, params=all_symbols
    )
index_df_all["name"] = index_df_all["symbol"].map(name_map)

STALE_DAYS = 5
fallback_notes = []


def _ensure_symbol_data(symbol: str) -> pd.DataFrame:
    """Returns date/close history for `symbol`, falling back to a live fetch
    (and splicing it into the shared frame) if the DB has nothing recent."""
    global index_df_all
    existing = index_df_all[index_df_all["symbol"] == symbol]
    is_stale = existing.empty or (
        pd.Timestamp.today().normalize() - pd.to_datetime(existing["date"]).max()
    ).days > STALE_DAYS
    if not is_stale:
        return existing
    try:
        live = _live_index_fallback(symbol)
        live = live.copy()
        live["symbol"] = symbol
        live["name"] = name_map[symbol]
        index_df_all = pd.concat([index_df_all[index_df_all["symbol"] != symbol], live], ignore_index=True)
        fallback_notes.append(name_map[symbol])
        return live
    except Exception as e:
        st.warning(f"{name_map[symbol]} 실시간 조회 실패: {e}")
        return existing


for group in INDICES:
    st.markdown(f"### {group['label']}")

    metric_cols = st.columns(len(group["symbols"]))
    for col, (symbol, name) in zip(metric_cols, group["symbols"]):
        symbol_df = _ensure_symbol_data(symbol).sort_values("date")
        if symbol_df.empty:
            col.metric(name, "N/A")
            continue
        latest = symbol_df["close"].iloc[-1]
        prev = symbol_df["close"].iloc[-2] if len(symbol_df) >= 2 else None
        delta_pct = f"{(latest - prev) / prev * 100:.2f}%" if prev else None
        col.metric(name, f"{latest:,.2f}", delta=delta_pct)

    charts_area = st.container()
    period = st.radio(
        "기간",
        options=list(PERIOD_OPTIONS.keys()),
        index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD),
        horizontal=True,
        key=f"period_{group['country']}",
    )
    with charts_area:
        for symbol, name in group["symbols"]:
            symbol_df = index_df_all[index_df_all["symbol"] == symbol]
            symbol_df = filter_by_period(symbol_df, "date", period)
            if symbol_df.empty:
                continue
            st.markdown(f"**{name}**")
            st.line_chart(symbol_df.set_index("date")["close"])

if fallback_notes:
    st.caption(
        f"배치 수집 데이터가 없어 실시간으로 최근 {FALLBACK_DAYS}일치를 가져온 지수: {', '.join(sorted(set(fallback_notes)))} "
        "(전체 10년 그래프를 보려면 `python -m app.collectors.run_collection`을 실행하세요.)"
    )

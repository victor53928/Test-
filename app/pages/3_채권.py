"""Bond prices / yields (US 10Y, TLT, KR govt bond ETF), split by currency.

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd
import streamlit as st

from app.db import get_conn
from app.formatting import DEFAULT_PERIOD, PERIOD_OPTIONS, filter_by_period, format_money
from app.sectors import BONDS

st.set_page_config(page_title="채권", layout="wide")
st.title("채권 가격 / 금리")

name_map = dict(BONDS)
_KRW_BOND_SYMBOLS = {"148070.KS"}
CURRENCY_GROUPS = {
    "KRW": ("🇰🇷 원화 채권", [sym for sym, _ in BONDS if sym in _KRW_BOND_SYMBOLS]),
    "USD": ("🇺🇸 달러 채권", [sym for sym, _ in BONDS if sym not in _KRW_BOND_SYMBOLS]),
}


def _format_bond_value(symbol: str, close) -> str:
    if symbol == "^TNX":  # yield, not a price
        return "N/A" if pd.isna(close) else f"{close:.2f}%"
    currency = "KRW" if symbol in _KRW_BOND_SYMBOLS else "USD"
    return format_money(close, currency, decimals=2)


period = st.radio(
    "기간", options=list(PERIOD_OPTIONS.keys()), index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD), horizontal=True
)

with get_conn() as conn:
    bonds_df = pd.read_sql("SELECT * FROM bond_prices ORDER BY date", conn)

if bonds_df.empty:
    st.warning("아직 수집된 채권 데이터가 없습니다. `python -m app.collectors.run_collection`을 먼저 실행하세요.")
    st.stop()

bonds_df["name"] = bonds_df["symbol"].map(name_map)

for currency, (label, symbols) in CURRENCY_GROUPS.items():
    group_df_all = bonds_df[bonds_df["symbol"].isin(symbols)]
    if group_df_all.empty:
        continue

    st.markdown(f"### {label} ({currency})")

    # "Latest" must reflect the most recent trading day regardless of the
    # chart period filter below, so it's computed before filtering.
    latest_rows = group_df_all.sort_values("date").groupby("symbol").tail(1)
    display_df = pd.DataFrame(
        {
            "채권": latest_rows["name"],
            "티커": latest_rows["symbol"],
            "가격/금리": [_format_bond_value(row.symbol, row.close) for row in latest_rows.itertuples()],
        }
    )
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    group_df = filter_by_period(group_df_all, "date", period)
    st.line_chart(group_df.pivot(index="date", columns="name", values="close"))

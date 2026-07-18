"""Portfolio holdings input and rebalancing view.

Run with: streamlit run app/dashboard.py (this page appears in the sidebar nav)
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd
import streamlit as st

from app.config import JPY_KRW_RATE, USD_KRW_RATE
from app.db import delete_holding, get_conn, upsert_holding
from app.formatting import format_money, right_aligned_table_html
from app.portfolio import compute_rebalancing_plan, get_holdings_with_value, summarize_by_asset_class
from app.sectors import BONDS, COMMODITIES, all_jp_tickers, all_kr_tickers, all_us_tickers

ASSET_CLASS_LABELS = {"stock": "주식", "commodity": "원자재", "bond": "채권"}

st.title("포트폴리오 입력 및 리밸런싱")

stock_options = [(t, f"{name} ({t})") for t, name, _ in all_kr_tickers() + all_us_tickers() + all_jp_tickers()]
commodity_options = [(sym, f"{name} ({sym})") for sym, name in COMMODITIES]
bond_options = [(sym, f"{name} ({sym})") for sym, name in BONDS if not sym.startswith("^")]

OPTIONS_BY_ASSET_CLASS = {
    "stock": stock_options,
    "commodity": commodity_options,
    "bond": bond_options,
}

st.subheader("보유 종목 추가 / 수정")
asset_class = st.selectbox(
    "자산군", options=list(ASSET_CLASS_LABELS.keys()), format_func=lambda k: ASSET_CLASS_LABELS[k]
)
options = OPTIONS_BY_ASSET_CLASS[asset_class]
option_labels = dict(options)

with st.form("add_holding_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        ticker = st.selectbox("종목", options=[o[0] for o in options], format_func=lambda t: option_labels[t])
    with col2:
        quantity = st.number_input("수량", min_value=0.0, step=1.0)
    submitted = st.form_submit_button("저장")
    if submitted and quantity > 0:
        with get_conn() as conn:
            upsert_holding(conn, ticker, quantity, asset_class)
        st.success(f"{option_labels[ticker]} {quantity}주 저장했습니다.")
        st.rerun()

st.subheader("현재 보유 종목")
with get_conn() as conn:
    holdings = get_holdings_with_value(conn)

if not holdings:
    st.info("아직 등록된 보유 종목이 없습니다. 위에서 추가해주세요.")
else:
    holdings_df = pd.DataFrame(holdings)
    display_holdings_df = holdings_df.copy()
    display_holdings_df["price"] = [
        format_money(row.price, row.currency, decimals=2) for row in holdings_df.itertuples()
    ]
    display_holdings_df["market_value"] = [
        format_money(row.market_value, row.currency) for row in holdings_df.itertuples()
    ]
    display_holdings_df["market_value_krw"] = holdings_df["market_value_krw"].map(lambda v: format_money(v, "KRW"))
    display_holdings_df = display_holdings_df.rename(
        columns={
            "ticker": "티커",
            "quantity": "수량",
            "asset_class": "자산군",
            "currency": "통화",
            "price": "현재가",
            "market_value": "평가금액",
            "market_value_krw": "평가금액(원화)",
        }
    )
    st.markdown(
        right_aligned_table_html(display_holdings_df, right_align_cols=["수량", "현재가", "평가금액", "평가금액(원화)"]),
        unsafe_allow_html=True,
    )

    delete_target = st.selectbox("삭제할 종목", options=["(선택 안 함)"] + [h["ticker"] for h in holdings])
    if delete_target != "(선택 안 함)" and st.button("선택한 종목 삭제"):
        with get_conn() as conn:
            delete_holding(conn, delete_target)
        st.rerun()

    totals, weights, grand_total = summarize_by_asset_class(holdings)
    plan = compute_rebalancing_plan(totals, grand_total)

    st.subheader("자산배분 현황 (목표: 주식 50% / 원자재 30% / 채권 20%)")
    st.caption(
        f"환율 적용: 1 USD = {USD_KRW_RATE:,.0f} KRW, 1 JPY = {JPY_KRW_RATE:,.2f} KRW "
        "(.env의 USD_KRW_RATE / JPY_KRW_RATE 값, 수동 설정)"
    )
    st.metric("총 평가금액", format_money(grand_total, "KRW"))

    plan_df = pd.DataFrame(plan)
    plan_df["asset_class"] = plan_df["asset_class"].map(ASSET_CLASS_LABELS)
    plan_df["current_weight"] = (plan_df["current_weight"] * 100).round(1)
    plan_df["target_weight"] = (plan_df["target_weight"] * 100).round(1)
    plan_df["deviation_pp"] = plan_df["deviation_pp"].round(1)
    plan_df["current_value"] = plan_df["current_value"].map(lambda v: format_money(v, "KRW"))
    plan_df["action_amount"] = plan_df["action_amount"].map(lambda v: format_money(v, "KRW"))
    plan_df["needs_rebalance"] = plan_df["needs_rebalance"].map({True: "예", False: "아니오"})
    plan_display_df = plan_df.rename(
        columns={
            "asset_class": "자산군",
            "current_value": "현재 평가금액",
            "current_weight": "현재 비중(%)",
            "target_weight": "목표 비중(%)",
            "deviation_pp": "이탈(%p)",
            "action_amount": "리밸런싱 필요 금액",
            "needs_rebalance": "리밸런싱 필요",
        }
    )
    st.markdown(
        right_aligned_table_html(
            plan_display_df,
            right_align_cols=["현재 평가금액", "현재 비중(%)", "목표 비중(%)", "이탈(%p)", "리밸런싱 필요 금액"],
        ),
        unsafe_allow_html=True,
    )

    for p in plan:
        label = ASSET_CLASS_LABELS[p["asset_class"]]
        if not p["needs_rebalance"]:
            st.success(f"{label}: 목표 비중 범위 내 ({p['current_weight']*100:.1f}%)")
        elif p["action_amount"] > 0:
            st.warning(f"{label}: 목표 대비 {abs(p['deviation_pp']):.1f}%p 부족 → 약 {format_money(p['action_amount'], 'KRW')} 추가 매수 필요")
        else:
            st.warning(f"{label}: 목표 대비 {abs(p['deviation_pp']):.1f}%p 초과 → 약 {format_money(abs(p['action_amount']), 'KRW')} 매도 필요")

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

from app.config import USD_KRW_RATE
from app.db import delete_holding, get_conn, upsert_holding
from app.portfolio import compute_rebalancing_plan, get_holdings_with_value, summarize_by_asset_class
from app.sectors import BONDS, COMMODITIES, all_kr_tickers, all_us_tickers

ASSET_CLASS_LABELS = {"stock": "주식", "commodity": "원자재", "bond": "채권"}

st.title("포트폴리오 입력 및 리밸런싱")

stock_options = [(t, f"{name} ({t})") for t, name, _ in all_kr_tickers() + all_us_tickers()]
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
    st.dataframe(holdings_df, use_container_width=True)

    delete_target = st.selectbox("삭제할 종목", options=["(선택 안 함)"] + [h["ticker"] for h in holdings])
    if delete_target != "(선택 안 함)" and st.button("선택한 종목 삭제"):
        with get_conn() as conn:
            delete_holding(conn, delete_target)
        st.rerun()

    totals, weights, grand_total = summarize_by_asset_class(holdings)
    plan = compute_rebalancing_plan(totals, grand_total)

    st.subheader("자산배분 현황 (목표: 주식 50% / 원자재 30% / 채권 20%)")
    st.caption(f"환율 적용: 1 USD = {USD_KRW_RATE:,.0f} KRW (.env의 USD_KRW_RATE 값, 수동 설정)")
    st.metric("총 평가금액 (KRW)", f"{grand_total:,.0f}")

    plan_df = pd.DataFrame(plan)
    plan_df["asset_class"] = plan_df["asset_class"].map(ASSET_CLASS_LABELS)
    plan_df["current_weight"] = (plan_df["current_weight"] * 100).round(1)
    plan_df["target_weight"] = (plan_df["target_weight"] * 100).round(1)
    plan_df["current_value"] = plan_df["current_value"].round(0)
    plan_df["action_amount"] = plan_df["action_amount"].round(0)
    st.dataframe(
        plan_df.rename(
            columns={
                "asset_class": "자산군",
                "current_value": "현재 평가금액(KRW)",
                "current_weight": "현재 비중(%)",
                "target_weight": "목표 비중(%)",
                "deviation_pp": "이탈(%p)",
                "action_amount": "리밸런싱 필요 금액(KRW)",
                "needs_rebalance": "리밸런싱 필요",
            }
        ),
        use_container_width=True,
    )

    for p in plan:
        label = ASSET_CLASS_LABELS[p["asset_class"]]
        if not p["needs_rebalance"]:
            st.success(f"{label}: 목표 비중 범위 내 ({p['current_weight']*100:.1f}%)")
        elif p["action_amount"] > 0:
            st.warning(f"{label}: 목표 대비 {abs(p['deviation_pp']):.1f}%p 부족 → 약 {p['action_amount']:,.0f}원 추가 매수 필요")
        else:
            st.warning(f"{label}: 목표 대비 {abs(p['deviation_pp']):.1f}%p 초과 → 약 {abs(p['action_amount']):,.0f}원 매도 필요")

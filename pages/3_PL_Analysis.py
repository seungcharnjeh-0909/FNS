"""
pages/3_PL_Analysis.py

- User enters the closing year/month directly (no hardcoded month
  control cell, per project spec section 10).
- Checks whether RAW_SYSTEM(PL) actually has data through that month
  yet (Phase 1 finding: it can lag behind the workbook's nominal
  closing month).
- Runs the P/L Engine (core/pnl_engine.py) to produce a current-month /
  YTD summary by management account.
- Shows a built-in formula sanity check comparing our calculated
  accounts (e.g. GP1, Ordinary Profit) against the value RAW already
  stores for that same account code.
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from core.period_engine import get_closing_period, check_data_availability
from core.pnl_engine import (
    load_account_rules,
    compute_monthly_totals,
    compute_pnl_summary,
    check_calculated_accounts_against_raw,
)

st.set_page_config(page_title="P/L Analysis", page_icon="💰", layout="wide")
st.title("💰 P/L Analysis (손익 분석)")

if "raw_pl_df" not in st.session_state:
    st.warning("아직 불러온 데이터가 없습니다. 먼저 **Data Import** 페이지로 이동하세요.")
    st.stop()

raw_pl_df = st.session_state["raw_pl_df"]

st.info(
    "현재는 **PERF(실적) 시나리오만** 계산합니다. RAW_SYSTEM(PL)에는 BP/RP/FCST/전년 "
    "데이터가 없기 때문입니다 — 이 데이터들이 연결되면 시나리오 비교 화면을 추가합니다."
)

# --- Closing period input (직접 입력) ---
st.subheader("마감 기간 선택")
c1, c2 = st.columns(2)
closing_year = c1.number_input("마감 연도", min_value=2000, max_value=2100, value=2026, step=1)
closing_month = c2.number_input("마감 월", min_value=1, max_value=12, value=8, step=1)

period = get_closing_period(int(closing_year), int(closing_month))
availability = check_data_availability(raw_pl_df, period.month)

if not availability["is_closing_month_available"]:
    st.warning(
        f"선택하신 {period.year}년 {period.month}월 실적이 아직 RAW 데이터에 없습니다. "
        f"현재 데이터는 **{availability['max_month_in_data']}월**까지만 있습니다. "
        f"아래 결과는 {availability['max_month_in_data']}월을 당월 기준으로 대신 계산한 것입니다."
    )
    effective_month = availability["max_month_in_data"]
else:
    effective_month = period.month

if effective_month == 0:
    st.error("RAW 데이터에 유효한 월별 실적이 전혀 없습니다.")
    st.stop()

effective_ytd_months = [m for m in period.ytd_months if m <= effective_month]

# --- Run the P/L Engine ---
CONFIG_PATH = Path(__file__).parent.parent / "config" / "account_rules.json"
account_rules = load_account_rules(CONFIG_PATH)

monthly_totals = compute_monthly_totals(raw_pl_df, account_rules)
summary = compute_pnl_summary(monthly_totals, current_month=effective_month, ytd_months=effective_ytd_months)

st.divider()

# --- Summary table ---
st.subheader(f"손익 요약 — 당월({effective_month}월) / 누계(1~{effective_month}월)")
display_summary = summary.rename(columns={
    "account_code": "계정코드",
    "account_name": "계정명",
    "current_month": "당월",
    "ytd": "누계(YTD)",
})
st.dataframe(
    display_summary.style.format({"당월": "{:,.0f}", "누계(YTD)": "{:,.0f}"}),
    use_container_width=True,
    hide_index=True,
)

# --- Chart: monthly trend for key accounts ---
st.subheader("월별 추이 — 매출액 / 매출원가 / GP1")
key_codes = ["4100000", "4200000", "4300000"]
chart_df = monthly_totals[monthly_totals["account_code"].isin(key_codes)]
fig = px.line(chart_df, x="MONTH", y="amount", color="account_name", markers=True)
fig.update_layout(xaxis_title="월", yaxis_title="금액", legend_title="계정")
st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- Formula sanity check ---
with st.expander("🔍 계산식 정합성 체크 (계산값 vs RAW 자체 값)"):
    st.caption(
        "GP1, 경상이익처럼 '계산식'으로 정의한 계정은 RAW_SYSTEM(PL)에도 이미 자체 값이 "
        "저장되어 있습니다. 두 값을 비교해서 우리 계산식이 실제 데이터와 맞는지 확인합니다."
    )
    check_df = check_calculated_accounts_against_raw(raw_pl_df, monthly_totals, account_rules)
    if check_df.empty:
        st.info("정의된 계산식 계정이 없습니다.")
    else:
        display_check = check_df.rename(columns={
            "account_code": "계정코드",
            "account_name": "계정명",
            "our_total": "우리 계산값",
            "raw_total": "RAW 자체 값",
            "difference": "차이",
        })
        st.dataframe(
            display_check.style.format({"우리 계산값": "{:,.2f}", "RAW 자체 값": "{:,.2f}", "차이": "{:,.4f}"}),
            use_container_width=True,
            hide_index=True,
        )
        max_diff = check_df["difference"].abs().max()
        if max_diff < 1:
            st.success(f"모든 계산식 계정의 차이가 {max_diff:.4f} 이내입니다 (반올림 오차 수준).")
        else:
            st.error(f"최대 차이 {max_diff:,.2f} — 계산식을 다시 확인하세요.")
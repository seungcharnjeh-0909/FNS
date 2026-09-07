"""
pages/3_PL_Analysis.py

- User picks a business scope (default: KAM 2, per project spec
  section 41 - "Focus on KAM 2. Do NOT automate North Central W&D
  yet") and enters the closing year/month directly (no hardcoded
  month control cell, per section 10).
- Checks whether RAW_SYSTEM(PL) actually has data through that month
  yet (Phase 1 finding: it can lag behind the workbook's nominal
  closing month).
- Runs the P/L Engine (core/pnl_engine.py) to produce a current-month /
  YTD summary by management account, scoped to the selected business.
- Shows a built-in formula sanity check comparing our calculated
  accounts (e.g. GP1, Ordinary Profit) against the value RAW already
  stores for that same account code.
- Compares our KAM 2 totals against the official 손익_KAM 2▷ report
  sheet's grand-total row - the "golden source" check from spec
  section 21.
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from core.period_engine import get_closing_period, check_data_availability
from core.mapping_engine import filter_to_scope
from core.pnl_engine import (
    load_account_rules,
    compute_monthly_totals,
    compute_pnl_summary,
    check_calculated_accounts_against_raw,
)
from core.golden_source import load_report_layout, load_kam2_report_totals

st.set_page_config(page_title="P/L Analysis", page_icon="💰", layout="wide")
st.title("💰 P/L Analysis (손익 분석)")

if "raw_pl_df" not in st.session_state or "mapping_df" not in st.session_state:
    st.warning("아직 불러온 데이터가 없습니다. 먼저 **Data Import** 페이지로 이동하세요.")
    st.stop()

raw_pl_df = st.session_state["raw_pl_df"]
mapping_df = st.session_state["mapping_df"]

st.info(
    "현재는 **PERF(실적) 시나리오만** 계산합니다. RAW_SYSTEM(PL)에는 BP/RP/FCST/전년 "
    "데이터가 없기 때문입니다 — 이 데이터들이 연결되면 시나리오 비교 화면을 추가합니다."
)

# --- Business scope selector ---
st.subheader("사업 범위 선택")
scope_options = sorted(mapping_df["LVL_1"].dropna().unique().tolist())
default_index = scope_options.index("KAM 2 사업실") if "KAM 2 사업실" in scope_options else 0
scope = st.selectbox(
    "LVL 1 기준 사업 범위 (Phase 1 기본값: KAM 2 사업실)",
    options=scope_options,
    index=default_index,
)
scoped_pl_df = filter_to_scope(raw_pl_df, mapping_df, lvl1_name=scope)
scope_cctr_count = mapping_df.loc[mapping_df["LVL_1"] == scope, "CCTR_CODE"].nunique()
st.caption(f"범위: **{scope}** ({scope_cctr_count}개 CCTR)")

if scoped_pl_df.empty:
    st.error(f"선택하신 범위('{scope}')에 해당하는 RAW 데이터가 없습니다.")
    st.stop()

# --- Closing period input (직접 입력) ---
st.subheader("마감 기간 선택")
c1, c2 = st.columns(2)
closing_year = c1.number_input("마감 연도", min_value=2000, max_value=2100, value=2026, step=1)
closing_month = c2.number_input("마감 월", min_value=1, max_value=12, value=8, step=1)

period = get_closing_period(int(closing_year), int(closing_month))
availability = check_data_availability(scoped_pl_df, period.month)

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

# --- Run the P/L Engine (scoped) ---
CONFIG_PATH = Path(__file__).parent.parent / "config" / "account_rules.json"
account_rules = load_account_rules(CONFIG_PATH)

monthly_totals = compute_monthly_totals(scoped_pl_df, account_rules)
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
    check_df = check_calculated_accounts_against_raw(scoped_pl_df, monthly_totals, account_rules)
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

# --- Golden source comparison (Excel report vs our Python calculation) ---
st.divider()
st.subheader("🏆 골든소스 비교 — 손익_KAM 2▷ 리포트 vs Python 계산값")
st.caption(
    "엑셀 워크북의 공식 리포트 시트(손익_KAM 2▷)에 이미 계산되어 있는 값과, "
    "우리가 RAW 데이터로부터 새로 계산한 값을 나란히 비교합니다. "
    "이 비교는 현재 'KAM 2 사업실' 범위에서만 검증되었습니다."
)

if scope != "KAM 2 사업실":
    st.info("골든소스 비교는 현재 'KAM 2 사업실' 범위에서만 지원됩니다.")
elif "workbook_bytes" not in st.session_state:
    st.info("골든소스 비교를 하려면 Data Import 페이지에서 워크북을 다시 업로드하세요.")
else:
    layout_path = Path(__file__).parent.parent / "config" / "report_sheet_layout.json"
    layout = load_report_layout(layout_path)
    golden = load_kam2_report_totals(st.session_state["workbook_bytes"], layout, key_codes)

    if golden.empty:
        st.warning("리포트 시트에서 비교할 값을 찾지 못했습니다.")
    else:
        golden_month = golden[golden["MONTH"] == effective_month]
        ours_month = monthly_totals[
            (monthly_totals["MONTH"] == effective_month) & (monthly_totals["account_code"].isin(key_codes))
        ]
        compare = ours_month.merge(golden_month, on=["MONTH", "account_code"], how="left")
        compare["difference"] = compare["amount"] - compare["excel_value"]

        display_compare = compare.rename(columns={
            "account_code": "계정코드",
            "account_name": "계정명",
            "amount": "Python 계산값",
            "excel_value": "Excel 값 (손익_KAM 2▷)",
            "difference": "차이",
        })[["계정코드", "계정명", "Python 계산값", "Excel 값 (손익_KAM 2▷)", "차이"]]

        st.dataframe(
            display_compare.style.format({
                "Python 계산값": "{:,.2f}",
                "Excel 값 (손익_KAM 2▷)": "{:,.2f}",
                "차이": "{:,.4f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

        max_diff = compare["difference"].abs().max()
        if pd.isna(max_diff):
            st.warning("비교할 데이터가 부족합니다.")
        elif max_diff < 1:
            st.success(f"✅ Excel과 Python 결과가 일치합니다 (최대 차이 {max_diff:.4f}).")
        else:
            st.error(f"❌ 최대 차이 {max_diff:,.2f} — 원인을 확인해야 합니다.")
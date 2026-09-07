"""
pages/7_Management_Performance.py

Reproduces the 보고용_KAM 2 report (project spec section 26): for each
sub-organization (LVL_2: KAM 2 운영 1/2/3, 사업지원), shows Revenue,
GP1, Cost Expense, GP2, Business Profit, Operating Profit for the
current month, previous month, and YTD - plus an editable variance
reason box (project spec section 27).

Revenue/GP1/GP2/Business Profit/Operating Profit come from RAW P/L
(core/pnl_engine.py + account_rules.json). Cost Expense (4200800) comes
from RAW Expense (expense_category_rules.json) - the real report
blends both sources into one table, same as here.

Plan (BP) and Previous Year columns are not available yet (RAW only
has the PERF scenario) and are shown as "준비중" rather than silently
left blank or filled with zero.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from core.period_engine import get_closing_period, check_data_availability
from core.mapping_engine import filter_to_scope
from core.pnl_engine import load_account_rules, compute_grouped_monthly_totals

st.set_page_config(page_title="Management Performance", page_icon="📋", layout="wide")
st.title("📋 Management Performance Report (경영실적 보고)")

if "raw_pl_df" not in st.session_state or "raw_expense_df" not in st.session_state or "mapping_df" not in st.session_state:
    st.warning("아직 불러온 데이터가 없습니다. 먼저 **Data Import** 페이지로 이동하세요.")
    st.stop()

raw_pl_df = st.session_state["raw_pl_df"]
raw_expense_df = st.session_state["raw_expense_df"]
mapping_df = st.session_state["mapping_df"]

st.info(
    "**계획(BP)/전년 컬럼은 아직 준비중입니다** (RAW 데이터에 PERF 실적만 있습니다). "
    "빈 칸으로 두거나 0으로 채우지 않고 '준비중'으로 명시적으로 표시합니다 — "
    "계획 대비 -100%처럼 잘못된 숫자가 나오는 것을 막기 위해서입니다."
)
st.warning(
    "⚠️ **Net Sales / GP1 / Cost Expense는 조직별로도 검증 완료**되었습니다 (엑셀 리포트와 정확히 일치). "
    "하지만 **GP2 / Business Profit / Operating Profit은 아직 배부(allocation) 로직이 완전히 검증되지 않았습니다** "
    "— 그룹 단위로는 실제로 약간의 차이가 발생할 수 있습니다 (config/account_rules.json 참고). "
    "참고용으로만 사용하세요."
)

# --- Business scope selector ---
st.subheader("사업 범위 선택")
scope_options = sorted(mapping_df["LVL_1"].dropna().unique().tolist())
default_index = scope_options.index("KAM 2 사업실") if "KAM 2 사업실" in scope_options else 0
scope = st.selectbox(
    "LVL 1 기준 사업 범위 (Phase 1 기본값: KAM 2 사업실)",
    options=scope_options,
    index=default_index,
    key="mgmt_scope",
)
scoped_pl_df = filter_to_scope(raw_pl_df, mapping_df, lvl1_name=scope)
scoped_exp_df = filter_to_scope(raw_expense_df, mapping_df, lvl1_name=scope)

if scoped_pl_df.empty or scoped_exp_df.empty:
    st.error(f"선택하신 범위('{scope}')에 해당하는 RAW 데이터가 없습니다.")
    st.stop()

# --- Closing period input ---
st.subheader("마감 기간 선택")
c1, c2 = st.columns(2)
closing_year = c1.number_input("마감 연도", min_value=2000, max_value=2100, value=2026, step=1, key="mgmt_year")
closing_month = c2.number_input("마감 월", min_value=1, max_value=12, value=8, step=1, key="mgmt_month")

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

if effective_month <= 1:
    st.error("전월 데이터가 없어 보고서를 만들 수 없습니다.")
    st.stop()

compare_month = effective_month - 1
ytd_months = [m for m in period.ytd_months if m <= effective_month]

# --- Compute grouped totals ---
PL_CONFIG = Path(__file__).parent.parent / "config" / "account_rules.json"
EXP_CONFIG = Path(__file__).parent.parent / "config" / "expense_category_rules.json"
pl_rules = load_account_rules(PL_CONFIG)
exp_rules = load_account_rules(EXP_CONFIG)

pl_grouped = compute_grouped_monthly_totals(scoped_pl_df, mapping_df, pl_rules, "LVL_2")
exp_grouped = compute_grouped_monthly_totals(scoped_exp_df, mapping_df, exp_rules, "LVL_2")

# Report accounts: Revenue/GP1/GP2/Business Profit/Operating Profit from
# P/L, Cost Expense from Expense - the real report blends both sources.
REPORT_ACCOUNTS = [
    ("4100000", "Net Sales", pl_grouped),
    ("4300000", "GP 1", pl_grouped),
    ("4200800", "Cost Expense", exp_grouped),
    ("4400000", "GP 2", pl_grouped),
    ("4500000", "Business Profit", pl_grouped),
    ("5200000", "Op Profit", pl_grouped),
]

groups = sorted(pl_grouped["LVL_2"].dropna().unique().tolist())

st.divider()
st.subheader(f"경영실적 보고 — 당월({effective_month}월) / 전월({compare_month}월) / 누계(1~{effective_month}월)")

for group in groups:
    st.markdown(f"#### {group}")
    rows = []
    for code, label, source_df in REPORT_ACCOUNTS:
        sub = source_df[(source_df["LVL_2"] == group) & (source_df["account_code"] == code)]
        current = sub.loc[sub["MONTH"] == effective_month, "amount"]
        prior = sub.loc[sub["MONTH"] == compare_month, "amount"]
        ytd = sub.loc[sub["MONTH"].isin(ytd_months), "amount"]

        current_val = float(current.iloc[0]) if not current.empty else 0.0
        prior_val = float(prior.iloc[0]) if not prior.empty else 0.0
        ytd_val = float(ytd.sum()) if not ytd.empty else 0.0
        mom_diff = current_val - prior_val

        rows.append({
            "계정": label,
            "전년": "준비중",
            "계획(BP)": "준비중",
            "전월": prior_val,
            "당월 실적": current_val,
            "전월비": mom_diff,
            "누계 실적": ytd_val,
            "연간 계획": "준비중",
        })

    report_table = pd.DataFrame(rows)
    st.dataframe(
        report_table.style.format({
            "전월": "{:,.0f}", "당월 실적": "{:,.0f}",
            "전월비": "{:+,.0f}", "누계 실적": "{:,.0f}",
        }),
        use_container_width=True,
        hide_index=True,
    )

    # --- Variance reason (project spec section 27) ---
    reason_key = f"variance_reason_{group}_{closing_year}_{closing_month}"
    st.text_area(
        f"📝 {group} — 전월대비 증감사유",
        key=reason_key,
        placeholder="예: ESMI 자재 3구간 수익 감소 등 (이 세션 동안만 저장됩니다 - 영구 저장은 DB 연동 후 지원 예정)",
        height=80,
    )
    st.divider()

st.caption(
    "증감사유는 현재 이 브라우저 세션에서만 유지됩니다. 새로고침하거나 다른 기기에서 열면 "
    "사라집니다 — Phase 3(데이터베이스 연동) 이후 영구 저장을 지원할 예정입니다."
)
"""
pages/4_Expense_Analysis.py

- Same business scope + closing period selectors as P/L Analysis.
- Category summary (Cost-nature Expense, SG&A, Total Expense) using
  the same base/calculated engine as P/L (core/pnl_engine.py) with
  config/expense_category_rules.json.
- Organizational breakdown by a chosen dimension (LVL 1/2/3, CCTR,
  BIZ_UNIT, UNIT, TEAM) - core/expense_engine.compute_expense_by_dimension.
- Top expense driver ranking for the selected month - only covers the
  Cost-nature branch, since SG&A detail rows are not populated in this
  workbook's RAW extract (see expense_category_rules.json notes).
"""

from pathlib import Path

import plotly.express as px
import streamlit as st

from core.period_engine import get_closing_period, check_data_availability
from core.mapping_engine import filter_to_scope
from core.pnl_engine import load_account_rules, compute_monthly_totals, compute_pnl_summary
from core.expense_engine import compute_expense_by_dimension, top_expense_drivers

st.set_page_config(page_title="Expense Analysis", page_icon="🧾", layout="wide")
st.title("🧾 Expense Analysis (비용 분석)")

if "raw_expense_df" not in st.session_state or "mapping_df" not in st.session_state:
    st.warning("아직 불러온 데이터가 없습니다. 먼저 **Data Import** 페이지로 이동하세요.")
    st.stop()

raw_expense_df = st.session_state["raw_expense_df"]
mapping_df = st.session_state["mapping_df"]

st.info(
    "총 비용은 검증된 상위 합계 계정(원가성경비 4200800 + 판매관리비 5100000)만 사용합니다. "
    "상세(leaf) 항목을 전부 더하면 판매관리비 쪽 상세 데이터가 비어 있어 총액이 조용히 "
    "누락되기 때문입니다 — 자세한 내용은 config/expense_category_rules.json 참고."
)

# --- Business scope selector ---
st.subheader("사업 범위 선택")
scope_options = sorted(mapping_df["LVL_1"].dropna().unique().tolist())
default_index = scope_options.index("KAM 2 사업실") if "KAM 2 사업실" in scope_options else 0
scope = st.selectbox(
    "LVL 1 기준 사업 범위 (Phase 1 기본값: KAM 2 사업실)",
    options=scope_options,
    index=default_index,
    key="expense_scope",
)
scoped_exp_df = filter_to_scope(raw_expense_df, mapping_df, lvl1_name=scope)
scope_cctr_count = mapping_df.loc[mapping_df["LVL_1"] == scope, "CCTR_CODE"].nunique()
st.caption(f"범위: **{scope}** ({scope_cctr_count}개 CCTR)")

if scoped_exp_df.empty:
    st.error(f"선택하신 범위('{scope}')에 해당하는 RAW 데이터가 없습니다.")
    st.stop()

# --- Closing period input ---
st.subheader("마감 기간 선택")
c1, c2 = st.columns(2)
closing_year = c1.number_input("마감 연도", min_value=2000, max_value=2100, value=2026, step=1, key="exp_year")
closing_month = c2.number_input("마감 월", min_value=1, max_value=12, value=8, step=1, key="exp_month")

period = get_closing_period(int(closing_year), int(closing_month))
availability = check_data_availability(scoped_exp_df, period.month)

if not availability["is_closing_month_available"]:
    st.warning(
        f"선택하신 {period.year}년 {period.month}월 비용이 아직 RAW 데이터에 없습니다. "
        f"현재 데이터는 **{availability['max_month_in_data']}월**까지만 있습니다. "
        f"아래 결과는 {availability['max_month_in_data']}월을 당월 기준으로 대신 계산한 것입니다."
    )
    effective_month = availability["max_month_in_data"]
else:
    effective_month = period.month

if effective_month == 0:
    st.error("RAW 데이터에 유효한 월별 비용이 전혀 없습니다.")
    st.stop()

effective_ytd_months = [m for m in period.ytd_months if m <= effective_month]

# --- Category summary (reuses the P/L engine's generic base/calculated logic) ---
CONFIG_PATH = Path(__file__).parent.parent / "config" / "expense_category_rules.json"
category_rules = load_account_rules(CONFIG_PATH)

monthly_totals = compute_monthly_totals(scoped_exp_df, category_rules)
summary = compute_pnl_summary(monthly_totals, current_month=effective_month, ytd_months=effective_ytd_months)

st.divider()
st.subheader(f"비용 요약 — 당월({effective_month}월) / 누계(1~{effective_month}월)")
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

st.divider()

# --- Organizational breakdown ---
st.subheader("조직별 비용 분해")
dimension_options = {
    "LVL 1": "LVL_1",
    "LVL 2": "LVL_2",
    "LVL 3": "LVL_3",
    "BIZ UNIT": "BIZ_UNIT",
    "UNIT": "UNIT",
    "TEAM": "TEAM",
    "CCTR": "CCTR",
}
dimension_label = st.selectbox("분해 기준", options=list(dimension_options.keys()))
dimension_col = dimension_options[dimension_label]

by_dim = compute_expense_by_dimension(scoped_exp_df, mapping_df, dimension_col)
by_dim_month = by_dim[by_dim["MONTH"] == effective_month].sort_values("amount", ascending=False)

fig = px.bar(by_dim_month, x=dimension_col, y="amount", text_auto=".2s")
fig.update_layout(xaxis_title=dimension_label, yaxis_title="금액")
st.plotly_chart(fig, use_container_width=True)
st.dataframe(
    by_dim_month.rename(columns={dimension_col: dimension_label, "amount": "당월 비용"})
    .style.format({"당월 비용": "{:,.0f}"}),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# --- Top expense drivers ---
st.subheader(f"{effective_month}월 비용 상위 항목 (원가성경비 상세 기준)")
st.caption(
    "이 순위는 원가성경비(4200800) 계열의 상세 항목만 포함합니다. "
    "판매관리비(SG&A)는 이 워크북의 RAW 데이터에 상세 내역이 없고 합계만 있어 순위에서 제외됩니다."
)
top_n = st.slider("표시할 항목 수", min_value=5, max_value=20, value=10)
top_drivers = top_expense_drivers(scoped_exp_df, effective_month, top_n=top_n)

fig2 = px.bar(top_drivers.sort_values("amount"), x="amount", y="Item Name", orientation="h")
fig2.update_layout(xaxis_title="금액", yaxis_title="")
st.plotly_chart(fig2, use_container_width=True)
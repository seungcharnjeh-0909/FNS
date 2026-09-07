"""
pages/5_Variance_Analysis.py

- Same business scope + closing period selectors as other pages.
- Month-over-month variance for P/L accounts and expense categories
  (core/variance_engine.py) - Variance Amount, Variance %, Contribution
  %, and Rank, per project spec section 16.
- Top expense line-item variance drivers between the two months
  (core/expense_engine.expense_item_variance) - project spec section
  17, "Top Variance Driver Engine".

NOTE: only month-over-month comparisons are available today. BP/RP/
Previous-Year comparisons will use the exact same variance_engine
functions once those scenarios are wired into the data model - nothing
here is hardcoded to "previous month" as a concept.
"""

from pathlib import Path

import plotly.express as px
import streamlit as st

from core.period_engine import get_closing_period, check_data_availability
from core.mapping_engine import filter_to_scope
from core.pnl_engine import load_account_rules, compute_monthly_totals
from core.variance_engine import compute_variance
from core.expense_engine import expense_item_variance

st.set_page_config(page_title="Variance Analysis", page_icon="📉", layout="wide")
st.title("📉 Variance Analysis (증감 분석)")

if "raw_pl_df" not in st.session_state or "raw_expense_df" not in st.session_state or "mapping_df" not in st.session_state:
    st.warning("아직 불러온 데이터가 없습니다. 먼저 **Data Import** 페이지로 이동하세요.")
    st.stop()

raw_pl_df = st.session_state["raw_pl_df"]
raw_expense_df = st.session_state["raw_expense_df"]
mapping_df = st.session_state["mapping_df"]

st.info(
    "현재는 **전월 대비(MoM)** 증감만 계산합니다. 계획(BP)/전년 데이터가 아직 없기 때문입니다. "
    "그 데이터가 연결되면 같은 화면에 '계획 대비', '전년 대비' 탭이 추가됩니다."
)

# --- Business scope selector ---
st.subheader("사업 범위 선택")
scope_options = sorted(mapping_df["LVL_1"].dropna().unique().tolist())
default_index = scope_options.index("KAM 2 사업실") if "KAM 2 사업실" in scope_options else 0
scope = st.selectbox(
    "LVL 1 기준 사업 범위 (Phase 1 기본값: KAM 2 사업실)",
    options=scope_options,
    index=default_index,
    key="variance_scope",
)
scoped_pl_df = filter_to_scope(raw_pl_df, mapping_df, lvl1_name=scope)
scoped_exp_df = filter_to_scope(raw_expense_df, mapping_df, lvl1_name=scope)
scope_cctr_count = mapping_df.loc[mapping_df["LVL_1"] == scope, "CCTR_CODE"].nunique()
st.caption(f"범위: **{scope}** ({scope_cctr_count}개 CCTR)")

if scoped_pl_df.empty or scoped_exp_df.empty:
    st.error(f"선택하신 범위('{scope}')에 해당하는 RAW 데이터가 없습니다.")
    st.stop()

# --- Closing period input ---
st.subheader("마감 기간 선택")
c1, c2 = st.columns(2)
closing_year = c1.number_input("마감 연도", min_value=2000, max_value=2100, value=2026, step=1, key="var_year")
closing_month = c2.number_input("마감 월", min_value=1, max_value=12, value=8, step=1, key="var_month")

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
    st.error("전월 데이터가 없어 증감 분석을 할 수 없습니다 (1월은 비교할 전월이 없습니다).")
    st.stop()

compare_month = effective_month - 1
st.caption(f"비교 기준: **{effective_month}월 vs {compare_month}월** (전월 대비)")


def _style_variance(df):
    return df.style.format({
        "당월": "{:,.0f}",
        "전월": "{:,.0f}",
        "증감액": "{:,.0f}",
        "증감률": "{:+.1%}",
        "기여도": "{:.1%}",
    }).map(lambda v: "color: #1a7f37" if isinstance(v, bool) and v else "", subset=["증가여부"])


# --- P/L variance ---
st.divider()
st.subheader(f"손익 계정 증감 — {effective_month}월 vs {compare_month}월")

CONFIG_PATH = Path(__file__).parent.parent / "config" / "account_rules.json"
account_rules = load_account_rules(CONFIG_PATH)
monthly_pl = compute_monthly_totals(scoped_pl_df, account_rules)
pl_variance = compute_variance(monthly_pl, current_month=effective_month, compare_month=compare_month)

display_pl = pl_variance.rename(columns={
    "account_code": "계정코드", "account_name": "계정명",
    "current_value": "당월", "compare_value": "전월",
    "variance_amount": "증감액", "variance_pct": "증감률",
    "contribution_pct": "기여도", "is_positive": "증가여부",
})
st.dataframe(_style_variance(display_pl), use_container_width=True, hide_index=True)

fig1 = px.bar(
    pl_variance.sort_values("variance_amount"),
    x="variance_amount", y="account_name", orientation="h",
    color="is_positive", color_discrete_map={True: "#1a7f37", False: "#c0392b"},
)
fig1.update_layout(xaxis_title="증감액", yaxis_title="", showlegend=False)
st.plotly_chart(fig1, use_container_width=True)

# --- Expense category variance ---
st.divider()
st.subheader(f"비용 카테고리 증감 — {effective_month}월 vs {compare_month}월")

EXPENSE_CONFIG_PATH = Path(__file__).parent.parent / "config" / "expense_category_rules.json"
expense_rules = load_account_rules(EXPENSE_CONFIG_PATH)
monthly_exp = compute_monthly_totals(scoped_exp_df, expense_rules)
exp_variance = compute_variance(monthly_exp, current_month=effective_month, compare_month=compare_month)

display_exp = exp_variance.rename(columns={
    "account_code": "계정코드", "account_name": "계정명",
    "current_value": "당월", "compare_value": "전월",
    "variance_amount": "증감액", "variance_pct": "증감률",
    "contribution_pct": "기여도", "is_positive": "증가여부",
})
st.dataframe(_style_variance(display_exp), use_container_width=True, hide_index=True)

# --- Top variance drivers (expense line items) ---
st.divider()
st.subheader(f"비용 상위 증감 항목 (Top Variance Drivers) — {effective_month}월 vs {compare_month}월")
st.caption(
    "원가성경비 계열 상세 항목만 포함합니다 (판매관리비는 상세 데이터가 없습니다). "
    "증감액 절대값 기준 상위 항목입니다."
)
top_n = st.slider("표시할 항목 수", min_value=5, max_value=20, value=10, key="variance_top_n")
item_variance = expense_item_variance(scoped_exp_df, effective_month, compare_month, top_n=top_n)

display_items = item_variance.rename(columns={
    "amount_a": f"{effective_month}월", "amount_b": f"{compare_month}월",
    "variance": "증감액", "variance_pct": "증감률",
})
st.dataframe(
    display_items.style.format({
        f"{effective_month}월": "{:,.0f}",
        f"{compare_month}월": "{:,.0f}",
        "증감액": "{:,.0f}",
        "증감률": "{:+.1%}",
    }),
    use_container_width=True,
    hide_index=True,
)

fig2 = px.bar(
    item_variance.sort_values("variance"),
    x="variance", y="Item Name", orientation="h",
)
fig2.update_layout(xaxis_title="증감액", yaxis_title="")
st.plotly_chart(fig2, use_container_width=True)
"""
pages/6_Reconciliation.py

Reproduces the real workbook's hidden 검증 (verification) sheet as a
proper Reconciliation Engine (project spec section 19):
- Compares shared account codes (4410000, 4420000) between RAW P/L and
  RAW Expense, per CCTR and month.
- PASS / WARNING / ERROR status from configurable tolerance.
- Summary card (total checks, passed, warnings, errors, total diff).
- Exception table (everything that isn't PASS) with CSV export.
"""

from pathlib import Path

import streamlit as st

from core.mapping_engine import filter_to_scope
from core.reconciliation_engine import (
    load_reconciliation_rules,
    compute_reconciliation,
    summarize_reconciliation,
)

st.set_page_config(page_title="Reconciliation", page_icon="🔎", layout="wide")
st.title("🔎 Reconciliation (검증)")

if "raw_pl_df" not in st.session_state or "raw_expense_df" not in st.session_state or "mapping_df" not in st.session_state:
    st.warning("아직 불러온 데이터가 없습니다. 먼저 **Data Import** 페이지로 이동하세요.")
    st.stop()

raw_pl_df = st.session_state["raw_pl_df"]
raw_expense_df = st.session_state["raw_expense_df"]
mapping_df = st.session_state["mapping_df"]

st.info(
    "실제 엑셀 워크북의 숨겨진 '검증' 시트와 같은 로직입니다: P/L RAW 데이터와 비용 RAW 데이터에 "
    "공통으로 존재하는 계정(원가성 인건비 4410000, 원가성 일반경비 4420000)이 CCTR·월별로 "
    "정확히 일치하는지 대조합니다. 두 원본 데이터는 같은 시스템(MNG)에서 추출된 것이므로, "
    "여기서 차이가 나면 계산 오류가 아니라 **데이터 추출/적재 문제**를 의미합니다."
)

# --- Business scope selector ---
st.subheader("사업 범위 선택")
scope_options = sorted(mapping_df["LVL_1"].dropna().unique().tolist())
default_index = scope_options.index("KAM 2 사업실") if "KAM 2 사업실" in scope_options else 0
scope = st.selectbox(
    "LVL 1 기준 사업 범위 (Phase 1 기본값: KAM 2 사업실)",
    options=scope_options,
    index=default_index,
    key="recon_scope",
)
scoped_pl_df = filter_to_scope(raw_pl_df, mapping_df, lvl1_name=scope)
scoped_exp_df = filter_to_scope(raw_expense_df, mapping_df, lvl1_name=scope)
scope_cctr_count = mapping_df.loc[mapping_df["LVL_1"] == scope, "CCTR_CODE"].nunique()
st.caption(f"범위: **{scope}** ({scope_cctr_count}개 CCTR)")

if scoped_pl_df.empty or scoped_exp_df.empty:
    st.error(f"선택하신 범위('{scope}')에 해당하는 RAW 데이터가 없습니다.")
    st.stop()

# --- Run the Reconciliation Engine ---
CONFIG_PATH = Path(__file__).parent.parent / "config" / "reconciliation_rules.json"
rules = load_reconciliation_rules(CONFIG_PATH)

recon_df = compute_reconciliation(scoped_pl_df, scoped_exp_df, rules)
summary = summarize_reconciliation(recon_df)

st.divider()

# --- Summary cards ---
st.subheader("검증 요약")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("전체 체크", f"{summary['total_checks']:,}")
c2.metric("🟢 PASS", f"{summary['passed']:,}")
c3.metric("🟡 WARNING", f"{summary['warnings']:,}")
c4.metric("🔴 ERROR", f"{summary['errors']:,}")
c5.metric("총 차이 절대값", f"{summary['total_abs_difference']:,.2f}")

if summary["errors"] == 0 and summary["warnings"] == 0:
    st.success("✅ 모든 항목이 PASS입니다 — P/L과 비용 원본 데이터가 완전히 일치합니다.")
elif summary["errors"] > 0:
    st.error(f"❌ {summary['errors']}건의 ERROR가 있습니다 — 데이터 추출/적재 과정을 확인하세요.")
else:
    st.warning(f"🟡 {summary['warnings']}건의 WARNING이 있습니다 — 반올림 오차 수준인지 확인하세요.")

st.divider()

# --- Exceptions table ---
st.subheader("예외 항목 (PASS가 아닌 건)")
exceptions = recon_df[recon_df["status"] != "PASS"].sort_values("difference", key=lambda s: s.abs(), ascending=False)

if exceptions.empty:
    st.info("예외 항목이 없습니다.")
else:
    display_exceptions = exceptions.rename(columns={
        "account_code": "계정코드", "account_name": "계정명",
        "pl_value": "P/L 값", "exp_value": "비용 값",
        "difference": "차이", "status": "상태",
    })
    st.dataframe(
        display_exceptions.style.format({"P/L 값": "{:,.2f}", "비용 값": "{:,.2f}", "차이": "{:,.2f}"}),
        use_container_width=True,
        hide_index=True,
    )
    csv_bytes = exceptions.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "예외 항목 CSV로 내려받기",
        data=csv_bytes,
        file_name="reconciliation_exceptions.csv",
        mime="text/csv",
    )

st.divider()

# --- Full detail (optional) ---
with st.expander(f"🔍 전체 상세 내역 보기 ({len(recon_df)}건, CCTR × 계정 × 월)"):
    display_all = recon_df.rename(columns={
        "account_code": "계정코드", "account_name": "계정명",
        "pl_value": "P/L 값", "exp_value": "비용 값",
        "difference": "차이", "status": "상태",
    })
    st.dataframe(
        display_all.style.format({"P/L 값": "{:,.2f}", "비용 값": "{:,.2f}", "차이": "{:,.2f}"}),
        use_container_width=True,
        hide_index=True,
    )
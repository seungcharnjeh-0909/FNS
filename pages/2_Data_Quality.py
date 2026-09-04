"""
pages/2_Data_Quality.py

STEP 10 of the Phase 1 roadmap: a basic Data Quality page.

Reads the DataFrames stored in session_state by 1_Data_Import.py and
runs:
- validation_engine checks (nulls, duplicate keys, bad month values)
  on RAW_SYSTEM(PL) and RAW_SYSTEM(EXP)
- mapping_engine checks (unmapped CCTR, duplicate mapping, blank
  hierarchy) using Code Mapping as master data
"""

import streamlit as st

from core.validation_engine import run_checks, summarize
from core.mapping_engine import (
    detect_unmapped_cctr,
    detect_duplicate_mapping,
    detect_blank_hierarchy,
)

st.set_page_config(page_title="Data Quality", page_icon="✅", layout="wide")
st.title("✅ Data Quality")

required_keys = ["raw_pl_df", "raw_expense_df", "mapping_df"]
if not all(k in st.session_state for k in required_keys):
    st.warning("No data loaded yet. Go to **Data Import** first.")
    st.stop()

raw_pl_df = st.session_state["raw_pl_df"]
raw_expense_df = st.session_state["raw_expense_df"]
mapping_df = st.session_state["mapping_df"]


def _status_badge(status: str) -> str:
    return {"PASS": "🟢 PASS", "WARNING": "🟡 WARNING", "ERROR": "🔴 ERROR"}.get(status, status)


def _render_check_table(results_df, key_prefix: str) -> None:
    summary = summarize(results_df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Checks", summary["total_checks"])
    c2.metric("Passed", summary["passed"])
    c3.metric("Errors", summary["errors"])

    display_df = results_df.copy()
    display_df["status"] = display_df["status"].apply(_status_badge)
    st.dataframe(display_df, use_container_width=True, hide_index=True, key=key_prefix)


# --- RAW_SYSTEM(PL) checks ---
st.header("RAW_SYSTEM(PL) Checks")
pl_results = run_checks(raw_pl_df, label="RAW_SYSTEM(PL)")
_render_check_table(pl_results, "pl_checks")

st.divider()

# --- RAW_SYSTEM(EXP) checks ---
st.header("RAW_SYSTEM(EXP) Checks")
exp_results = run_checks(raw_expense_df, label="RAW_SYSTEM(EXP)")
_render_check_table(exp_results, "exp_checks")

st.divider()

# --- Mapping checks ---
st.header("Code Mapping Checks")

st.subheader("Unmapped CCTR — found in RAW_SYSTEM(PL)")
unmapped_pl = detect_unmapped_cctr(raw_pl_df, mapping_df, cctr_col="CCTR")
if unmapped_pl.empty:
    st.success("No unmapped CCTR codes found in RAW_SYSTEM(PL).")
else:
    st.error(f"{len(unmapped_pl)} unmapped CCTR code(s) found in RAW_SYSTEM(PL).")
    st.dataframe(unmapped_pl, use_container_width=True, hide_index=True)

st.subheader("Unmapped CCTR — found in RAW_SYSTEM(EXP)")
unmapped_exp = detect_unmapped_cctr(raw_expense_df, mapping_df, cctr_col="CCTR")
if unmapped_exp.empty:
    st.success("No unmapped CCTR codes found in RAW_SYSTEM(EXP).")
else:
    st.error(f"{len(unmapped_exp)} unmapped CCTR code(s) found in RAW_SYSTEM(EXP).")
    st.dataframe(unmapped_exp, use_container_width=True, hide_index=True)

st.subheader("Duplicate Mapping Keys")
dup_mapping = detect_duplicate_mapping(mapping_df)
if dup_mapping.empty:
    st.success("No duplicate CCTR codes found in Code Mapping.")
else:
    st.error(f"{len(dup_mapping)} row(s) involved in duplicate CCTR mapping keys.")
    st.dataframe(dup_mapping, use_container_width=True, hide_index=True)

st.subheader("Blank Organizational Hierarchy (LVL 1 / 2 / 3)")
blank_hierarchy = detect_blank_hierarchy(mapping_df)
if blank_hierarchy.empty:
    st.success("No mapping rows with a blank hierarchy level.")
else:
    st.warning(f"{len(blank_hierarchy)} mapping row(s) have a blank LVL 1/2/3 value.")
    st.dataframe(blank_hierarchy, use_container_width=True, hide_index=True)

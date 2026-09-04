"""
pages/1_Data_Import.py

STEP 5-9 of the Phase 1 roadmap:
- Upload the existing Management Performance Excel workbook.
- Detect all sheets and their visible/hidden state (Workbook Inspector).
- Confirm the 3 required sheets are present.
- Load RAW_SYSTEM(PL), RAW_SYSTEM(EXP), Code Mapping into DataFrames.
- Show row count / column count / column names / sample data for each.

Loaded DataFrames are stored in st.session_state so the Data Quality
page (and later pages) can reuse them without re-parsing the workbook.
"""

import json
from pathlib import Path

import streamlit as st

from core.workbook_loader import load_workbook
from core.workbook_inspector import inspect_sheets, check_required_sheets
from core.raw_pl_parser import parse_raw_pl
from core.raw_expense_parser import parse_raw_expense
from core.mapping_engine import load_code_mapping

st.set_page_config(page_title="Data Import", page_icon="📥", layout="wide")
st.title("📥 Data Import")

CONFIG_DIR = Path(__file__).parent.parent / "config"
sheet_config = json.loads((CONFIG_DIR / "sheet_config.json").read_text(encoding="utf-8"))
settings = json.loads((CONFIG_DIR / "settings.json").read_text(encoding="utf-8"))

uploaded_file = st.file_uploader(
    "Upload the Management Performance Excel workbook (.xlsx)",
    type=["xlsx"],
)

if uploaded_file is None:
    st.info("Upload a workbook to begin. No data leaves your machine — this runs locally.")
    st.stop()

# --- Load workbook (openpyxl) for structural inspection ---
with st.spinner("Opening workbook..."):
    try:
        wb = load_workbook(uploaded_file)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

st.success(f"Workbook opened. {len(wb.sheetnames)} sheets found.")

# --- STEP 7: sheet inventory ---
st.subheader("Workbook Inspector — Sheet Inventory")
sheet_summary = inspect_sheets(wb)
st.dataframe(sheet_summary, use_container_width=True, hide_index=True)

# --- Confirm required sheets exist ---
st.subheader("Required Sheets Check")
required_sheets = settings["required_sheets"]
required_check = check_required_sheets(wb, required_sheets)
st.dataframe(required_check, use_container_width=True, hide_index=True)

if not required_check["found"].all():
    st.error("One or more required sheets are missing. Cannot continue loading raw data.")
    st.stop()

st.divider()

# --- STEP 8: load the 3 required datasets ---
# openpyxl workbook was opened read-only for inspection; pandas needs
# its own read of the file, so we rewind the uploaded file buffer.
uploaded_file.seek(0)

with st.spinner("Loading RAW_SYSTEM(PL), RAW_SYSTEM(EXP), and Code Mapping..."):
    try:
        raw_pl_df = parse_raw_pl(
            uploaded_file,
            sheet_name=sheet_config["raw_pl"]["sheet_name"],
            header_row=sheet_config["raw_pl"]["header_row"],
        )
        uploaded_file.seek(0)
        raw_expense_df = parse_raw_expense(
            uploaded_file,
            sheet_name=sheet_config["raw_expense"]["sheet_name"],
            header_row=sheet_config["raw_expense"]["header_row"],
        )
        uploaded_file.seek(0)
        mapping_df = load_code_mapping(
            uploaded_file,
            sheet_name=sheet_config["code_mapping"]["sheet_name"],
            header_row=sheet_config["code_mapping"]["header_row"],
        )
    except ValueError as exc:
        st.error(f"Failed to load required data: {exc}")
        st.stop()

# Persist for other pages
st.session_state["raw_pl_df"] = raw_pl_df
st.session_state["raw_expense_df"] = raw_expense_df
st.session_state["mapping_df"] = mapping_df

st.success("All 3 required datasets loaded successfully.")


def _show_dataset(title: str, df) -> None:
    st.subheader(title)
    c1, c2 = st.columns(2)
    c1.metric("Rows", f"{len(df):,}")
    c2.metric("Columns", len(df.columns))
    st.write("Columns:", list(df.columns))
    st.dataframe(df.head(10), use_container_width=True, hide_index=True)


_show_dataset("RAW_SYSTEM(PL)", raw_pl_df)
_show_dataset("RAW_SYSTEM(EXP)", raw_expense_df)
_show_dataset("Code Mapping", mapping_df)

st.divider()
st.info("Next: open **Data Quality** in the sidebar to run automated checks on this data.")

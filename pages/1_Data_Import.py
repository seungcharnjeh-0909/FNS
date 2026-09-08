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
from core import db

st.set_page_config(page_title="Data Import", page_icon="📥", layout="wide")
st.title("📥 데이터 임포트")

CONFIG_DIR = Path(__file__).parent.parent / "config"
sheet_config = json.loads((CONFIG_DIR / "sheet_config.json").read_text(encoding="utf-8"))
settings = json.loads((CONFIG_DIR / "settings.json").read_text(encoding="utf-8"))

# --- DB connection (optional - app still works without it, just without persistence) ---
try:
    conn = db.get_connection()
    db.init_schema(conn)
    db_available = True
except Exception as exc:
    conn = None
    db_available = False
    with st.expander("🐞 DB 연결 에러 자세히 보기 (개발용)"):
        st.exception(exc)

if db_available:
    mapping_status = db.get_mapping_status(conn)
    if mapping_status["count"] > 0:
        st.caption(
            f"💾 DB에 저장된 Code Mapping: {mapping_status['count']}개 CCTR "
            f"(마지막 저장: {mapping_status['last_saved']})"
        )
else:
    st.caption("⚠️ DB에 연결되지 않았습니다 - 이번 세션 동안만 데이터가 유지됩니다.")

uploaded_file = st.file_uploader(
    "경영실적 엑셀 워크북을 업로드하세요 (.xlsx)",
    type=["xlsx"],
)

if uploaded_file is None:
    st.info("워크북을 업로드하면 시작됩니다. 데이터는 로컬에서만 처리되며 외부로 전송되지 않습니다.")
    st.stop()

# --- Load workbook (openpyxl) for structural inspection ---
# Keep the raw bytes too - later pages (e.g. golden-source comparison)
# need to reopen the workbook for direct cell access, and the uploaded
# file's buffer position is not safe to rely on across reruns.
st.session_state["workbook_bytes"] = uploaded_file.getvalue()

with st.spinner("워크북을 여는 중..."):
    try:
        wb = load_workbook(uploaded_file)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

st.success(f"워크북을 열었습니다. 총 {len(wb.sheetnames)}개 시트를 찾았습니다.")

# --- STEP 7: sheet inventory ---
st.subheader("워크북 인스펙터 — 시트 목록")
sheet_summary = inspect_sheets(wb)
st.dataframe(sheet_summary, use_container_width=True, hide_index=True)

# --- Confirm required sheets exist ---
st.subheader("필수 시트 확인")
required_sheets = settings["required_sheets"]
required_check = check_required_sheets(wb, required_sheets)
st.dataframe(required_check, use_container_width=True, hide_index=True)

if not required_check["found"].all():
    st.error("필수 시트 중 일부가 누락되었습니다. 원본 데이터를 계속 불러올 수 없습니다.")
    st.stop()

st.divider()

# --- STEP 8: load the 3 required datasets ---
# openpyxl workbook was opened read-only for inspection; pandas needs
# its own read of the file, so we rewind the uploaded file buffer.
uploaded_file.seek(0)

with st.spinner("RAW_SYSTEM(PL), RAW_SYSTEM(EXP), Code Mapping을 불러오는 중..."):
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
        st.error(f"필수 데이터 로드에 실패했습니다: {exc}")
        st.stop()

# Persist for other pages
st.session_state["raw_pl_df"] = raw_pl_df
st.session_state["raw_expense_df"] = raw_expense_df
st.session_state["mapping_df"] = mapping_df

st.success("필수 데이터 3종을 모두 성공적으로 불러왔습니다.")


def _show_dataset(title: str, df) -> None:
    st.subheader(title)
    c1, c2 = st.columns(2)
    c1.metric("행 수", f"{len(df):,}")
    c2.metric("열 수", len(df.columns))
    st.write("컬럼 목록:", list(df.columns))
    st.dataframe(df.head(10), use_container_width=True, hide_index=True)


_show_dataset("RAW_SYSTEM(PL)", raw_pl_df)
_show_dataset("RAW_SYSTEM(EXP)", raw_expense_df)
_show_dataset("Code Mapping", mapping_df)

# --- Save mapping to DB for reuse (across sessions and devices) ---
if db_available:
    st.divider()
    st.subheader("💾 Code Mapping을 DB에 저장")
    st.caption(
        "조직 매핑 정보는 자주 바뀌지 않으니, DB에 저장해두면 다음번 분석 때 "
        "워크북을 다시 안 올려도 됩니다 (RAW 파일만 올리는 기능은 추후 지원 예정)."
    )
    if st.button("지금 매핑을 DB에 저장"):
        try:
            db.save_mapping(conn, mapping_df)
            st.success(f"저장 완료: {len(mapping_df)}개 CCTR")
        except Exception as exc:
            st.error(f"저장 실패: {exc}")

st.divider()
st.info("다음 단계: 사이드바에서 **Data Quality**를 열어 자동 검증 결과를 확인하세요.")
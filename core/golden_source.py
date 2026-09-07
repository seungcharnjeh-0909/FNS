"""
golden_source.py

INPUT:
    The original workbook (reopened from raw bytes, since we need
    direct cell access to a formatted report sheet rather than a flat
    data table) plus config/report_sheet_layout.json.

PROCESS:
    Per project spec section 21 ("Existing Excel as Golden Source"),
    Python results must be compared against the official Excel report
    - not just against RAW data. This module reads the KAM 2 scope's
    grand-total row ("사업실 합계") straight out of the 손익_KAM 2▷
    report sheet's "2026 PERF" column block, using only the column
    positions recorded in config (never hardcoded in Python).

OUTPUT:
    load_kam2_report_totals() -> DataFrame: MONTH, account_code, excel_value
"""

import io
import json
from pathlib import Path

import openpyxl
import pandas as pd


def load_report_layout(path: str | Path) -> dict:
    """Load report_sheet_layout.json, dropping the '_notes' key."""
    layout = json.loads(Path(path).read_text(encoding="utf-8"))
    layout.pop("_notes", None)
    return layout


def load_kam2_report_totals(workbook_bytes: bytes, layout: dict, account_codes: list[str]) -> pd.DataFrame:
    """
    Extract the KAM 2 grand-total row's monthly 2026 PERF values for a
    set of account codes, directly from the official report sheet.

    Args:
        workbook_bytes: raw bytes of the uploaded .xlsx file.
        layout: dict loaded from report_sheet_layout.json (one entry
                keyed by sheet name, e.g. "손익_KAM 2▷").
        account_codes: which account codes to extract, e.g.
                       ["4100000", "4200000", "4300000"].

    Returns:
        DataFrame: MONTH, account_code, excel_value. Empty if the sheet
        or matching rows are not found (never raises - this is a
        best-effort comparison, not a required data source).
    """
    sheet_name = next(iter(layout.keys()), None)
    if sheet_name is None:
        return pd.DataFrame(columns=["MONTH", "account_code", "excel_value"])

    cfg = layout[sheet_name]
    wb = openpyxl.load_workbook(io.BytesIO(workbook_bytes), data_only=True, read_only=True)
    if sheet_name not in wb.sheetnames:
        return pd.DataFrame(columns=["MONTH", "account_code", "excel_value"])

    ws = wb[sheet_name]
    lvl1_idx = cfg["lvl1_col_index"]
    code_idx = cfg["account_code_col_index"]
    perf_start = cfg["perf_2026_start_col_index"]
    month_count = cfg["perf_2026_month_count"]
    total_label = cfg["total_row_lvl1_label"]

    found_codes: set[str] = set()
    rows = []
    for row in ws.iter_rows(min_row=cfg["data_start_row"], values_only=True):
        if len(row) <= perf_start + month_count:
            continue
        lvl1 = row[lvl1_idx]
        code = str(row[code_idx]) if row[code_idx] is not None else None
        if lvl1 != total_label or code not in account_codes or code in found_codes:
            continue

        for month_offset in range(month_count):
            value = row[perf_start + month_offset]
            rows.append({
                "MONTH": month_offset + 1,
                "account_code": code,
                "excel_value": float(value) if value is not None else 0.0,
            })
        found_codes.add(code)  # only take the first matching total row per code

        if found_codes == set(account_codes):
            break

    return pd.DataFrame(rows)
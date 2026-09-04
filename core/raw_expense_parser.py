"""
raw_expense_parser.py

INPUT:
    File path/buffer for the source workbook, plus sheet_config.json
    (sheet name + header row for RAW_SYSTEM(EXP)).

PROCESS:
    Same idea as raw_pl_parser.py, but for the expense feed
    (~96,000 rows). Kept as a separate module because the Expense
    Engine (Phase 1 STEP 15+ in the roadmap) will eventually need
    expense-specific columns/logic that P/L does not.

OUTPUT:
    A pandas DataFrame with columns:
    INDEX, MONTH, CCTR, CCTR Name, Item Code, Item Name, PERF, composite_key
"""

from typing import Union

import pandas as pd


def parse_raw_expense(file: Union[str, "object"], sheet_name: str, header_row: int) -> pd.DataFrame:
    """
    Load and clean the RAW_SYSTEM(EXP) sheet.

    Args:
        file: path or file-like object for the source workbook.
        sheet_name: name of the expense raw sheet (from config).
        header_row: 1-indexed row number that holds the column headers.

    Returns:
        Cleaned DataFrame ready for downstream expense calculations.
    """
    df = pd.read_excel(
        file,
        sheet_name=sheet_name,
        header=header_row - 1,
        engine="openpyxl",
    )

    required = ["INDEX", "MONTH", "CCTR", "CCTR Name", "Item Code", "Item Name", "PERF"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"RAW_SYSTEM(EXP) is missing expected columns: {missing}")

    df = df[required].copy()
    df["PERF"] = pd.to_numeric(df["PERF"], errors="coerce")
    df["MONTH"] = pd.to_numeric(df["MONTH"], errors="coerce").astype("Int64")

    df["composite_key"] = (
        df["MONTH"].astype(str) + df["CCTR"].astype(str) + df["Item Code"].astype(str)
    )

    return df.reset_index(drop=True)

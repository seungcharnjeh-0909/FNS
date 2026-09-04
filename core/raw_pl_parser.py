"""
raw_pl_parser.py

INPUT:
    File path/buffer for the source workbook, plus sheet_config.json
    (sheet name + header row for RAW_SYSTEM(PL)).

PROCESS:
    Reads the RAW_SYSTEM(PL) sheet with pandas (vectorized, no
    row-by-row loops), validates the required columns are present,
    coerces PERF to numeric, and builds the composite key
    (MONTH + CCTR + Item Code) that the old workbook used for VLOOKUP -
    in the new system this key exists only as a column, ready for a
    pandas merge instead of thousands of individual lookups.

OUTPUT:
    A pandas DataFrame with columns:
    INDEX, MONTH, CCTR, CCTR Name, Item Code, Item Name, PERF, composite_key
"""

from typing import Union

import pandas as pd


def parse_raw_pl(file: Union[str, "object"], sheet_name: str, header_row: int) -> pd.DataFrame:
    """
    Load and clean the RAW_SYSTEM(PL) sheet.

    Args:
        file: path or file-like object for the source workbook.
        sheet_name: name of the P/L raw sheet (from config).
        header_row: 1-indexed row number that holds the column headers.

    Returns:
        Cleaned DataFrame ready for downstream P/L calculations.
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
        raise ValueError(f"RAW_SYSTEM(PL) is missing expected columns: {missing}")

    df = df[required].copy()
    df["PERF"] = pd.to_numeric(df["PERF"], errors="coerce")
    df["MONTH"] = pd.to_numeric(df["MONTH"], errors="coerce").astype("Int64")

    # This replaces the old VLOOKUP composite key (MONTH + CCTR + Item Code).
    # Keeping it as a plain column means later joins are a single
    # DataFrame.merge() instead of 7,000+ individual lookups.
    df["composite_key"] = (
        df["MONTH"].astype(str) + df["CCTR"].astype(str) + df["Item Code"].astype(str)
    )

    return df.reset_index(drop=True)

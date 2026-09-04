"""
mapping_engine.py

INPUT:
    The Code Mapping sheet (master data: CCTR -> organizational
    hierarchy) plus the RAW P/L and RAW Expense DataFrames.

PROCESS:
    - Loads Code Mapping as its own DataFrame (treated as MASTER DATA,
      per project spec section 7 - not copied into every monthly file).
    - Detects CCTR codes that appear in RAW data but have no mapping
      row (unmapped CCTR).
    - Detects duplicate CCTR codes inside the mapping table itself
      (a mapping key should be unique).
    - Detects mapping rows with a blank organizational hierarchy
      (LVL 1 / LVL 2 / LVL 3 missing), which would break grouping
      later.

OUTPUT:
    load_code_mapping()        -> DataFrame of the mapping master data
    detect_unmapped_cctr()     -> DataFrame of CCTR codes missing a mapping
    detect_duplicate_mapping() -> DataFrame of duplicate CCTR CODE rows
    detect_blank_hierarchy()   -> DataFrame of mapping rows with blank LVL columns
"""

from typing import Union

import pandas as pd

# Source column name -> clean internal name
_COLUMN_RENAME = {
    "CODE": "CCTR_CODE",
    "NAME": "CCTR_NAME",
    "ENTITY": "ENTITY",
    "L/S": "L_S",
    "BIZ UNIT": "BIZ_UNIT",
    "DIVISION": "DIVISION",
    "UNIT": "UNIT",
    "TEAM": "TEAM",
    "PERF GROUP": "PERF_GROUP",
    "LVL 1": "LVL_1",
    "LVL 2": "LVL_2",
    "LVL 3": "LVL_3",
    "비고": "REMARK",
}


def load_code_mapping(file: Union[str, "object"], sheet_name: str, header_row: int) -> pd.DataFrame:
    """
    Load the Code Mapping sheet as master data.

    Args:
        file: path or file-like object for the source workbook.
        sheet_name: name of the mapping sheet (from config), default "Code Mapping".
        header_row: 1-indexed row number that holds the column headers.

    Returns:
        DataFrame with clean column names (see _COLUMN_RENAME).
    """
    df = pd.read_excel(
        file,
        sheet_name=sheet_name,
        header=header_row - 1,
        engine="openpyxl",
    )
    df = df.rename(columns=_COLUMN_RENAME)

    keep_cols = [c for c in _COLUMN_RENAME.values() if c in df.columns]
    df = df[keep_cols].copy()

    # Drop fully blank trailing rows that Excel sometimes carries in the used range.
    df = df.dropna(subset=["CCTR_CODE"]).reset_index(drop=True)
    return df


def detect_unmapped_cctr(raw_df: pd.DataFrame, mapping_df: pd.DataFrame, cctr_col: str = "CCTR") -> pd.DataFrame:
    """
    Find CCTR codes used in raw data that have no row in Code Mapping.

    Args:
        raw_df: RAW P/L or RAW Expense DataFrame (must contain cctr_col).
        mapping_df: output of load_code_mapping().
        cctr_col: name of the CCTR column in raw_df.

    Returns:
        DataFrame with one column "CCTR" listing each unmapped code once,
        plus a "row_count" of how many raw rows reference it.
    """
    mapped_codes = set(mapping_df["CCTR_CODE"].astype(str))
    raw = raw_df.copy()
    raw["CCTR"] = raw[cctr_col].astype(str)

    unmapped = raw.loc[~raw["CCTR"].isin(mapped_codes)]
    if unmapped.empty:
        return pd.DataFrame(columns=["CCTR", "row_count"])

    result = (
        unmapped.groupby("CCTR")
        .size()
        .reset_index(name="row_count")
        .sort_values("row_count", ascending=False)
        .reset_index(drop=True)
    )
    return result


def detect_duplicate_mapping(mapping_df: pd.DataFrame) -> pd.DataFrame:
    """
    Find CCTR codes that appear more than once in the mapping master data.
    A duplicate mapping key is dangerous because a merge/join would
    silently fan out rows.

    Returns:
        DataFrame of the full mapping rows involved in a duplicate,
        empty if none found.
    """
    dup_mask = mapping_df["CCTR_CODE"].duplicated(keep=False)
    return mapping_df.loc[dup_mask].sort_values("CCTR_CODE").reset_index(drop=True)


def detect_blank_hierarchy(mapping_df: pd.DataFrame) -> pd.DataFrame:
    """
    Find mapping rows where the organizational hierarchy (LVL 1/2/3) is
    genuinely blank (NaN) rather than the valid placeholder "-".

    Returns:
        DataFrame of mapping rows with at least one blank LVL column.
    """
    lvl_cols = [c for c in ["LVL_1", "LVL_2", "LVL_3"] if c in mapping_df.columns]
    if not lvl_cols:
        return pd.DataFrame()

    blank_mask = mapping_df[lvl_cols].isna().any(axis=1)
    return mapping_df.loc[blank_mask].reset_index(drop=True)

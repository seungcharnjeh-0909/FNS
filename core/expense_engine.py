"""
expense_engine.py

INPUT:
    - Cleaned RAW_SYSTEM(EXP) DataFrame (~96,000 rows, from raw_expense_parser).
    - Code Mapping DataFrame (from mapping_engine) for organizational
      grouping (LVL 1/2/3, DIVISION, BIZ_UNIT, UNIT, TEAM).
    - config/expense_category_rules.json for verified top-level totals
      (see core/pnl_engine.py - the same base/calculated engine is
      reused here since the aggregation logic is identical; only the
      account codes differ).

PROCESS:
    1. Organizational breakdown: for a chosen grouping dimension (e.g.
       LVL_1, CCTR, DIVISION), sum ONLY the two verified top-level
       expense codes (4200800 Cost-nature Expense, 5100000 SG&A) per
       group. This avoids the double-counting / silent-zero risk
       described in expense_category_rules.json - never sum "every
       detail row" blindly (project spec section 16: don't hide errors
       by converting to zero).
    2. Top expense driver: rank individual detail (leaf) line items by
       amount for a chosen month. Only meaningful within the Cost-nature
       branch today, because SG&A detail rows are not populated in this
       workbook's RAW extract - the UI must say so explicitly rather
       than implying a complete ranking.

OUTPUT:
    compute_expense_by_dimension() -> DataFrame: MONTH, <dimension>, amount
    top_expense_drivers()          -> DataFrame: Item Name, amount (ranked)
"""

import pandas as pd

# The only two codes we trust as complete, non-double-counted totals.
_VERIFIED_TOTAL_CODES = ["4200800", "5100000"]


def compute_expense_by_dimension(
    exp_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
    dimension: str,
) -> pd.DataFrame:
    """
    Break total expense (Cost-nature + SG&A) down by an organizational
    dimension, month by month.

    Args:
        exp_df: cleaned RAW_SYSTEM(EXP) DataFrame.
        mapping_df: output of mapping_engine.load_code_mapping().
        dimension: one of the mapping columns to group by, e.g.
                   "LVL_1", "LVL_2", "LVL_3", "DIVISION", "BIZ_UNIT",
                   "UNIT", "TEAM", or "CCTR" (CCTR comes from exp_df
                   itself, not the mapping).

    Returns:
        DataFrame: MONTH, <dimension>, amount
    """
    totals_only = exp_df[exp_df["Item Code"].isin(_VERIFIED_TOTAL_CODES)]

    if dimension == "CCTR":
        grouped = totals_only.groupby(["MONTH", "CCTR"])["PERF"].sum().reset_index()
        return grouped.rename(columns={"PERF": "amount"})

    merged = totals_only.merge(
        mapping_df[["CCTR_CODE", dimension]],
        left_on="CCTR",
        right_on="CCTR_CODE",
        how="left",
    )
    merged[dimension] = merged[dimension].fillna("(미매핑)")
    grouped = merged.groupby(["MONTH", dimension])["PERF"].sum().reset_index()
    return grouped.rename(columns={"PERF": "amount"})


def top_expense_drivers(exp_df: pd.DataFrame, month: int, top_n: int = 10) -> pd.DataFrame:
    """
    Rank individual expense line items (detail/leaf accounts) by amount
    for a single month. Detail codes are identified as any Item Code
    that does NOT end in "00" (the convention this workbook uses for
    subtotal/rollup rows).

    NOTE: only the Cost-nature (42xxxxx) branch has real detail data in
    this workbook's RAW extract - SG&A (51xxxxx) detail rows are all
    zero, so they will not appear here even though SG&A has a real
    total. Callers should tell the user this ranking excludes SG&A
    detail.

    Args:
        exp_df: cleaned RAW_SYSTEM(EXP) DataFrame.
        month: which MONTH to rank.
        top_n: how many items to return.

    Returns:
        DataFrame: Item Name, amount - sorted by amount descending.
    """
    is_detail = ~exp_df["Item Code"].str.endswith("00")
    month_detail = exp_df.loc[is_detail & (exp_df["MONTH"] == month)]

    ranked = (
        month_detail.groupby("Item Name")["PERF"]
        .sum()
        .reset_index()
        .rename(columns={"PERF": "amount"})
        .sort_values("amount", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    return ranked
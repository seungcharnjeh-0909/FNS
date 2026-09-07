"""
period_engine.py

INPUT:
    A closing year and closing month chosen by the user (no more
    hardcoded "month control cell" like the old Excel workbook - see
    project spec section 10).

PROCESS:
    Derives every date-based value the rest of the app needs from that
    single (year, month) pair: previous month, previous year same
    month, the YTD month range, and the remaining months in the year.
    Also checks whether the RAW data actually contains the closing
    month yet (see Phase 1 finding: RAW_SYSTEM(PL) can lag behind the
    workbook's nominal closing month).

OUTPUT:
    ClosingPeriod dataclass + check_data_availability() helper.
"""

from dataclasses import dataclass

import pandas as pd


@dataclass
class ClosingPeriod:
    """All date-derived values for a single closing period."""
    year: int
    month: int                      # 1-12, the month being closed
    previous_month: int             # 1-12 (wraps to 12 of previous year if month == 1)
    previous_month_year: int
    previous_year: int              # same month, one year earlier
    ytd_months: list[int]           # e.g. [1, 2, ..., month]
    remaining_months: list[int]     # e.g. [month+1, ..., 12]


def get_closing_period(year: int, month: int) -> ClosingPeriod:
    """
    Build a ClosingPeriod from a user-chosen year and month.

    Args:
        year: closing year, e.g. 2026.
        month: closing month, 1-12.

    Returns:
        ClosingPeriod with all derived values filled in.

    Raises:
        ValueError: if month is not between 1 and 12.
    """
    if not 1 <= month <= 12:
        raise ValueError(f"month must be between 1 and 12, got {month}")

    if month == 1:
        previous_month = 12
        previous_month_year = year - 1
    else:
        previous_month = month - 1
        previous_month_year = year

    return ClosingPeriod(
        year=year,
        month=month,
        previous_month=previous_month,
        previous_month_year=previous_month_year,
        previous_year=year - 1,
        ytd_months=list(range(1, month + 1)),
        remaining_months=list(range(month + 1, 13)),
    )


def check_data_availability(raw_df: pd.DataFrame, closing_month: int) -> dict:
    """
    Check whether the RAW data actually contains data through the
    chosen closing month. In practice the RAW extract can lag behind
    the workbook's nominal closing month (e.g. an "August closing"
    file whose RAW feed only goes through July because August actuals
    were not final yet when the extract was taken).

    Args:
        raw_df: cleaned RAW P/L or Expense DataFrame (must have MONTH).
        closing_month: the month the user selected to close.

    Returns:
        dict with:
            max_month_in_data: latest MONTH value present in the data
            is_closing_month_available: bool
            missing_months: list of months between the latest available
                             month and the closing month (exclusive of
                             the latest available, inclusive of closing)
    """
    months_with_data = raw_df.loc[raw_df["PERF"].notna() | raw_df["PERF"].isna(), "MONTH"]
    # Only count a month as "available" if at least one row has a non-zero,
    # non-null PERF - an all-zero month usually means "not actually loaded yet".
    nonzero = raw_df.loc[raw_df["PERF"].fillna(0) != 0, "MONTH"]
    max_month = int(nonzero.max()) if not nonzero.empty else 0

    missing_months = [m for m in range(max_month + 1, closing_month + 1)]

    return {
        "max_month_in_data": max_month,
        "is_closing_month_available": closing_month <= max_month,
        "missing_months": missing_months,
    }
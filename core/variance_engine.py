"""
variance_engine.py

INPUT:
    Any "monthly_totals" long-format DataFrame with columns
    MONTH, account_code (or category_code), account_name, amount -
    the same shape produced by core.pnl_engine.compute_monthly_totals().
    This makes the Variance Engine reusable across P/L accounts,
    expense categories, or any future scenario (BP/RP/FCST) once those
    are available - not tied to one specific dataset.

PROCESS:
    Per project spec section 16 ("Variance Engine"):
    - Variance Amount = current - compare
    - Variance % = variance amount / |compare value| (kept as NaN, not
      silently 0, when the compare value is 0 - dividing by zero is a
      real data situation, not an error to hide)
    - Contribution % = this account's variance amount / total absolute
      variance across all accounts
    - Rank = ordered by absolute variance amount, biggest movers first

    A second function does the same comparison but summed over a set
    of months first (for YTD-vs-YTD comparisons once more scenarios
    exist).

OUTPUT:
    compute_variance()     -> DataFrame: one row per account, current
                               value, compare value, variance amount/%,
                               contribution %, rank
    compute_ytd_variance() -> same shape, but comparing two YTD month sets
"""

import numpy as np
import pandas as pd


def _variance_table(current: pd.Series, compare: pd.Series, names: pd.Series) -> pd.DataFrame:
    """Shared calculation once both sides are reduced to one value per account."""
    df = pd.DataFrame({
        "current_value": current,
        "compare_value": compare,
    }).fillna(0.0)
    df["account_name"] = df.index.map(names)
    df["variance_amount"] = df["current_value"] - df["compare_value"]

    # Keep NaN (not 0) when compare_value is 0 - a real "cannot compute %"
    # situation, not something to hide (project spec section 16).
    df["variance_pct"] = np.where(
        df["compare_value"] != 0,
        df["variance_amount"] / df["compare_value"].abs(),
        np.nan,
    )

    total_abs_variance = df["variance_amount"].abs().sum()
    df["contribution_pct"] = np.where(
        total_abs_variance != 0,
        df["variance_amount"].abs() / total_abs_variance,
        np.nan,
    )

    df["is_positive"] = df["variance_amount"] > 0

    df = df.sort_values("variance_amount", key=lambda s: s.abs(), ascending=False)
    df["rank"] = range(1, len(df) + 1)

    df.index.name = "account_code"
    return df.reset_index()[
        ["rank", "account_code", "account_name", "current_value", "compare_value",
         "variance_amount", "variance_pct", "contribution_pct", "is_positive"]
    ]


def compute_variance(monthly_totals: pd.DataFrame, current_month: int, compare_month: int) -> pd.DataFrame:
    """
    Compare a single current month against a single comparison month
    (e.g. current month vs previous month).

    Args:
        monthly_totals: output of pnl_engine.compute_monthly_totals().
        current_month: the month to evaluate, e.g. 7.
        compare_month: the month to compare against, e.g. 6.

    Returns:
        DataFrame ranked by absolute variance amount (biggest movers first).
    """
    names = monthly_totals.drop_duplicates("account_code").set_index("account_code")["account_name"]
    current = monthly_totals.loc[monthly_totals["MONTH"] == current_month].set_index("account_code")["amount"]
    compare = monthly_totals.loc[monthly_totals["MONTH"] == compare_month].set_index("account_code")["amount"]
    return _variance_table(current, compare, names)


def compute_ytd_variance(monthly_totals: pd.DataFrame, current_ytd_months: list[int], compare_ytd_months: list[int]) -> pd.DataFrame:
    """
    Compare two YTD ranges (e.g. this year's Jan-Jul vs a prior period's
    Jan-Jul, once that data exists as a separate scenario).

    Args:
        monthly_totals: output of pnl_engine.compute_monthly_totals().
        current_ytd_months: months to sum for the "current" side.
        compare_ytd_months: months to sum for the "compare" side.

    Returns:
        DataFrame ranked by absolute variance amount.
    """
    names = monthly_totals.drop_duplicates("account_code").set_index("account_code")["account_name"]
    current = (
        monthly_totals.loc[monthly_totals["MONTH"].isin(current_ytd_months)]
        .groupby("account_code")["amount"].sum()
    )
    compare = (
        monthly_totals.loc[monthly_totals["MONTH"].isin(compare_ytd_months)]
        .groupby("account_code")["amount"].sum()
    )
    return _variance_table(current, compare, names)
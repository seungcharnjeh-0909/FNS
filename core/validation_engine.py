"""
validation_engine.py

INPUT:
    A cleaned RAW DataFrame (P/L or Expense) as produced by
    raw_pl_parser / raw_expense_parser.

PROCESS:
    Runs a fixed set of vectorized data-quality checks (no row-by-row
    loops): null CCTR, null Item Code, non-numeric / null PERF amount,
    duplicate composite key, and month values outside 1-12. Each check
    is independent so adding a new one later doesn't touch the others.

OUTPUT:
    run_checks() -> pandas DataFrame, one row per check, columns:
    check_name, status (PASS/WARNING/ERROR), issue_count, description
"""

import pandas as pd

from models.validation import CheckResult


def _status_from_count(count: int, warning_threshold: int = 0) -> str:
    """PASS if no issues, otherwise ERROR (kept simple for Phase 1 - a
    WARNING tier can be introduced later once we know which checks are
    tolerable in small numbers)."""
    return "PASS" if count <= warning_threshold else "ERROR"


def run_checks(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """
    Run the Phase 1 data-quality checklist on a raw DataFrame.

    Args:
        df: cleaned RAW P/L or RAW Expense DataFrame (must contain
            CCTR, Item Code, PERF, MONTH, composite_key columns).
        label: human-readable name of the dataset, used in messages
            (e.g. "RAW_SYSTEM(PL)").

    Returns:
        DataFrame summarizing each check.
    """
    results: list[CheckResult] = []

    # 1. Null CCTR
    null_cctr = int(df["CCTR"].isna().sum())
    results.append(CheckResult(
        check_name="Null CCTR",
        status=_status_from_count(null_cctr),
        issue_count=null_cctr,
        description=f"{label}: rows with a blank CCTR code.",
    ))

    # 2. Null Item Code (account)
    null_item = int(df["Item Code"].isna().sum())
    results.append(CheckResult(
        check_name="Null Item Code",
        status=_status_from_count(null_item),
        issue_count=null_item,
        description=f"{label}: rows with a blank Item Code (account).",
    ))

    # 3. Non-numeric / null PERF amount
    null_perf = int(df["PERF"].isna().sum())
    results.append(CheckResult(
        check_name="Non-numeric / blank PERF amount",
        status=_status_from_count(null_perf),
        issue_count=null_perf,
        description=f"{label}: rows where PERF could not be read as a number.",
    ))

    # 4. Duplicate composite key (MONTH + CCTR + Item Code)
    dup_count = int(df["composite_key"].duplicated(keep=False).sum())
    results.append(CheckResult(
        check_name="Duplicate composite key",
        status=_status_from_count(dup_count),
        issue_count=dup_count,
        description=f"{label}: rows sharing the same MONTH+CCTR+Item Code key (would double-count in a merge).",
    ))

    # 5. Unexpected month (outside 1-12)
    bad_month = int(((df["MONTH"] < 1) | (df["MONTH"] > 12) | df["MONTH"].isna()).sum())
    results.append(CheckResult(
        check_name="Unexpected MONTH value",
        status=_status_from_count(bad_month),
        issue_count=bad_month,
        description=f"{label}: rows where MONTH is missing or outside 1-12.",
    ))

    return pd.DataFrame([r.__dict__ for r in results])


def summarize(results: pd.DataFrame) -> dict:
    """
    Roll a checks DataFrame up into totals for a dashboard-style summary.

    Returns:
        dict with total_checks, passed, errors.
    """
    return {
        "total_checks": len(results),
        "passed": int((results["status"] == "PASS").sum()),
        "errors": int((results["status"] == "ERROR").sum()),
    }

"""
reconciliation_engine.py

INPUT:
    - Cleaned RAW_SYSTEM(PL) and RAW_SYSTEM(EXP) DataFrames.
    - config/reconciliation_rules.json: which account codes exist in
      both raw sources and should reconcile, plus PASS/WARNING/ERROR
      tolerance thresholds.

PROCESS:
    This reproduces the real workbook's hidden 검증 (verification)
    sheet (project spec section 19): it compares the same account
    code's total, per CCTR and month, between the P/L raw feed and the
    Expense raw feed. In the source workbook, both feeds are extracted
    from the same underlying system, so a mismatch signals a real data
    problem (an extraction error, a partial refresh, etc.) rather than
    a business calculation error - which is exactly why this check is
    valuable on every closing, not just once.

    Tolerance is configurable (never hardcoded), and a divide-by-zero
    or missing-side case never gets silently rounded to "matches" -
    every combination gets an explicit PASS/WARNING/ERROR status.

OUTPUT:
    compute_reconciliation()   -> DataFrame: MONTH, CCTR, account_code,
                                  account_name, pl_value, exp_value,
                                  difference, status
    summarize_reconciliation() -> dict: total_checks, passed, warnings,
                                  errors, total_abs_difference
"""

import json
from pathlib import Path

import pandas as pd


def load_reconciliation_rules(path: str | Path) -> dict:
    """Load reconciliation_rules.json, dropping the '_notes' documentation key."""
    rules = json.loads(Path(path).read_text(encoding="utf-8"))
    rules.pop("_notes", None)
    return rules


def _status(difference: float, warning_threshold: float, error_threshold: float) -> str:
    """Classify a difference into PASS / WARNING / ERROR using configured tolerance."""
    abs_diff = abs(difference)
    if abs_diff <= warning_threshold:
        return "PASS"
    if abs_diff <= error_threshold:
        return "WARNING"
    return "ERROR"


def compute_reconciliation(pl_df: pd.DataFrame, exp_df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """
    Compare shared account codes between RAW P/L and RAW Expense, per
    CCTR and month.

    Args:
        pl_df: cleaned RAW_SYSTEM(PL) DataFrame (already scoped, e.g.
               to KAM 2 - see mapping_engine.filter_to_scope).
        exp_df: cleaned RAW_SYSTEM(EXP) DataFrame (same scope as pl_df).
        rules: dict loaded from reconciliation_rules.json.

    Returns:
        DataFrame with one row per (account_code, CCTR, MONTH):
        account_code, account_name, CCTR, MONTH, pl_value, exp_value,
        difference, status.
    """
    warning_threshold = rules["tolerance"]["warning_threshold"]
    error_threshold = rules["tolerance"]["error_threshold"]

    rows = []
    for check in rules["checks"]:
        code = check["account_code"]
        name = check["name"]

        pl_side = pl_df.loc[pl_df["Item Code"] == code].groupby(["CCTR", "MONTH"])["PERF"].sum()
        exp_side = exp_df.loc[exp_df["Item Code"] == code].groupby(["CCTR", "MONTH"])["PERF"].sum()

        combined = pd.DataFrame({"pl_value": pl_side, "exp_value": exp_side}).fillna(0.0)
        combined["difference"] = combined["pl_value"] - combined["exp_value"]
        combined["status"] = combined["difference"].apply(
            lambda d: _status(d, warning_threshold, error_threshold)
        )
        combined["account_code"] = code
        combined["account_name"] = name

        combined = combined.reset_index()  # brings CCTR, MONTH back as columns
        rows.append(combined)

    if not rows:
        return pd.DataFrame(columns=[
            "account_code", "account_name", "CCTR", "MONTH",
            "pl_value", "exp_value", "difference", "status",
        ])

    result = pd.concat(rows, ignore_index=True)
    return result[
        ["account_code", "account_name", "CCTR", "MONTH", "pl_value", "exp_value", "difference", "status"]
    ]


def summarize_reconciliation(recon_df: pd.DataFrame) -> dict:
    """
    Roll a reconciliation DataFrame up into totals for a dashboard-style
    summary, per project spec section 19 ("Display summary: Total
    Checks, Passed, Warnings, Errors, Total Difference").

    Returns:
        dict with total_checks, passed, warnings, errors, total_abs_difference.
    """
    return {
        "total_checks": len(recon_df),
        "passed": int((recon_df["status"] == "PASS").sum()),
        "warnings": int((recon_df["status"] == "WARNING").sum()),
        "errors": int((recon_df["status"] == "ERROR").sum()),
        "total_abs_difference": float(recon_df["difference"].abs().sum()),
    }
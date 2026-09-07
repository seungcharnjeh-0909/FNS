"""
pnl_engine.py

INPUT:
    - Cleaned RAW_SYSTEM(PL) DataFrame (from raw_pl_parser).
    - config/account_rules.json: which account codes are "base"
      (sum straight from RAW) vs "calculated" (a formula over other
      accounts already computed).
    - A ClosingPeriod (from period_engine) that says which month is
      "current" and which months make up YTD.

PROCESS:
    This replaces the old workbook's per-account SUMIFS formulas with
    one vectorized groupby, and replaces per-account IF/formula chains
    with a small formula evaluator driven by config instead of hard-
    coded Python per account (see project spec section 14 - "Excel
    Business Logic -> Reusable Software Logic", not a 1:1 port).

    Only "+"/"-" formulas are supported for now (that covers every
    verified relationship in this workbook, e.g. "4100000 - 4200000").

OUTPUT:
    compute_monthly_totals()  -> DataFrame: one row per (MONTH, account code)
    compute_pnl_summary()     -> DataFrame: one row per account, columns
                                 for current-month and YTD totals
    check_calculated_accounts_against_raw() -> DataFrame comparing our
                                 calculated formula result to the value
                                 RAW already stores for that same code
                                 (a lightweight, built-in sanity check)
"""

import json
from pathlib import Path

import pandas as pd


def load_account_rules(path: str | Path) -> dict:
    """Load account_rules.json, dropping the '_notes' documentation key."""
    rules = json.loads(Path(path).read_text(encoding="utf-8"))
    rules.pop("_notes", None)
    return rules


def _evaluate_formula(formula: str, known_values: dict[str, float]) -> float:
    """
    Evaluate a simple "+"/"-" formula string like "4100000 - 4200000".

    Args:
        formula: space-separated formula, e.g. "5200000 + 6100000 - 6200000".
        known_values: dict of account_code -> amount already computed.

    Returns:
        The computed amount.

    Raises:
        KeyError: if the formula references an account not yet computed.
    """
    tokens = formula.split()
    total = known_values[tokens[0]]
    i = 1
    while i < len(tokens):
        op, code = tokens[i], tokens[i + 1]
        value = known_values[code]
        total = total + value if op == "+" else total - value
        i += 2
    return total


def compute_monthly_totals(raw_df: pd.DataFrame, account_rules: dict) -> pd.DataFrame:
    """
    Aggregate RAW_SYSTEM(PL) into one amount per (MONTH, account code)
    for every account in account_rules - base accounts by summing RAW
    rows, calculated accounts by evaluating their formula per month.

    Args:
        raw_df: cleaned RAW_SYSTEM(PL) DataFrame.
        account_rules: dict loaded from account_rules.json.

    Returns:
        Long-format DataFrame: MONTH, account_code, account_name, amount
    """
    months = sorted(raw_df["MONTH"].dropna().unique().tolist())

    # Base accounts: one groupby covers every base account at once.
    base_codes = [c for c, r in account_rules.items() if r["type"] == "base_account"]
    base_sums = (
        raw_df.loc[raw_df["Item Code"].isin(base_codes)]
        .groupby(["MONTH", "Item Code"])["PERF"]
        .sum()
    )

    # month -> {account_code: amount}, filled in as we go so calculated
    # accounts can reference already-computed base (or calculated) accounts.
    per_month_values: dict[int, dict[str, float]] = {m: {} for m in months}
    for month in months:
        for code in base_codes:
            per_month_values[month][code] = float(base_sums.get((month, code), 0.0))

    calculated_codes = [c for c, r in account_rules.items() if r["type"] == "calculated"]
    for month in months:
        for code in calculated_codes:
            formula = account_rules[code]["formula"]
            per_month_values[month][code] = _evaluate_formula(formula, per_month_values[month])

    rows = []
    for month in months:
        for code, rule in account_rules.items():
            rows.append({
                "MONTH": month,
                "account_code": code,
                "account_name": rule["name"],
                "amount": per_month_values[month][code],
            })
    return pd.DataFrame(rows)


def compute_pnl_summary(monthly_totals: pd.DataFrame, current_month: int, ytd_months: list[int]) -> pd.DataFrame:
    """
    Roll monthly totals up into a current-month / YTD summary table,
    in the order accounts are defined in account_rules.json.

    Args:
        monthly_totals: output of compute_monthly_totals().
        current_month: the closing month (1-12).
        ytd_months: list of months to sum for YTD, e.g. [1..8].

    Returns:
        DataFrame: account_code, account_name, current_month, ytd
    """
    current = (
        monthly_totals.loc[monthly_totals["MONTH"] == current_month]
        .set_index("account_code")["amount"]
    )
    ytd = (
        monthly_totals.loc[monthly_totals["MONTH"].isin(ytd_months)]
        .groupby("account_code")["amount"]
        .sum()
    )

    # Preserve account order + names from the first month's rows.
    order = monthly_totals.drop_duplicates("account_code")[["account_code", "account_name"]]

    summary = order.copy()
    summary["current_month"] = summary["account_code"].map(current).fillna(0.0)
    summary["ytd"] = summary["account_code"].map(ytd).fillna(0.0)
    return summary.reset_index(drop=True)


def check_calculated_accounts_against_raw(raw_df: pd.DataFrame, monthly_totals: pd.DataFrame, account_rules: dict) -> pd.DataFrame:
    """
    Built-in sanity check: for every "calculated" account, RAW also
    happens to store its own value for that same account code (the old
    workbook pre-computed it too). Compare our formula-based result to
    what RAW already has - if they diverge, either the formula is wrong
    or RAW's own figure includes something our formula does not.

    Args:
        raw_df: cleaned RAW_SYSTEM(PL) DataFrame.
        monthly_totals: output of compute_monthly_totals().
        account_rules: dict loaded from account_rules.json.

    Returns:
        DataFrame: account_code, account_name, our_total, raw_total, difference
    """
    calculated_codes = [c for c, r in account_rules.items() if r["type"] == "calculated"]
    if not calculated_codes:
        return pd.DataFrame(columns=["account_code", "account_name", "our_total", "raw_total", "difference"])

    our_totals = (
        monthly_totals.loc[monthly_totals["account_code"].isin(calculated_codes)]
        .groupby("account_code")["amount"]
        .sum()
    )
    raw_totals = (
        raw_df.loc[raw_df["Item Code"].isin(calculated_codes)]
        .groupby("Item Code")["PERF"]
        .sum()
    )

    rows = []
    for code in calculated_codes:
        our_val = float(our_totals.get(code, 0.0))
        raw_val = float(raw_totals.get(code, 0.0))
        rows.append({
            "account_code": code,
            "account_name": account_rules[code]["name"],
            "our_total": our_val,
            "raw_total": raw_val,
            "difference": our_val - raw_val,
        })
    return pd.DataFrame(rows)
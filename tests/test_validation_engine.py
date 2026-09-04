"""Tests for core/validation_engine.py using synthetic data only -
no real company data should ever be used in tests."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.validation_engine import run_checks, summarize


def _sample_df() -> pd.DataFrame:
    # Mirrors the STATE AFTER raw_pl_parser/raw_expense_parser have run:
    # PERF is already coerced to numeric (invalid values become NaN),
    # since validation_engine.run_checks() is always called after parsing,
    # never on unparsed raw Excel values.
    return pd.DataFrame({
        "INDEX": ["1A001X1", "1A001X2", "1A001X3"],
        "MONTH": [1, 1, 13],          # row 3 has an invalid month
        "CCTR": ["A001", "A001", None],  # row 3 has a null CCTR
        "CCTR Name": ["Test Unit", "Test Unit", "Test Unit"],
        "Item Code": ["X1", "X2", "X3"],
        "Item Name": ["Revenue", "Cost", "Other"],
        "PERF": [100.0, float("nan"), 50.0],  # row 2 failed numeric conversion upstream
        "composite_key": ["1A001X1", "1A001X2", "13NoneX3"],
    })


def test_run_checks_detects_known_issues():
    df = _sample_df()
    results = run_checks(df, label="TEST")

    by_check = results.set_index("check_name")["issue_count"].to_dict()
    assert by_check["Null CCTR"] == 1
    assert by_check["Non-numeric / blank PERF amount"] == 1
    assert by_check["Unexpected MONTH value"] == 1


def test_summarize_counts_pass_and_error():
    df = _sample_df()
    results = run_checks(df, label="TEST")
    summary = summarize(results)
    assert summary["total_checks"] == 5
    assert summary["errors"] >= 1

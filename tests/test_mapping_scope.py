"""Tests for core/mapping_engine.py scope filtering, using synthetic data."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.mapping_engine import get_scope_cctr_codes, filter_to_scope


def _sample_mapping() -> pd.DataFrame:
    return pd.DataFrame({
        "CCTR_CODE": ["A001", "A002", "B001"],
        "LVL_1": ["KAM 2 사업실", "KAM 2 사업실", "북중부 W&D 사업실"],
    })


def test_get_scope_cctr_codes_returns_only_matching_lvl1():
    mapping_df = _sample_mapping()
    codes = get_scope_cctr_codes(mapping_df, "KAM 2 사업실")
    assert codes == {"A001", "A002"}


def test_filter_to_scope_excludes_out_of_scope_rows():
    mapping_df = _sample_mapping()
    raw_df = pd.DataFrame({
        "CCTR": ["A001", "B001", "A002"],
        "PERF": [100, 200, 300],
    })
    scoped = filter_to_scope(raw_df, mapping_df, lvl1_name="KAM 2 사업실")
    assert set(scoped["CCTR"]) == {"A001", "A002"}
    assert scoped["PERF"].sum() == 400
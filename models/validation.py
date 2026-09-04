"""
validation.py (model)

Defines the shape of one data-quality check result so every engine in
the app (validation_engine, mapping_engine, reconciliation_engine later)
reports issues in the same structure. Keeping this in one place means
the UI (data_quality.py page) only needs to know how to render one type
of object.
"""

from dataclasses import dataclass
from typing import Literal

Status = Literal["PASS", "WARNING", "ERROR"]


@dataclass
class CheckResult:
    """Result of a single data-quality check."""
    check_name: str
    status: Status
    issue_count: int
    description: str

"""
workbook_loader.py

INPUT:
    Path or file-like object pointing to the Management Performance
    Excel workbook (.xlsx).

PROCESS:
    Opens the workbook once with openpyxl in read-only mode so we can
    inspect sheet names / visibility without paying the cost of loading
    every cell into memory twice.

OUTPUT:
    An openpyxl Workbook object that other core modules (inspector,
    parsers) read from.

Why read-only mode:
    The source workbook is ~19MB with 1M+ formulas. read_only=True
    streams rows instead of materializing the whole file, which keeps
    the app responsive.
"""

from pathlib import Path
from typing import Union

import openpyxl
from openpyxl.workbook.workbook import Workbook


def load_workbook(file: Union[str, Path, "object"]) -> Workbook:
    """
    Load an Excel workbook for inspection and raw-data extraction.

    Args:
        file: A file path (str/Path) or a file-like object such as the
              one Streamlit's file_uploader returns.

    Returns:
        An openpyxl Workbook opened in read-only mode with formula
        values (data_only=True) so we get calculated results, not
        formula text.

    Raises:
        ValueError: if the file cannot be opened as an .xlsx workbook.
    """
    try:
        return openpyxl.load_workbook(
            filename=file,
            data_only=True,
            read_only=True,
            keep_links=False,
        )
    except Exception as exc:  # noqa: BLE001 - we want to surface a clean message to the UI
        raise ValueError(f"Could not open this file as an Excel workbook: {exc}") from exc

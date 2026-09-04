"""
app.py

Entry point for the FNS Business Planning Closing Automation System.

Run with:
    streamlit run app.py

This file only sets up page config and a landing screen. Actual
functionality lives in pages/ (Streamlit auto-discovers files in that
folder and lists them in the left sidebar as separate pages).
"""

import json
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Business Planning Closing Automation",
    page_icon="📊",
    layout="wide",
)

SETTINGS_PATH = Path(__file__).parent / "config" / "settings.json"
settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))

st.title(f"📊 {settings['app_name']}")
st.caption(f"{settings['phase']}  ·  Scope: {settings['scope']}")

st.markdown(
    """
    ### Welcome

    This is the local Phase 1 prototype. It does **not** replace the
    official Excel closing process yet - it proves that the source
    data can be read, checked, and understood in Python before any
    calculation logic is rebuilt.

    **Use the pages in the left sidebar:**

    1. **Data Import** — upload the Management Performance workbook,
       confirm required sheets are present, and load the raw data.
    2. **Data Quality** — review automated checks on the raw data and
       the Code Mapping master data.

    ---
    No login, no cloud storage, no multi-user features in this version —
    everything runs locally on your machine for a single session.
    """
)

if "raw_pl_df" in st.session_state:
    st.success("A workbook is currently loaded in this session. Go to **Data Quality** to review it.")
else:
    st.info("No workbook loaded yet. Start on the **Data Import** page.")

"""
db.py

INPUT:
    Streamlit secrets ([connections.postgres]) pointing at a hosted
    Postgres database (Supabase free tier).

PROCESS:
    Provides small, focused helpers on top of Streamlit's built-in SQL
    connection (st.connection) for the two things Phase 1 needs to stop
    losing on every session refresh:
    - Code Mapping master data (so it doesn't need re-uploading)
    - Variance reason notes (project spec section 27)

    A hosted Postgres is used instead of local SQLite specifically
    because the person needs this from more than one device - a local
    SQLite file lives only on whichever machine/server wrote it and
    can't do that.

OUTPUT:
    get_connection(), init_schema(), save_mapping(), load_mapping(),
    save_variance_reason(), load_variance_reasons()
"""

import pandas as pd
import streamlit as st
from sqlalchemy import text


def get_connection():
    """
    Get Streamlit's cached SQL connection, configured via
    st.secrets['connections']['postgres']['url'].
    """
    return st.connection("postgres", type="sql")


def init_schema(conn) -> None:
    """
    Create the tables this app needs, if they don't already exist.
    Safe to call on every app run - CREATE TABLE IF NOT EXISTS is a
    no-op once the tables exist.
    """
    with conn.session as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS code_mapping (
                cctr_code TEXT PRIMARY KEY,
                cctr_name TEXT,
                entity TEXT,
                l_s TEXT,
                biz_unit TEXT,
                division TEXT,
                unit TEXT,
                team TEXT,
                perf_group TEXT,
                lvl_1 TEXT,
                lvl_2 TEXT,
                lvl_3 TEXT,
                remark TEXT,
                updated_at TIMESTAMP DEFAULT now()
            )
        """))
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS variance_reasons (
                id SERIAL PRIMARY KEY,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                page TEXT NOT NULL,
                group_name TEXT NOT NULL,
                reason TEXT,
                updated_at TIMESTAMP DEFAULT now(),
                UNIQUE (year, month, page, group_name)
            )
        """))
        session.commit()


# Mapping between our DataFrame column names and the DB's lowercase column names.
_MAPPING_COLUMNS = {
    "CCTR_CODE": "cctr_code", "CCTR_NAME": "cctr_name", "ENTITY": "entity",
    "L_S": "l_s", "BIZ_UNIT": "biz_unit", "DIVISION": "division",
    "UNIT": "unit", "TEAM": "team", "PERF_GROUP": "perf_group",
    "LVL_1": "lvl_1", "LVL_2": "lvl_2", "LVL_3": "lvl_3", "REMARK": "remark",
}


def save_mapping(conn, mapping_df: pd.DataFrame) -> None:
    """
    Replace the stored Code Mapping master data with the given
    DataFrame. Mapping data is small (tens of rows) and changes rarely,
    so a full replace-on-save is simpler and safer than diffing/upserting.

    Args:
        conn: connection from get_connection().
        mapping_df: output of mapping_engine.load_code_mapping().
    """
    to_save = mapping_df.rename(columns=_MAPPING_COLUMNS)
    db_cols = [c for c in _MAPPING_COLUMNS.values() if c in to_save.columns]
    to_save = to_save[db_cols]

    with conn.session as session:
        session.execute(text("DELETE FROM code_mapping"))
        session.commit()

    to_save.to_sql("code_mapping", conn.engine, if_exists="append", index=False)


def load_mapping(conn) -> pd.DataFrame:
    """
    Load the stored Code Mapping master data, renamed back to the
    column names the rest of the app expects.

    Returns:
        DataFrame in the same shape as mapping_engine.load_code_mapping()
        (CCTR_CODE, CCTR_NAME, ..., LVL_1, LVL_2, LVL_3, REMARK), or an
        empty DataFrame if nothing has been saved yet.
    """
    rename_back = {v: k for k, v in _MAPPING_COLUMNS.items()}
    df = conn.query("SELECT * FROM code_mapping", ttl=0)
    if df.empty:
        return df
    return df.rename(columns=rename_back)[list(rename_back.values())]


def get_mapping_status(conn) -> dict:
    """Quick check for the UI: how many CCTR are stored, and when was it last saved."""
    df = conn.query("SELECT COUNT(*) AS n, MAX(updated_at) AS last_saved FROM code_mapping", ttl=0)
    if df.empty or df.iloc[0]["n"] == 0:
        return {"count": 0, "last_saved": None}
    return {"count": int(df.iloc[0]["n"]), "last_saved": df.iloc[0]["last_saved"]}


def save_variance_reason(conn, year: int, month: int, page: str, group_name: str, reason: str) -> None:
    """
    Upsert a single variance-reason note (project spec section 27:
    "계획대비 증감사유" / "전월대비 증감사유").

    Args:
        conn: connection from get_connection().
        year, month: the closing period this note belongs to.
        page: which screen the note was written on, e.g.
              "management_performance" or "variance_analysis".
        group_name: which row/group the note is about (e.g. an LVL_2 name).
        reason: the free-text note itself.
    """
    with conn.session as session:
        session.execute(
            text("""
                INSERT INTO variance_reasons (year, month, page, group_name, reason, updated_at)
                VALUES (:year, :month, :page, :group_name, :reason, now())
                ON CONFLICT (year, month, page, group_name)
                DO UPDATE SET reason = EXCLUDED.reason, updated_at = now()
            """),
            {"year": year, "month": month, "page": page, "group_name": group_name, "reason": reason},
        )
        session.commit()


def load_variance_reasons(conn, year: int, month: int, page: str) -> dict[str, str]:
    """
    Load all saved variance reasons for one page/year/month.

    Returns:
        dict of group_name -> reason text.
    """
    df = conn.query(
        "SELECT group_name, reason FROM variance_reasons WHERE year = :year AND month = :month AND page = :page",
        params={"year": year, "month": month, "page": page},
        ttl=0,
    )
    return dict(zip(df["group_name"], df["reason"])) if not df.empty else {}
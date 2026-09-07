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
st.caption(f"{settings['phase']}  ·  대상: {settings['scope']}")

st.markdown(
    """
    ### 이 화면은 무엇인가요?

    로컬 **Phase 1 프로토타입**입니다. 아직 기존 엑셀 마감 프로세스를
    대체하지는 않습니다. 계산 로직(P/L, 비용, 변동 분석 등)을 다시 만들기
    전에, **원천 데이터를 Python에서 정확하게 읽고 검증할 수 있는지**를
    먼저 증명하는 단계입니다.
    """
)

st.markdown("### 사용 순서")

with st.container(border=True):
    st.markdown("#### STEP 1. Data Import")
    st.markdown(
        """
        1. 왼쪽 사이드바에서 **Data Import** 페이지를 엽니다.
        2. 경영실적 엑셀 워크북(.xlsx)을 업로드합니다.
        3. 필수 시트 3개(`RAW_SYSTEM(PL)`, `RAW_SYSTEM(EXP)`, `Code Mapping`)가
           모두 있는지 자동으로 확인합니다.
        4. 확인이 끝나면 원본 데이터가 자동으로 불러와집니다.
        """
    )

with st.container(border=True):
    st.markdown("#### STEP 2. Data Quality")
    st.markdown(
        """
        1. 왼쪽 사이드바에서 **Data Quality** 페이지를 엽니다.
        2. 원본 데이터(RAW_SYSTEM PL/EXP)에 대한 자동 검증 결과를 확인합니다
           (빈 값, 중복 키, 잘못된 월 값 등).
        3. Code Mapping 마스터 데이터의 문제도 함께 확인합니다
           (미매핑 CCTR, 중복 매핑, 조직 계층 공백 등).
        """
    )

st.markdown(
    """
    ---
    이번 버전은 로그인, 클라우드 저장, 다중 사용자 기능이 없습니다 —
    한 번에 한 세션씩만 사용되고, 데이터는 세션이 끝나면 사라집니다.
    """
)

if "raw_pl_df" in st.session_state:
    st.success("현재 세션에 업로드된 워크북이 있습니다. **Data Quality** 페이지에서 확인하세요.")
else:
    st.info("아직 업로드된 워크북이 없습니다. **Data Import** 페이지에서 시작하세요.")
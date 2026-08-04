"""
진입점. 오늘 목표는 디자인이 아니라 화면 이동·상태 흐름 확인 (더미 E2E).
Product -> Generate -> Loading -> Result 까지 관통. History는 빈 목록까지만.
"""
import streamlit as st

st.set_page_config(page_title="소형가전 광고 생성기", layout="wide")

DEFAULT_STATE = {
    "product": None,
    "product_id": None,
    "product_image_url": None,
    "product_name": "",
    "price": "",
    "selling_points": "",
    "selected_tones": ["emotional", "modern", "practical", "premium"],  # M2: 항상 4종
    "time_slots": [],  # PM 승인: 체크박스 다중 선택 (최대 3개)
    "job_id": None,
    "job_status": "idle",
    "results": [],
}
for key, default in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.title("소형가전 광고 생성기")
st.caption("왼쪽 사이드바에서 Product → Generate → History 순서로 진행하세요.")
st.info("이 진입 화면은 상태 초기화용입니다. 왼쪽 메뉴에서 **1 Product**부터 시작하세요.")

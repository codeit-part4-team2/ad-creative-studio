import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.title("3 · 생성 이력")

try:
    history = requests.get(f"{API_BASE}/api/v1/history", timeout=10).json()
except requests.exceptions.ConnectionError:
    st.error(f"백엔드({API_BASE})에 연결할 수 없습니다.")
    st.stop()

if not history:
    st.info("아직 생성한 광고가 없습니다. **1 Product**에서 시작해보세요.")
else:
    for item in reversed(history):
        with st.expander(f"{item['job_id']} · {len(item['results'])}개 결과"):
            st.write(item)

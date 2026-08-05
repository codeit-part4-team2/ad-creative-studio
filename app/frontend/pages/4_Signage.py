"""
시간대별 제품 노출 페이지 (강사님 피드백 반영, S1).
지금 이 순간 어떤 시간대인지 자동 판정해서, 그 시간대용으로 생성된 광고를 "지금 노출 중"으로 보여준다.
실제 사이니지처럼 동작 — 시간이 바뀌면 노출되는 배너도 자동으로 바뀐다.
"""
import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.title("4 · 시간대별 제품 노출")
st.caption("지금 시각 기준으로 자동 판정된 시간대의 광고를 보여줍니다 (실제 사이니지 동작 시뮬레이션).")

if not st.session_state.get("product_id"):
    st.warning("먼저 **1 Product**에서 상품을 등록하고, **2 Generate**에서 광고를 생성해주세요.")
    st.stop()

if st.button("🔄 새로고침"):
    st.rerun()

try:
    resp = requests.get(f"{API_BASE}/api/v1/exposure/{st.session_state.product_id}", timeout=10)
    resp.raise_for_status()
    exposure = resp.json()
except requests.exceptions.ConnectionError:
    st.error(f"백엔드({API_BASE})에 연결할 수 없습니다.")
    st.stop()
except requests.exceptions.HTTPError as e:
    st.error(f"조회 실패: {e.response.text}")
    st.stop()

st.subheader(f"⏰ 현재 시간대: {exposure['time_slot_label']}")

if not exposure["available"]:
    st.warning(
        f"'{exposure['time_slot_label']}' 시간대로 생성된 광고가 아직 없습니다. "
        f"**2 Generate**에서 이 시간대를 선택해 먼저 생성해주세요."
    )
else:
    st.success("지금 이 광고가 노출되고 있습니다 👇")
    tone_label_map = {"emotional": "감성", "modern": "모던", "practical": "실용", "premium": "프리미엄"}
    cols = st.columns(len(exposure["tones"]))
    for col, tone_result in zip(cols, exposure["tones"]):
        with col:
            st.markdown(f"**{tone_label_map.get(tone_result['tone'], tone_result['tone'])}**")
            first_image = next(iter(tone_result["images"].values()), None)
            if first_image:
                st.image(first_image, width=200)  # TODO: 실제 생성 이미지로 교체 (지금은 mock URL)
            st.info(f"{tone_result['headline']}\n\n{tone_result['subcopy']}")

st.divider()
st.caption(
    "실제 서비스에서는 이 화면이 매장 사이니지나 스토어 배너에 그대로 연결되어, "
    "시간이 바뀌면 자동으로 노출 콘텐츠가 전환됩니다."
)

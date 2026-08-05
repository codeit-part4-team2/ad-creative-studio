"""
기본 페이지 (강사님 피드백 반영) — 소형가전 재판매 소상공인이 이 서비스를 처음 만나는 진입 화면.
"이게 뭐고, 왜 써야 하는지"를 바로 보여주고, 시작 버튼으로 Wizard(Product)로 안내한다.
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

st.title("🔌 소형가전 AI 광고 생성기")
st.caption("쿠팡·알리·테무에서 사입한 소형가전, 제조사 사진 그대로 쓰지 마세요.")

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("제품 사진 한 장이면 충분합니다")
    st.markdown(
        """
- ✅ **제품은 그대로 보존**하면서 배경·조명·분위기만 새로 생성
- ✅ **톤 4종**(감성/모던/실용/프리미엄)을 한 번에 만들어서 고르기만 하면 됨
- ✅ **시간대별**(아침/출근/오후/퇴근/저녁/심야) 노출에 맞춘 광고 자동 전환
- ✅ 썸네일·상세페이지 배너·SNS 카드까지 한 번에 출력

프롬프트를 쓸 줄 몰라도 됩니다 — 사진 올리고, 몇 가지만 골라주세요.
        """
    )
    if st.button("지금 시작하기 →", type="primary"):
        st.switch_page("pages/1_Product.py")

with col2:
    st.info(
        "**이런 분들께 추천합니다**\n\n"
        "- 이커머스에서 소형가전을 재판매하시는 분\n"
        "- 제조사 사진과 똑같아서 경쟁이 힘든 분\n"
        "- 촬영 스튜디오 없이 광고 이미지를 만들고 싶은 분"
    )

st.divider()
st.caption("왼쪽 메뉴에서 Product → Generate → History 순서로도 바로 이동할 수 있습니다.")

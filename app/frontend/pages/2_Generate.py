import time
import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.title("2 · 광고 생성")

if not st.session_state.get("product_id"):
    st.warning("먼저 **1 Product**에서 상품을 등록하세요.")
    st.stop()

st.write(f"상품: **{st.session_state.product_name}**")

TIME_SLOT_OPTIONS = [
    ("morning", "☀ 아침", "여유·준비"),
    ("commute_am", "🚇 출근 러시아워", "즉시결정·짧은 관여"),
    ("afternoon", "🏢 오후", "비교·정보탐색"),
    ("commute_pm", "🚇 퇴근 러시아워", "즉시결정·보상심리"),
    ("evening", "🌇 저녁", "여유·라이프스타일"),
    ("late_night", "🌙 심야", "긴급성·한정 (프로모션 정보 입력 시에만 구체적 문구)"),
]
MAX_SLOTS = 3

st.subheader("노출 시간대 선택 (여러 개 선택 가능, 최대 3개)")
st.caption("출퇴근 러시아워와 퇴근 후는 소형가전 구매 심리가 달라서 세분화했습니다.")

selected = []
cols = st.columns(3)
for i, (key, label, desc) in enumerate(TIME_SLOT_OPTIONS):
    with cols[i % 3]:
        if st.checkbox(label, key=f"ts_{key}", help=desc):
            selected.append(key)

if len(selected) > MAX_SLOTS:
    st.warning(f"최대 {MAX_SLOTS}개까지만 선택할 수 있어요 (GPU 대기열 보호).")
elif selected:
    est = len(selected) * 4 * 15  # 톤4종 x 시간대 x 15초 가정
    st.info(f"예상 생성 시간: 약 {est}초 (~{est // 60}분) · 톤 4종 × 선택 시간대 {len(selected)}개")

show_promo = "late_night" in selected
promotion = None
if show_promo:
    with st.expander("심야 시간대 프로모션 정보 (선택 — 없으면 일반 문구로 생성됩니다)"):
        discount = st.number_input("할인율 (%)", min_value=0, max_value=90, value=0)
        ends_at = st.text_input("종료 시각 (예: 24:00)", value="")
        if discount or ends_at:
            promotion = {"discount_percent": discount or None, "ends_at": ends_at or None}

can_generate = bool(selected) and len(selected) <= MAX_SLOTS

if st.button("광고 만들기", type="primary", disabled=not can_generate):
    try:
        resp = requests.post(f"{API_BASE}/api/v1/generations", json={
            "product_id": st.session_state.product_id,
            "time_slots": selected,
        }, timeout=10)
        resp.raise_for_status()
        job_id = resp.json()["job_id"]
        st.session_state.job_id = job_id
        st.session_state.job_status = "processing"
    except requests.exceptions.ConnectionError:
        st.error(f"백엔드({API_BASE})에 연결할 수 없습니다.")
        st.stop()
    except requests.exceptions.HTTPError as e:
        st.error(f"생성 요청 실패: {e.response.text}")
        st.stop()

    with st.status("광고를 만들고 있어요...", expanded=True) as status:
        placeholder = st.empty()
        for _ in range(60):  # 최대 ~30초 폴링 (데모용 mock worker는 매우 빠름)
            job = requests.get(f"{API_BASE}/api/v1/jobs/{job_id}", timeout=10).json()
            placeholder.write(
                f"{job['status']} · {job['completed_count']}/{job['total_count']} "
                f"· {job.get('current_step') or ''}"
            )
            if job["status"] == "completed":
                status.update(label="완료!", state="complete")
                break
            time.sleep(0.5)
        else:
            status.update(label="시간 초과 - 다시 시도해주세요", state="error")
            st.stop()

    result = requests.get(f"{API_BASE}/api/v1/generations/{job_id}", timeout=10).json()
    st.session_state.results = result["results"]

if st.session_state.get("results"):
    st.divider()
    st.subheader("결과")
    tone_label_map = {"emotional": "감성", "modern": "모던", "practical": "실용", "premium": "프리미엄"}
    for r in st.session_state.results:
        st.markdown(f"**{tone_label_map.get(r['tone'], r['tone'])} · {r.get('time_slot', '')}**")
        cols = st.columns(len(r["images"]) or 1)
        for col, (fmt, url) in zip(cols, r["images"].items()):
            with col:
                st.caption(fmt)
                st.image(url, width=150)  # TODO: 실제 생성 이미지로 교체 (지금은 mock URL)
        st.info(f"{r['headline']}\n\n{r['subcopy']}")
        st.divider()

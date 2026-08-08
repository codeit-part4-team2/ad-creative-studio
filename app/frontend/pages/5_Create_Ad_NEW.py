"""
신규 통합 Wizard — 기존 1_Product.py / 2_Generate.py를 대체하기 위한 병렬 구현.
백엔드 API·로직은 전혀 안 건드리고, 기존 두 페이지에서 쓰던 API 호출을 그대로 재사용해서
한 화면 안에서 단계가 순차적으로 열리는 흐름으로만 재배치한다.
검증 끝나면(기존 페이지와 동작 비교 + pytest 통과) 1_Product.py/2_Generate.py를 없앤다.
"""
import time
import requests
import streamlit as st

API_BASE = "http://localhost:8000"

TIME_SLOT_OPTIONS = [
    ("morning", "☀ 아침", "여유·준비"),
    ("commute_am", "🚇 출근 러시아워", "즉시결정·짧은 관여"),
    ("afternoon", "🏢 오후", "비교·정보탐색"),
    ("commute_pm", "🚇 퇴근 러시아워", "즉시결정·보상심리"),
    ("evening", "🌇 저녁", "여유·라이프스타일"),
    ("late_night", "🌙 심야", "긴급성·한정 (프로모션 정보 입력 시에만 구체적 문구)"),
]
MAX_SLOTS = 3
TONE_LABEL_MAP = {"emotional": "감성", "modern": "모던", "practical": "실용", "premium": "프리미엄"}

st.title("광고 만들기")

if "wizard_step" not in st.session_state:
    st.session_state.wizard_step = 1


def render_product_step():
    st.subheader("① 상품 정보")

    if st.session_state.wizard_step > 1 and st.session_state.get("product_id"):
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"✓ **{st.session_state.product_name}** · {int(st.session_state.price):,}원")
                if st.session_state.get("selling_points"):
                    st.caption(st.session_state.selling_points)
            with col2:
                if st.button("수정", key="edit_product_step"):
                    st.session_state.wizard_step = 1
                    st.rerun()
        return

    uploaded = st.file_uploader("제품 사진을 끌어다 놓으세요", type=["jpg", "jpeg", "png"])
    product_name = st.text_input("제품명 *", value=st.session_state.get("product_name", ""),
                                  placeholder="스팀 에어프라이어 5L")
    price = st.number_input("가격 *", min_value=0, step=1000,
                             value=int(st.session_state.get("price") or 0))
    selling_points = st.text_input("셀링포인트 (쉼표로 구분, 선택)",
                                    value=st.session_state.get("selling_points", ""),
                                    placeholder="기름 없이 조리, 1인 가구 추천")

    if uploaded:
        st.image(uploaded, caption="업로드한 사진 미리보기", width=200)

    # 시간대 선택 단계와 마찬가지로 명시적 버튼으로 확정한다 - 이미지+제품명만으로
    # 자동 전환하면 가격·셀링포인트를 채울 틈 없이 곧장 넘어가버려서 UX상 별로였다.
    # 가격은 필수(0원 상품은 실제로 없음), 셀링포인트는 선택(Prompt Builder가 없어도 동작).
    ready = bool(uploaded and product_name.strip() and price > 0)
    if st.button("다음: 광고 설정", type="primary", disabled=not ready, key="confirm_product"):
        with st.spinner("상품 등록 중..."):
            try:
                files = {"image": (uploaded.name, uploaded.getvalue(), uploaded.type)}
                data = {"product_name": product_name, "price": price, "selling_points": selling_points}
                resp = requests.post(f"{API_BASE}/api/v1/products", files=files, data=data, timeout=10)
                resp.raise_for_status()
                body = resp.json()

                st.session_state.product_id = body["product_id"]
                st.session_state.product_image_url = body["image_url"]
                st.session_state.product_name = product_name
                st.session_state.price = price
                st.session_state.selling_points = selling_points

                # [수정] 버튼 흐름은 항상 "재등록"이라 매번 새 product_id가 발급된다 -
                # 이 버튼을 누른 시점엔 사실상 항상 상품이 (재)등록된 것이므로 무조건 초기화한다.
                st.session_state.time_slots = []
                st.session_state.job_id = None
                st.session_state.results = []

                st.session_state.wizard_step = 2
                st.rerun()
            except requests.exceptions.ConnectionError:
                st.error(f"백엔드({API_BASE})에 연결할 수 없습니다. `uvicorn app.backend.main:app --reload` 를 먼저 실행하세요.")
            except requests.exceptions.HTTPError as e:
                st.error(f"업로드 실패: {e.response.text}")


def render_ad_settings_step():
    if st.session_state.wizard_step < 2:
        return
    st.subheader("② 광고 설정")

    if st.session_state.wizard_step > 2 and st.session_state.get("time_slots"):
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                labels = [label for key, label, _ in TIME_SLOT_OPTIONS if key in st.session_state.time_slots]
                st.markdown("✓ **시간대**: " + ", ".join(labels) + " (톤 4종 자동 생성)")
            with col2:
                if st.button("수정", key="edit_settings_step"):
                    st.session_state.wizard_step = 2
                    st.rerun()
        return

    st.caption(f"노출 시간대를 선택하세요 (최대 {MAX_SLOTS}개). 톤 4종(감성/모던/실용/프리미엄)은 자동으로 함께 생성됩니다.")

    selected = []
    cols = st.columns(3)
    for i, (key, label, desc) in enumerate(TIME_SLOT_OPTIONS):
        with cols[i % 3]:
            default = key in st.session_state.get("time_slots", [])
            if st.checkbox(label, value=default, key=f"wiz_ts_{key}", help=desc):
                selected.append(key)

    if len(selected) > MAX_SLOTS:
        st.warning(f"최대 {MAX_SLOTS}개까지만 선택할 수 있어요 (GPU 대기열 보호).")

    promotion = None
    if "late_night" in selected:
        with st.expander("심야 시간대 프로모션 정보 (선택 — 없으면 일반 문구로 생성됩니다)"):
            discount = st.number_input("할인율 (%)", min_value=0, max_value=90, value=0, key="wiz_discount")
            ends_at = st.text_input("종료 시각 (예: 24:00)", value="", key="wiz_ends_at")
            if discount or ends_at:
                promotion = {"discount_percent": discount or None, "ends_at": ends_at or None}

    can_continue = bool(selected) and len(selected) <= MAX_SLOTS
    if st.button("다음: 검토 및 생성", type="primary", disabled=not can_continue, key="confirm_settings"):
        st.session_state.time_slots = selected
        st.session_state.promotion = promotion
        st.session_state.wizard_step = 3
        st.rerun()


def render_review_and_generate_step():
    if st.session_state.wizard_step < 3:
        return
    st.subheader("③ 검토 및 생성")

    slots = st.session_state.get("time_slots", [])
    labels = [label for key, label, _ in TIME_SLOT_OPTIONS if key in slots]
    est_seconds = len(slots) * 4 * 15

    st.write(f"**상품**: {st.session_state.product_name}")
    st.write(f"**시간대**: {', '.join(labels)}")
    st.write(f"**생성 개수**: 톤 4종 × 시간대 {len(slots)}개 = {len(slots) * 4}개 (규격 3종씩)")
    st.caption(f"예상 소요 시간: 약 {est_seconds}초")

    if st.session_state.wizard_step != 3:
        return

    if st.button("🎨 광고 생성", type="primary", key="generate_btn"):
        try:
            resp = requests.post(f"{API_BASE}/api/v1/generations", json={
                "product_id": st.session_state.product_id,
                "time_slots": slots,
            }, timeout=10)
            resp.raise_for_status()
            st.session_state.job_id = resp.json()["job_id"]
            # 이전 생성 결과가 session_state에 남아있으면 render_result_step이
            # "이미 결과 있음"으로 착각해서 새 job_id를 폴링하지 않고 옛 결과를
            # 그대로 보여준다 (설정 [수정] 후 재생성했을 때 실제로 재현됨) - 명시적으로 비운다.
            st.session_state.results = []
            st.session_state.wizard_step = 4
            st.rerun()
        except requests.exceptions.ConnectionError:
            st.error(f"백엔드({API_BASE})에 연결할 수 없습니다.")
        except requests.exceptions.HTTPError as e:
            st.error(f"생성 요청 실패: {e.response.text}")


def render_result_step():
    if st.session_state.wizard_step < 4:
        return
    st.subheader("④ 결과")

    job_id = st.session_state.job_id

    if not st.session_state.get("results"):
        with st.status("광고를 만들고 있어요...", expanded=True) as status:
            placeholder = st.empty()
            for _ in range(60):
                job = requests.get(f"{API_BASE}/api/v1/jobs/{job_id}", timeout=10).json()
                placeholder.write(
                    f"{job['status']} · {job['completed_count']}/{job['total_count']} "
                    f"· {job.get('current_step') or ''}"
                )
                if job["status"] == "completed":
                    status.update(label="완료!", state="complete")
                    break
                if job["status"] == "failed":
                    status.update(label=f"실패: {job.get('error_message')}", state="error")
                    st.stop()
                time.sleep(0.5)
            else:
                status.update(label="시간 초과 - 다시 시도해주세요", state="error")
                st.stop()

        result = requests.get(f"{API_BASE}/api/v1/generations/{job_id}", timeout=10).json()
        st.session_state.results = result["results"]

    for r in st.session_state.results:
        st.markdown(f"**{TONE_LABEL_MAP.get(r['tone'], r['tone'])} · {r.get('time_slot', '')}**")
        cols = st.columns(len(r["images"]) or 1)
        for col, (fmt, url) in zip(cols, r["images"].items()):
            with col:
                st.caption(fmt)
                st.image(f"{API_BASE}{url}" if url.startswith("/") else url, width=150)
        st.info(f"{r['headline']}\n\n{r['subcopy']}")
        st.divider()

    st.caption("규격별/전체 다운로드, 즐겨찾기, 러시아워 쇼츠 생성은 **History** 메뉴에서 계속 이용할 수 있습니다.")

    if st.button("🔄 새 광고 만들기"):
        for key in ("wizard_step", "product_id", "product_image_url", "product_name", "price",
                    "selling_points", "time_slots", "promotion", "job_id", "results"):
            st.session_state.pop(key, None)
        st.rerun()


render_product_step()
render_ad_settings_step()
render_review_and_generate_step()
render_result_step()

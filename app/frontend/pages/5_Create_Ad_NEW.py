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

# 로딩 화면 단계 - (경과초, 라벨, 보조문구 또는 None). 실제 백엔드가 세부 stage를 아직
# 안 돌려줘서(job["current_step"]은 "시간대/톤 생성 중" 정도만 줌) 지금은 경과시간 기준으로
# 단계 메시지만 고른다 - 완료/실패 여부는 반드시 backend job status로 판정한다(아래 참고).
# 임계값은 순수 모델 추론시간(L4 실측 fast_composite B: P50 2.37s)이 아니라 Streamlit→
# Backend→모델서버→Overlay→History까지 합친 E2E 체감시간 기준이어야 하므로, 최종 baseline
# 확정 후 실제 E2E latency가 나오면 그때 다시 조정한다. 가짜 퍼센트(83% 같은)는 신뢰를
# 떨어뜨리니 안 쓴다 - "지금 이 단계를 하고 있다"는 정성적 신호만 준다.
# 보조문구는 라벨 문자열 비교가 아니라 여기 튜플에 직접 묶어둔다 - 나중에 라벨 문구를
# 고치면서 보조문구가 조용히 사라지는 걸 방지.
LOADING_STAGES = [
    (0, "상품 정보를 확인했어요", None),
    (2, "시간대에 맞는 광고 콘셉트를 구성했어요", None),
    (5, "제품이 돋보이는 배경을 만들고 있어요", "좋은 상태로 제품을 포장하고 있습니다 :)"),
    (12, "광고 문구를 자연스럽게 조합하고 있어요", None),
    (15, "거의 다 됐어요 - 최종 결과를 정리하고 있어요", None),
]
MAX_POLL_SECONDS = 45  # fast_composite로 바뀌면 낮춰도 됨, 지금은 17초 P95 기준 여유 있게


def _render_loading_experience(job_id: str):
    """
    단순 스피너 대신, 실제 파이프라인 단계에 맞춘 체크리스트형 로딩 화면.
    완료/실패 판정은 반드시 백엔드 job 상태(진짜 사실)로 하고, 화면에 보이는 단계
    메시지만 경과시간으로 고른다 - 그래서 fast_composite로 훨씬 빨리 끝나도
    (예: 6초) 문제없이 바로 "완료"로 넘어간다(중간 단계를 억지로 다 보여주지 않음).
    """
    start = time.time()
    with st.status("광고를 만들고 있어요 ✨", expanded=True) as status:
        placeholder = st.empty()
        for _ in range(int(MAX_POLL_SECONDS / 0.5)):
            try:
                job = requests.get(f"{API_BASE}/api/v1/jobs/{job_id}", timeout=10).json()
            except requests.exceptions.RequestException as e:
                status.update(label=f"백엔드 연결이 끊겼어요: {e}", state="error")
                st.stop()

            if job["status"] == "completed":
                status.update(label="광고가 완성됐어요 🎉", state="complete")
                return
            if job["status"] == "failed":
                status.update(label=f"생성 실패: {job.get('error_message', '알 수 없는 오류')}", state="error")
                st.stop()

            elapsed = time.time() - start
            # 마지막 임계값을 넘긴 뒤에도(quality_regenerate처럼 오래 걸리는 경우) 마지막
            # 단계가 계속 "진행 중(🎨)"으로 남아있게 한다 - 전부 ✅인데 아무 표시도 없이
            # 멈춰있는 것처럼 보이는 걸 방지.
            current_idx = 0
            for i, (threshold, _, _) in enumerate(LOADING_STAGES):
                if elapsed >= threshold:
                    current_idx = i
            lines = []
            for i, (threshold, label, subtext) in enumerate(LOADING_STAGES):
                if i < current_idx:
                    lines.append(f"✅ {label}")
                elif i == current_idx:
                    lines.append(f"🎨 {label}")
                    if subtext:
                        lines.append(f"　　{subtext}")
                else:
                    lines.append(f"⬜ {label}")
            # 실제 진행 개수(백엔드가 주는 사실)도 정성적 단계 표시와 같이 보여준다 -
            # 응답에 없을 수도 있으니 방어적으로 확인 후에만 표시한다.
            completed = job.get("completed_count")
            total = job.get("total_count")
            if completed is not None and total:
                lines.append(f"\n**현재 {completed} / {total}개 생성 완료**")
            placeholder.markdown("\n\n".join(lines))
            time.sleep(0.5)

        status.update(label="예상보다 오래 걸리고 있어요 - 잠시 후 다시 확인해주세요", state="error")
        st.stop()


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

    st.write(f"**상품**: {st.session_state.product_name}")
    st.write(f"**시간대**: {', '.join(labels)}")
    st.write(
        f"**생성 개수**: 톤 4종 × 시간대 {len(slots)}개 × 기본 규격 2종 "
        f"= {len(slots) * 8}개 이미지"
    )
    # 예상 소요시간은 일부러 안 보여준다 - 모델팀 구조(fast_composite/quality_regenerate/
    # 캐시/배치)가 계속 바뀌는 중이라 지금 숫자를 계산해서 보여주면 오히려 신뢰를 깎는다.
    # 실제 E2E 실측 끝나면 그때 진짜 근거 있는 숫자로 넣는다.
    st.caption("선택한 시간대와 생성 옵션에 따라 잠시 시간이 걸릴 수 있어요.")

    if st.session_state.wizard_step == 3:  # 4단계(생성 요청 완료 후)로 넘어가면 버튼 다시 안 보여줌
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
        _render_loading_experience(job_id)

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

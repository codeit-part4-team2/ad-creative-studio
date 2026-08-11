from datetime import datetime

import requests
import streamlit as st

from app.frontend.video_view_state import (
    KST,
    RUSH_HOUR_SLOTS,
    VideoViewKind,
    build_video_view_state,
    can_create_rush_hour_short,
    default_activation_at,
)

API_BASE = "http://localhost:8000"


def api_url(path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    return f"{API_BASE}{path}"


def _youtube_status() -> dict:
    try:
        response = requests.get(api_url("/api/v1/youtube/status"), timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return {
            "configured": False,
            "connection_id": "unavailable",
            "token_available": False,
        }


def _create_video(result_id: str) -> str | None:
    try:
        response = requests.post(
            api_url("/api/v1/videos"),
            json={"result_id": result_id},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["video_job_id"]
    except requests.exceptions.RequestException as exc:
        st.error(f"쇼츠 생성 요청 실패: {exc}")
        return None


def render_video_workflow(result: dict) -> None:
    if not can_create_rush_hour_short(result):
        return

    result_id = result.get("result_id")
    if not result_id:
        st.error("영상 생성을 위한 result_id가 없습니다.")
        return

    st.markdown("#### 러시아워 무표정 AI 코믹 쇼츠")
    session_key = f"video_job_{result_id}"
    video_job_id = result.get("video_job_id") or st.session_state.get(session_key)
    if not video_job_id:
        if st.button("🎬 코믹 쇼츠 만들기", key=f"shorts_{result_id}"):
            created_id = _create_video(result_id)
            if created_id:
                st.session_state[session_key] = created_id
                st.rerun()
        return

    st.session_state[session_key] = video_job_id
    try:
        response = requests.get(
            api_url(f"/api/v1/videos/{video_job_id}"),
            timeout=10,
        )
        response.raise_for_status()
        job = response.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"쇼츠 상태 조회 실패: {exc}")
        return

    render_status = job["render_status"]
    view_state = build_video_view_state(job)
    if view_state.kind is VideoViewKind.CREATING:
        st.info(f"쇼츠 생성 중입니다. 현재 상태: {render_status}")
        if st.button("상태 새로고침", key=f"refresh_{result_id}"):
            st.rerun()
        return
    if view_state.kind is VideoViewKind.FAILED:
        st.error(job.get("error_message") or "쇼츠 생성에 실패했습니다.")
        if st.button("쇼츠 다시 만들기", key=f"retry_{result_id}"):
            created_id = _create_video(result_id)
            if created_id:
                st.session_state[session_key] = created_id
                st.rerun()
        return

    video_url = job.get("video_url")
    if view_state.show_video and video_url:
        st.video(api_url(video_url))

    script_lines = job.get("script_lines") or []
    if script_lines:
        with st.expander("쇼츠 대본 확인", expanded=True):
            for index, line in enumerate(script_lines, start=1):
                st.markdown(f"{index}. {line}")
            st.caption(
                f"음성: {job.get('tts_engine') or '확인 중'} · "
                f"프리셋: {job.get('tts_voice_preset') or '확인 중'}"
            )

    if view_state.kind is VideoViewKind.PRONUNCIATION_REVIEW:
        st.error(
            "상품명 또는 영문·숫자 발음 표기가 확인되지 않았습니다. "
            "상품의 한글 발음 표기를 보완한 뒤 쇼츠를 다시 생성해주세요."
        )
    if view_state.kind in {VideoViewKind.APPROVED, VideoViewKind.PUBLISHING, VideoViewKind.PUBLISH_WARNING}:
        st.success(f"내부 노출 승인 완료 · 활성 시각: {job.get('activation_at')}")
        publish_status = job["publish_status"]
        if publish_status == "scheduled":
            st.success(f"YouTube 예약 완료 · 영상 ID: {job.get('youtube_video_id')}")
        elif publish_status == "pending":
            st.info("YouTube 예약 업로드를 처리 중입니다.")
        elif publish_status != "not_requested":
            st.warning(
                "내부 노출 승인은 유지됩니다. "
                f"YouTube 상태: {publish_status} · {job.get('youtube_error') or ''}"
            )
        return
    if view_state.kind is VideoViewKind.REJECTED:
        st.warning("이 쇼츠는 운영자 검수에서 거절되었습니다.")
        return

    default_at = default_activation_at(job["time_slot"], datetime.now(KST))
    activation_date = st.date_input(
        "내부 노출 시작일",
        value=default_at.date(),
        key=f"activation_date_{result_id}",
    )
    activation_time = st.time_input(
        "내부 노출 시작 시각 (KST)",
        value=default_at.time().replace(tzinfo=None),
        key=f"activation_time_{result_id}",
    )
    activation_at = datetime.combine(activation_date, activation_time, tzinfo=KST)

    youtube = _youtube_status()
    if youtube.get("configured"):
        st.caption(f"연결된 YouTube 채널: {youtube['connection_id']}")
        publish_to_youtube = st.checkbox(
            "같은 시각에 YouTube Shorts 예약 게시",
            key=f"publish_to_youtube_{result_id}",
        )
    else:
        st.caption("YouTube 연결 전: 내부 러시아워 노출만 승인할 수 있습니다.")
        publish_to_youtube = False

    st.info(
        "승인 전에는 게시되지 않습니다. 음성 발음·자막·제품 보존을 직접 확인한 뒤 "
        "내부 노출과 YouTube 게시를 승인해주세요."
    )
    approve_col, reject_col = st.columns(2)
    with approve_col:
        if view_state.can_approve and st.button("검수 승인", key=f"approve_{result_id}"):
            try:
                approval = requests.post(
                    api_url(f"/api/v1/videos/{video_job_id}/approve"),
                    json={
                        "activation_at": activation_at.isoformat(),
                        "publish_to_youtube": publish_to_youtube,
                    },
                    timeout=10,
                )
                approval.raise_for_status()
                st.rerun()
            except requests.exceptions.RequestException as exc:
                st.error(f"쇼츠 승인 실패: {exc}")

    with reject_col:
        reject_confirmed = st.checkbox(
            "거절 확인",
            key=f"reject_confirmed_{result_id}",
        )
        if st.button(
            "검수 거절",
            key=f"reject_{result_id}",
            disabled=not reject_confirmed or not view_state.can_reject,
        ):
            try:
                rejection = requests.post(
                    api_url(f"/api/v1/videos/{video_job_id}/reject"),
                    timeout=10,
                )
                rejection.raise_for_status()
                st.rerun()
            except requests.exceptions.RequestException as exc:
                st.error(f"쇼츠 거절 실패: {exc}")


st.title("3 · 생성 이력")
favorite_only = st.checkbox("⭐ 즐겨찾기만 보기")

try:
    response = requests.get(
        api_url("/api/v1/history"),
        params={"favorite_only": favorite_only},
        timeout=10,
    )
    response.raise_for_status()
    history = response.json()
except requests.exceptions.ConnectionError:
    st.error(f"백엔드({API_BASE})에 연결할 수 없습니다.")
    st.stop()
except requests.exceptions.RequestException as exc:
    st.error(f"생성 이력을 불러오지 못했습니다: {exc}")
    st.stop()

if not history:
    message = (
        "즐겨찾기한 광고가 없습니다."
        if favorite_only
        else "아직 생성된 광고가 없습니다. 광고 만들기에서 첫 광고를 만들어보세요."
    )
    st.info(message)
else:
    tone_labels = {
        "emotional": "감성",
        "modern": "모던",
        "practical": "실용",
        "premium": "프리미엄",
    }
    for item in reversed(history):
        star = "⭐" if item.get("favorite") else "☆"
        with st.expander(f"{star} {item['job_id']} · {len(item['results'])}개 결과"):
            favorite_col, download_col = st.columns(2)
            with favorite_col:
                favorite_label = (
                    "즐겨찾기 해제" if item.get("favorite") else "⭐ 즐겨찾기 추가"
                )
                if st.button(favorite_label, key=f"fav_{item['job_id']}"):
                    try:
                        favorite_response = requests.patch(
                            api_url(f"/api/v1/history/{item['job_id']}/favorite"),
                            timeout=10,
                        )
                        favorite_response.raise_for_status()
                        st.rerun()
                    except requests.exceptions.RequestException as exc:
                        st.error(f"즐겨찾기 변경 실패: {exc}")

            with download_col:
                try:
                    zip_response = requests.get(
                        api_url(f"/api/v1/download/{item['job_id']}/all"),
                        timeout=10,
                    )
                    if zip_response.status_code == 200:
                        st.download_button(
                            "⬇ 전체 다운로드 (ZIP)",
                            data=zip_response.content,
                            file_name=f"{item['job_id']}_all.zip",
                            mime="application/zip",
                            key=f"dl_all_{item['job_id']}",
                        )
                    else:
                        st.caption("다운로드 불가 (파일 없음)")
                except requests.exceptions.RequestException:
                    st.caption("다운로드 서버 연결 실패")

            for result in item["results"]:
                st.markdown(
                    f"**{tone_labels.get(result['tone'], result['tone'])} · "
                    f"{result.get('time_slot', '')}**"
                )
                columns = st.columns(len(result["images"]) or 1)
                for column, (image_format, url) in zip(
                    columns,
                    result["images"].items(),
                ):
                    with column:
                        st.caption(image_format)
                        image_url = api_url(url)
                        st.image(image_url, width=150)
                        try:
                            image_response = requests.get(image_url, timeout=10)
                            image_response.raise_for_status()
                            image_bytes = image_response.content
                        except requests.exceptions.RequestException:
                            image_bytes = None
                        if image_bytes is not None:
                            st.download_button(
                                "⬇",
                                data=image_bytes,
                                file_name=(
                                    f"{item['job_id']}_{result.get('time_slot', '')}_"
                                    f"{result['tone']}_{image_format}.png"
                                ),
                                mime="image/png",
                                key=(
                                    f"dl_{item['job_id']}_{result['tone']}_"
                                    f"{result.get('time_slot', '')}_{image_format}"
                                ),
                            )
                        else:
                            st.caption("다운로드 불가")
                st.caption(f"{result['headline']} · {result['subcopy']}")
                render_video_workflow(result)

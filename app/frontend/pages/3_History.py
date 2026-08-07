import requests
import streamlit as st

# 원래는 app.backend.services.video_generation_service의 RUSH_HOUR_SLOTS를 import해서
# 백엔드와 상수를 공유하려 했으나, Streamlit이 페이지를 실행하는 방식/환경에 따라
# `app` 패키지가 sys.path에 안 잡혀서 ModuleNotFoundError로 History 페이지 전체가
# 죽는 문제가 실제로 발생했다 (pytest는 pyproject.toml의 pythonpath 설정 덕에
# 항상 잡히지만, streamlit run으로 띄울 땐 그 설정이 적용 안 됨).
# 프론트↔백엔드 프로세스 경계를 넘는 import는 이런 환경 의존성 위험이 있어서,
# 값을 다시 로컬 상수로 되돌린다 - 실제 판정은 어차피 백엔드가 하므로(400 반환),
# 이 상수는 "버튼을 보여줄지 말지"만 결정하는 UX용이라 중복이어도 위험은 낮다.
RUSH_HOUR_SLOTS = {"commute_am", "commute_pm"}

API_BASE = "http://localhost:8000"

st.title("3 · 생성 이력")

favorite_only = st.checkbox("⭐ 즐겨찾기만 보기")

try:
    resp = requests.get(f"{API_BASE}/api/v1/history",
                         params={"favorite_only": favorite_only}, timeout=10)
    resp.raise_for_status()
    history = resp.json()
except requests.exceptions.ConnectionError:
    st.error(f"백엔드({API_BASE})에 연결할 수 없습니다.")
    st.stop()

if not history:
    msg = "즐겨찾기한 광고가 없습니다." if favorite_only else "아직 생성한 광고가 없습니다. **광고 만들기**에서 첫 광고를 만들어보세요."
    st.info(msg)
else:
    tone_label_map = {"emotional": "감성", "modern": "모던", "practical": "실용", "premium": "프리미엄"}
    for item in reversed(history):
        star = "⭐" if item.get("favorite") else "☆"
        with st.expander(f"{star} {item['job_id']} · {len(item['results'])}개 결과"):
            col_fav, col_dl = st.columns(2)

            with col_fav:
                if st.button(f"{'즐겨찾기 해제' if item.get('favorite') else '⭐ 즐겨찾기 추가'}",
                             key=f"fav_{item['job_id']}"):
                    try:
                        r = requests.patch(f"{API_BASE}/api/v1/history/{item['job_id']}/favorite", timeout=10)
                        r.raise_for_status()
                        st.rerun()
                    except requests.exceptions.RequestException as e:
                        st.error(f"즐겨찾기 변경 실패: {e}")

            with col_dl:
                try:
                    zip_resp = requests.get(f"{API_BASE}/api/v1/download/{item['job_id']}/all", timeout=10)
                    if zip_resp.status_code == 200:
                        st.download_button(
                            "📦 전체 다운로드 (ZIP)",
                            data=zip_resp.content,
                            file_name=f"{item['job_id']}_all.zip",
                            mime="application/zip",
                            key=f"dl_all_{item['job_id']}",
                        )
                    else:
                        st.caption("다운로드 불가 (파일 없음)")
                except requests.exceptions.RequestException:
                    st.caption("다운로드 서버 연결 실패")

            for r in item["results"]:
                st.markdown(f"**{tone_label_map.get(r['tone'], r['tone'])} · {r.get('time_slot', '')}**")
                cols = st.columns(len(r["images"]) or 1)
                for col, (fmt, url) in zip(cols, r["images"].items()):
                    with col:
                        st.caption(fmt)
                        image_url = f"{API_BASE}{url}" if url.startswith("/") else url
                        st.image(image_url, width=150)
                        # 개별 이미지 다운로드 (톤×시간대×규격 단위)
                        try:
                            img_bytes = requests.get(image_url, timeout=10).content
                        except requests.exceptions.RequestException:
                            img_bytes = None
                        if img_bytes is not None:
                            st.download_button(
                                "⬇",
                                data=img_bytes,
                                file_name=f"{item['job_id']}_{r.get('time_slot', '')}_{r['tone']}_{fmt}.png",
                                mime="image/png",
                                key=f"dl_{item['job_id']}_{r['tone']}_{r.get('time_slot','')}_{fmt}",
                            )
                        else:
                            st.caption("다운로드 불가")
                st.caption(f"{r['headline']} · {r['subcopy']}")

                # 러시아워(출근/퇴근) 결과만 쇼츠 생성 가능
                if r.get("time_slot") in RUSH_HOUR_SLOTS:
                    result_id = r.get("result_id")
                    video_key = f"video_job_{result_id}"

                    if r.get("video_url"):
                        st.video(f"{API_BASE}{r['video_url']}")
                    elif st.session_state.get(video_key):
                        # 요청은 이미 보냈고 조회 중
                        try:
                            status_resp = requests.get(
                                f"{API_BASE}/api/v1/videos/{st.session_state[video_key]}", timeout=10)
                            status = status_resp.json()
                            if status["status"] == "completed":
                                st.rerun()  # History 다시 불러와서 video_url 반영된 걸 보여줌
                            elif status["status"] == "failed":
                                st.error(f"쇼츠 생성 실패: {status.get('error_message')}")
                                del st.session_state[video_key]
                            else:
                                st.info(f"쇼츠 생성 중... ({status['status']})")
                        except requests.exceptions.RequestException as e:
                            st.error(f"쇼츠 상태 조회 실패: {e}")
                    else:
                        if st.button("🎬 러시아워 쇼츠 만들기", key=f"shorts_{result_id}"):
                            try:
                                create_resp = requests.post(
                                    f"{API_BASE}/api/v1/videos",
                                    json={"result_id": result_id},
                                    timeout=10,
                                )
                                create_resp.raise_for_status()
                                st.session_state[video_key] = create_resp.json()["video_job_id"]
                                st.rerun()
                            except requests.exceptions.RequestException as e:
                                st.error(f"쇼츠 생성 요청 실패: {e}")

import requests
import streamlit as st

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
    msg = "즐겨찾기한 광고가 없습니다." if favorite_only else "아직 생성한 광고가 없습니다. **1 Product**에서 시작해보세요."
    st.info(msg)
else:
    tone_label_map = {"emotional": "감성", "modern": "모던", "practical": "실용", "premium": "프리미엄"}
    for item in reversed(history):
        star = "⭐" if item.get("favorite") else "☆"
        with st.expander(f"{star} {item['job_id']} · {len(item['results'])}개 결과"):
            if st.button(f"{'즐겨찾기 해제' if item.get('favorite') else '⭐ 즐겨찾기 추가'}",
                         key=f"fav_{item['job_id']}"):
                requests.patch(f"{API_BASE}/api/v1/history/{item['job_id']}/favorite", timeout=10)
                st.rerun()

            for r in item["results"]:
                st.markdown(f"**{tone_label_map.get(r['tone'], r['tone'])} · {r.get('time_slot', '')}**")
                cols = st.columns(len(r["images"]) or 1)
                for col, (fmt, url) in zip(cols, r["images"].items()):
                    with col:
                        st.caption(fmt)
                        st.image(f"{API_BASE}{url}" if url.startswith("/") else url, width=150)
                st.caption(f"{r['headline']} · {r['subcopy']}")

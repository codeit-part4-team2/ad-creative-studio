import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.title("1 · 상품 등록")

uploaded = st.file_uploader("제품 사진을 끌어다 놓으세요", type=["jpg", "jpeg", "png"])
product_name = st.text_input("제품명", value=st.session_state.get("product_name", ""),
                              placeholder="스팀 에어프라이어 5L")
price = st.number_input("가격", min_value=0, step=1000,
                         value=int(st.session_state.get("price") or 0))
selling_points = st.text_input("셀링포인트 (쉼표로 구분, 선택)",
                                value=st.session_state.get("selling_points", ""),
                                placeholder="기름 없이 조리, 1인 가구 추천")

if uploaded:
    st.image(uploaded, caption="업로드한 사진", width=240)

if st.button("다음: 광고 생성으로", type="primary", disabled=not (uploaded and product_name)):
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
        st.success(f"등록 완료 (product_id: {body['product_id']}). 왼쪽 메뉴에서 **2 Generate**로 이동하세요.")
    except requests.exceptions.ConnectionError:
        st.error(f"백엔드({API_BASE})에 연결할 수 없습니다. `uvicorn app.backend.main:app --reload` 를 먼저 실행하세요.")
    except requests.exceptions.HTTPError as e:
        st.error(f"업로드 실패: {e.response.text}")

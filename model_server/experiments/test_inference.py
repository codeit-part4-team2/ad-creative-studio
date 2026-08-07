import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inference import load_pipeline, generate_image
from PIL import Image

# 이 스크립트 파일이 있는 폴더 경로 (실행 위치와 무관하게 고정됨)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 1회 로딩
pipe = load_pipeline()

# 상품 이미지 준비
product_image = Image.open(os.path.join(SCRIPT_DIR,"product_sample.jpeg")).convert("RGB")

# 비교 실험: 영어 vs 한글 (prompt + negative_prompt 세트로 언어 통일)
test_cases = {
    "en": {
        "prompt": "a small home appliance product photo, studio lighting, white background",
        "negative_prompt": "blurry, low quality, distorted",
    },
    "ko": {
        "prompt": "작은 가전제품 제품 사진, 스튜디오 조명, 흰색 배경",
        "negative_prompt": "흐릿함, 저품질, 왜곡됨",
    },
}

for lang, case in test_cases.items():
    result = generate_image(
        pipe=pipe,
        product_image=product_image,
        prompt=case["prompt"],
        negative_prompt=case["negative_prompt"],
        seed=42,
    )
    output_path = os.path.join(SCRIPT_DIR, f"test_inference_output_{lang}.png")
    result.save(output_path)
    print(f"[{lang}] 생성 완료: {output_path} 저장됨")
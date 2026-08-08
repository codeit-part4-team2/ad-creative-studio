import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inference import load_pipeline, generate_image, _fit_square
from PIL import Image

# 이 스크립트 파일이 있는 폴더 경로 (실행 위치와 무관하게 고정됨)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 1회 로딩
pipe = load_pipeline()

# 상품 이미지 준비
product_image = Image.open(os.path.join(SCRIPT_DIR,"microwave.webp")).convert("RGB")
print(f"원본 이미지 크기 (W,H): {product_image.size}")
assert product_image.size[0] != product_image.size[1], "원본이 정사각형이라 letterbox 경로를 타지 않습니다!"

# --- 1단계: _fit_square() 단독 확인 (letterbox 검증)
fitted = _fit_square(product_image)
print(f"_fit_square() 처리 후 크기: {fitted.size}")
assert fitted.size == (1024,1024), f"letterbox 결과가 1024x1024가 아님: {fitted.size}"
fitted_check_path = os.path.join(SCRIPT_DIR, "microwave_fitted_check.png")
fitted.save(fitted_check_path)
print(f"letterbox 확인용 이미지 저장됨: {fitted_check_path}")

# --- 2단계: 전체 파이프라인 실행 (최종 출력 확인, 영어 프롬프트만) ---
prompt = "a small home appliance product photo, studio lighting, white background"
negative_prompt = "blurry, low quality, distorted"

result = generate_image(
    pipe=pipe,
    product_image=product_image,
    prompt=prompt,
    negative_prompt=negative_prompt,
    seed=42,
)
print(f"최종 출력 크기: {result.size}")
assert result.size == (1024,1024), f"최종 출력이 1024x1024가 아님: {result.size}"
output_path = os.path.join(SCRIPT_DIR,"test_inference_rect_output.png")
result.save(output_path)
print(f"생성완료: {output_path} 저장됨")
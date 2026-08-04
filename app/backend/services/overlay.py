"""
결정 7: 모델이 이미지 안에 한글을 그리지 않는다 - 배경 이미지 위에 PIL로 문구를 오버레이한다.
문구만 수정할 때 이미지를 재생성하지 않아도 된다 (PATCH /generations/{id}/copy 참고).
"""
from PIL import Image, ImageDraw, ImageFont

from app.prompt.templates import OUTPUT_FORMATS

FONT_PATH = "assets/fonts/NanumSquareBold.ttf"  # TODO: 실제 폰트 파일 배치


def overlay_copy(background_image: Image.Image, headline: str, subcopy: str,
                  output_format: str) -> Image.Image:
    spec = OUTPUT_FORMATS[output_format]
    img = background_image.resize(spec["size"]).convert("RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 44)
    except OSError:
        font = ImageFont.load_default()

    w, h = spec["size"]
    draw.text((40, h - 160), headline, font=font, fill="white")
    draw.text((40, h - 100), subcopy, font=font, fill="white")
    return img

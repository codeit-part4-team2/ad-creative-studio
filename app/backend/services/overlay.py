"""
결정 7: 모델이 이미지 안에 한글을 그리지 않는다 - 배경 이미지 위에 PIL로 문구를 오버레이한다.
문구만 수정할 때 이미지를 재생성하지 않아도 된다 (PATCH /generations/{id}/copy 참고).

M1(제품 보존형 배경 생성)은 R2/R3의 model_server가 아직 완성되지 않았으므로,
그때까지는 톤별 색상 placeholder 배경 위에 실제 오버레이를 적용해서
M3(문구 오버레이)·S2(규격별 실제 이미지 차별화)를 지금 바로 검증 가능하게 한다.
model_server 연동 후에는 배경만 실제 생성 이미지로 교체하면 되고, 오버레이 로직은 그대로 재사용된다.
"""
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.prompt.templates import OUTPUT_FORMATS

FONT_PATH = "assets/fonts/NanumGothic-Regular.ttf"  # 한글 지원 폰트, 없으면 시스템 기본으로 자동 폴백
OUTPUT_DIR = Path("data/outputs")

# 톤별 placeholder 배경색 (실제 모델 연동 전까지 임시) - 톤 느낌을 최소한으로 구분
TONE_PLACEHOLDER_COLOR = {
    "emotional": (196, 164, 132),   # 우드톤 베이지
    "modern": (60, 60, 65),         # 무채색 스튜디오
    "practical": (235, 245, 250),   # 밝은 주방톤
    "premium": (20, 20, 24),        # 다크 + (텍스트는 골드 느낌으로 별도 처리)
}
TONE_TEXT_COLOR = {
    "emotional": "white",
    "modern": "white",
    "practical": "black",
    "premium": "#D4AF37",  # 골드
}

# 규격별 텍스트 영역 여백/폭 - 이 폭을 넘으면 자동 줄바꿈
TEXT_MARGIN = 40
TEXT_AREA_RATIO = 0.85  # 이미지 너비의 85%까지만 텍스트가 차지하도록


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """max_width(px)를 넘지 않도록 글자 단위로 줄바꿈. 한글은 띄어쓰기가 없어도 넘칠 수 있어 글자 단위로 처리."""
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for ch in text:
        candidate = current + ch
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def create_placeholder_background(tone: str, size: tuple[int, int]) -> Image.Image:
    """model_server 연동 전 임시 배경. 실제 생성 이미지가 오면 이 함수 호출부만 교체하면 된다."""
    color = TONE_PLACEHOLDER_COLOR.get(tone, (128, 128, 128))
    return Image.new("RGB", size, color)


def overlay_copy(background_image: Image.Image, headline: str, subcopy: str,
                  output_format: str, tone: str = "modern") -> Image.Image:
    spec = OUTPUT_FORMATS[output_format]
    img = background_image.resize(spec["size"]).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = spec["size"]

    try:
        headline_font = ImageFont.truetype(FONT_PATH, max(28, w // 22))
        subcopy_font = ImageFont.truetype(FONT_PATH, max(20, w // 32))
    except OSError:
        headline_font = ImageFont.load_default()
        subcopy_font = ImageFont.load_default()

    text_color = TONE_TEXT_COLOR.get(tone, "white")
    max_text_width = int(w * TEXT_AREA_RATIO)

    headline_lines = _wrap_text(draw, headline, headline_font, max_text_width)
    subcopy_lines = _wrap_text(draw, subcopy, subcopy_font, max_text_width)

    # 아래에서부터 쌓아 올려서, 줄바꿈으로 늘어나도 이미지 밖(위/아래)으로 안 벗어나게 한다
    line_gap = 8
    headline_size = getattr(headline_font, "size", 20)
    subcopy_size = getattr(subcopy_font, "size", 14)
    headline_line_h = headline_size + line_gap
    subcopy_line_h = subcopy_size + line_gap
    block_height = len(headline_lines) * headline_line_h + len(subcopy_lines) * subcopy_line_h
    y = max(TEXT_MARGIN, h - TEXT_MARGIN - block_height)

    for line in headline_lines:
        draw.text((TEXT_MARGIN, y), line, font=headline_font, fill=text_color)
        y += headline_line_h
    for line in subcopy_lines:
        draw.text((TEXT_MARGIN, y), line, font=subcopy_font, fill=text_color)
        y += subcopy_line_h

    return img


def generate_and_save(job_id: str, tone: str, time_slot: str, headline: str, subcopy: str,
                       output_formats: list[str]) -> dict[str, str]:
    """
    톤별 placeholder 배경 위에 규격별로 실제 오버레이 이미지를 만들어 data/outputs/에 저장하고,
    /files/outputs/... 정적 서빙 URL을 규격별로 반환한다 (M3+S2 실제 동작).
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    urls: dict[str, str] = {}
    for fmt in output_formats:
        spec = OUTPUT_FORMATS[fmt]
        background = create_placeholder_background(tone, spec["size"])
        final_image = overlay_copy(background, headline, subcopy, fmt, tone=tone)

        filename = f"{job_id}_{tone}_{time_slot}_{fmt}_{uuid.uuid4().hex[:6]}.png"
        file_path = OUTPUT_DIR / filename
        final_image.save(file_path)

        urls[fmt] = f"/files/outputs/{filename}"
    return urls


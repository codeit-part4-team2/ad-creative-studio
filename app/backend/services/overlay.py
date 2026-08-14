"""
결정 7: 모델이 이미지 안에 한글을 그리지 않는다 - 배경 이미지 위에 PIL로 문구를 오버레이한다.

⚠️ 문서 정정: 원래 "문구만 수정할 때 이미지를 재생성하지 않아도 된다"는 전제였는데,
이제 문구가 PNG에 실제로 구워지므로(generate_and_save가 저장한 파일이 최종 결과물)
이 전제가 무효화됐다. PATCH /generations/{id}/copy(update_copy)는 지금 받은 문구를
그대로 되돌려줄 뿐 실제로 이미지를 다시 굽지도, job["result"]를 갱신하지도 않는다 -
History에는 여전히 옛 문구가 남는 상태다. 이 엔드포인트를 실제로 쓰려면
overlay.overlay_copy()를 재호출해서 이미지를 다시 저장하고 job["result"]도
갱신하도록 완성해야 한다 (기존 TODO 범위, 이 PR로 전제가 바뀌었다는 점만 남겨둔다).

M1(제품 보존형 배경 생성)은 R2/R3의 model_server가 아직 완성되지 않았으므로,
그때까지는 톤별 색상 placeholder 배경 위에 실제 오버레이를 적용해서
M3(문구 오버레이)·S2(규격별 실제 이미지 차별화)를 지금 바로 검증 가능하게 한다.
model_server 연동 후에는 배경만 실제 생성 이미지로 교체하면 되고, 오버레이 로직은 그대로 재사용된다.
"""
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.prompt.templates import OUTPUT_FORMATS

FONT_PATH = str(Path(__file__).resolve().parents[3] / "assets" / "fonts" / "NanumGothic-Regular.ttf")
# CWD 상대경로가 아니라 이 파일 위치 기준 절대경로로 고정 - uvicorn을 레포 루트가 아닌 곳에서
# 띄워도(예: 배포 스크립트가 다른 작업 디렉토리에서 실행) 폰트를 못 찾는 일이 없게 한다.
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


def _output_url(file_path: Path) -> str:
    relative_path = file_path.resolve().relative_to(Path("data").resolve())
    return f"/files/{relative_path.as_posix()}"


def save_source_image(
    *,
    job_id: str,
    tone: str,
    time_slot: str,
    image: Image.Image,
) -> str:
    """Persist the text-free model output without resizing or drawing copy."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = (
        f"{job_id}_{tone}_{time_slot}_source_{uuid.uuid4().hex[:6]}.png"
    )
    file_path = OUTPUT_DIR / filename
    image.convert("RGB").save(file_path, format="PNG")
    return _output_url(file_path)


def _fit_and_pad(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """
    단순 resize()는 비율을 무시하고 강제로 규격에 맞춰서, 정사각형이 아닌 실제 생성
    이미지(모델에서 받은 배경)를 규격이 다른 3종(1:1/가로형/세로형)으로 뽑을 때
    제품이 눌리거나 늘어난다. 이 프로젝트의 평가 1순위 지표가 제품 보존율이라
    후처리 단계에서 비율을 깨면 안 된다 - 비율은 유지한 채 캔버스 중앙에 배치하고
    남는 부분은 흰색으로 채운다(레터박스). placeholder(단색) 배경일 때도 결과는
    기존 resize()와 사실상 동일하므로 Mock 경로에는 영향 없다.
    """
    fitted = ImageOps.contain(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    x = (size[0] - fitted.width) // 2
    y = (size[1] - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas


def overlay_copy(background_image: Image.Image, headline: str, subcopy: str,
                  output_format: str, tone: str = "modern") -> Image.Image:
    spec = OUTPUT_FORMATS[output_format]
    img = _fit_and_pad(background_image, spec["size"])
    draw = ImageDraw.Draw(img)
    w, h = spec["size"]

    try:
        headline_font = ImageFont.truetype(FONT_PATH, max(28, w // 22))
        subcopy_font = ImageFont.truetype(FONT_PATH, max(20, w // 32))
    except OSError:
        print(f"[WARNING] 한글 폰트 로드 실패: {FONT_PATH} - 시스템 기본 폰트로 폴백 "
              f"(이 폰트는 한글 글리프가 없어 화면에 □□□로 나올 수 있습니다)")
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
                       output_formats: list[str], background_image: "Image.Image | None" = None) -> dict[str, str]:
    """
    배경 위에 규격별로 실제 오버레이 이미지를 만들어 OUTPUT_DIR에 저장하고,
    /files/... 정적 서빙 URL을 규격별로 반환한다 (M3+S2 실제 동작).

    background_image를 안 주면(Mock 경로) 톤별 placeholder를 새로 만들고,
    실제로 받은 배경 이미지가 있으면(model_server 연동 경로) 그걸 그대로 쓴다 -
    오버레이·규격 분기 로직은 배경이 어디서 왔든 완전히 동일하게 재사용된다.

    URL은 OUTPUT_DIR의 실제 위치를 기준으로 동적으로 만든다(하드코딩 안 함) -
    테스트에서 OUTPUT_DIR을 data/outputs/ 하위의 별도 서브폴더로 monkeypatch해서
    실제 데모 파일(data/outputs/ 최상위)을 안 건드리고 격리할 수 있게 하기 위함.

    TODO(follow-up, blocking 아님): 생성할 때마다 톤4종×규격3종 = 최대 12개 PNG가
    data/outputs/에 계속 쌓이기만 하고 지우는 로직이 없다. 데모 단계에선 무해하지만,
    운영 단계에선 오래된 파일 정리 정책(예: N일 지난 파일 삭제, 혹은 History에서
    삭제된 job의 파일도 같이 삭제)이 필요하다.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    urls: dict[str, str] = {}
    for fmt in output_formats:
        spec = OUTPUT_FORMATS[fmt]
        background = background_image if background_image is not None else create_placeholder_background(tone, spec["size"])
        final_image = overlay_copy(background, headline, subcopy, fmt, tone=tone)

        filename = f"{job_id}_{tone}_{time_slot}_{fmt}_{uuid.uuid4().hex[:6]}.png"
        file_path = OUTPUT_DIR / filename
        final_image.save(file_path)

        urls[fmt] = _output_url(file_path)
    return urls

import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.backend.schemas.generation import ProductCreateResponse
from app.backend.services.store import PRODUCTS

router = APIRouter(prefix="/api/v1/products", tags=["products"])

UPLOAD_DIR = Path("data/uploads")
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB (가이드 상세 이미지 업로드 제한과 동일하게)


@router.post("", response_model=ProductCreateResponse)
async def create_product(
    image: UploadFile = File(...),
    product_name: str = Form(...),
    price: Optional[int] = Form(None),
    selling_points: Optional[str] = Form(None),  # comma-separated, TODO: JSON 배열로 교체
):
    suffix = Path(image.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"허용되지 않는 파일 형식: {suffix or '(없음)'}. jpg/jpeg/png만 가능")

    content = await image.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, f"파일이 너무 큽니다 (최대 {MAX_UPLOAD_BYTES // (1024*1024)}MB)")
    if not content:
        raise HTTPException(400, "빈 파일입니다")

    product_id = f"prd_{uuid.uuid4().hex[:6]}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / f"{product_id}{suffix}"
    file_path.write_bytes(content)

    image_url = f"/files/uploads/{product_id}{suffix}"
    PRODUCTS[product_id] = {
        "product_name": product_name,
        "price": price,
        "selling_points": (selling_points or "").split(",") if selling_points else [],
        "image_url": image_url,
        "image_path": str(file_path),
    }
    return ProductCreateResponse(product_id=product_id, image_url=image_url)

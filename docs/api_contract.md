# API Contract

## 러시아워 쇼츠 승인 API (현재 계약)

쇼츠는 `commute_am` 또는 `commute_pm` 결과에서만 만들 수 있으며 1080x1920, 30fps,
H.264/AAC, 10~15초입니다. 기존 대표 이미지 1장과 모델 서버가 순차 생성한 이미지 2장,
MeloTTS 한국어 음성 4개, 밝은 외곽선 자막으로 무표정 AI 코믹 영상을 만듭니다. 음악은 사용하지 않습니다.

### POST /api/v1/videos

요청은 `{ "result_id": "res_005528a3" }`입니다. 성공 시 `202`와 아래 응답을 반환합니다.

```json
{ "video_job_id": "video_4fd12ab89c31", "render_status": "queued" }
```

알 수 없는 결과는 `404`, 러시아워가 아닌 결과는 `400`, 활성 중복 작업은 `409`입니다.
렌더링은 BackgroundTasks에서 실행되며 생성 응답은 승인을 의미하지 않습니다.

### GET /api/v1/videos/{video_job_id}

렌더링, 검수, 외부 게시 상태를 분리해 반환합니다.

```json
{
  "video_job_id": "video_4fd12ab89c31",
  "result_id": "res_005528a3",
  "product_id": "prd_001",
  "tone": "practical",
  "time_slot": "commute_am",
  "render_status": "completed",
  "approval_status": "pending",
  "publish_status": "not_requested",
  "video_url": "/files/videos/video_4fd12ab89c31.mp4",
  "script_version": "deadpan-ai-v1",
  "script_lines": ["전자레인지입니다.", "저는 퇴근을 하지 않습니다."],
  "tts_engine": "melotts-korean",
  "tts_voice_preset": "deadpan-ai-v1",
  "tts_audio_sha256": "<64자리 SHA-256>",
  "pronunciation_review_required": false,
  "pronunciation_reviewed_at": null,
  "scene_image_sha256s": ["<hero>", "<self-aware>", "<benefit>"],
  "caption_layout_version": "bright-outline-v1"
}
```

`pronunciation_review_required=true`이면 영상을 직접 듣고 발음이 정확한 경우에만 승인 요청의
`pronunciation_confirmed`를 `true`로 보냅니다. 확인 시각은 `pronunciation_reviewed_at`에 기록됩니다.

### POST /api/v1/videos/{video_job_id}/approve

```json
{
  "activation_at": "2026-08-10T08:00:00+09:00",
  "publish_to_youtube": false,
  "pronunciation_confirmed": false
}
```

- `activation_at`은 UTC offset이 필수이고 현재보다 최소 10분 이후여야 합니다.
- `commute_am`은 KST 08:00 이상 09:30 미만, `commute_pm`은 18:00 이상 19:30 미만입니다.
- 원본 광고 지문, MP4 SHA-256, TTS SHA-256, 서로 다른 장면 이미지 3개의 SHA-256을 승인 직전에 검사합니다.
- 발음 검수가 필요한 영상은 사람의 명시적 청취 확인 없이는 승인할 수 없습니다.
- 동일 요청은 멱등이며, 승인 이후 다른 예약 조건으로 변경하면 `409`입니다.
- 일정 검증 실패는 `422`, 상태·무결성·발음 확인 충돌은 `409`입니다.
- YouTube 요청 시 성공 응답은 우선 `publish_status=pending`이며 업로드는 백그라운드 처리됩니다.

### POST /api/v1/videos/{video_job_id}/reject

검수 대기 상태만 거절할 수 있습니다. 성공 시 `200`, 이미 승인 또는 거절된 작업은 `409`입니다.

### GET /api/v1/youtube/status

```json
{
  "configured": false,
  "connection_id": "demo_merchant_channel",
  "token_available": false
}
```

토큰 값, OAuth 파일 경로, 클라이언트 비밀은 반환하지 않습니다.

### GET /api/v1/exposure/{product_id}

기존 배너 응답에 `video`가 추가됩니다. 승인·렌더 완료·활성 시각 도달·상품/러시아워 일치
조건을 모두 만족하는 최신 영상만 반환합니다. YouTube 게시 실패는 내부 노출을 막지 않습니다.

```json
{
  "time_slot": "commute_am",
  "available": true,
  "tones": [],
  "video": {
    "video_job_id": "video_4fd12ab89c31",
    "video_url": "/files/videos/video_4fd12ab89c31.mp4"
  }
}
```

서버 재시작 시 중단된 렌더는 `failed`, 결과가 불확실한 YouTube 업로드는
`needs_review`로 복구합니다. 내부 승인 상태는 YouTube 상태와 독립적으로 유지됩니다.
렌더와 YouTube 게시 작업은 각각 서비스 전역 큐에서 직렬화하며 운영 프로세스는 1개를 사용합니다.

---

R2/R3(model_server)와 R4+R5(app/backend) 사이의 계약입니다. 이 문서만 맞으면
서로 상대방의 구현을 기다리지 않고 병렬로 개발할 수 있습니다.

> **업데이트**: 시간대는 1차 회의록의 3종(아침/점심/저녁)에서, PM 승인으로
> 러시아워를 반영한 **6종 + 체크박스 다중 선택**으로 변경되었습니다
> (소형가전은 출퇴근 시간대와 퇴근 후의 구매 심리가 다르다는 근거).
> 한 번에 최대 3개까지만 선택 가능합니다 (`MAX_TIME_SLOTS_PER_REQUEST`, GPU 대기열 보호).

---

## 1. Public API (app/frontend ↔ app/backend)

### POST /api/v1/products
상품 등록 (multipart/form-data, 이미지 포함)

```json
{
  "product_name": "스팀 에어프라이어 5L",
  "price": 89000,
  "selling_points": "기름 없이 조리,1인 가구 추천"
}
```
응답
```json
{ "product_id": "prd_001", "image_url": "/files/products/prd_001.png" }
```

### POST /api/v1/generations
광고 생성 요청

```json
{
  "product_id": "prd_001",
  "tones": ["emotional", "modern", "practical", "premium"],
  "time_slots": ["commute_am", "evening"],
  "output_formats": ["thumbnail", "detail_banner", "sns_card"]
}
```
- `tones`는 생략하면 4종 전체가 기본값 (M2 — 항상 4종 동시 생성)
- `time_slots`는 1개 이상, 최대 3개: `morning | commute_am | afternoon | commute_pm | evening | late_night`

응답 — `202`
```json
{ "job_id": "job_001", "status": "queued", "estimated_seconds": 120 }
```

### GET /api/v1/jobs/{job_id}
생성 진행 상태 (폴링)
```json
{
  "job_id": "job_001",
  "status": "processing",
  "progress": 60,
  "current_step": "background_generation",
  "completed_count": 2,
  "total_count": 8,
  "estimated_seconds": 120
}
```
`total_count` = 톤 수 × 선택 시간대 수 (예: 4톤 × 2시간대 = 8)

### GET /api/v1/generations/{job_id}
완료된 결과 조회
```json
{
  "job_id": "job_001",
  "status": "completed",
  "results": [
    {
      "tone": "emotional",
      "time_slot": "commute_am",
      "headline": "아침의 여유",
      "subcopy": "10분이면 완성되는 아침",
      "images": {
        "thumbnail": "/files/result_01_1x1.png",
        "detail_banner": "/files/result_01_banner.png",
        "sns_card": "/files/result_01_4x5.png"
      }
    }
    // ... 선택한 톤 x 시간대 조합 수만큼 반복
  ]
}
```

### PATCH /api/v1/generations/{generation_id}/copy
이미지는 재생성하지 않고 문구만 수정 (PIL 오버레이 전략의 핵심 이점, 결정 7)
```json
{ "headline": "새로운 아침의 시작", "subcopy": "간편하게 즐기는 스팀 요리" }
```

### GET /api/v1/history
생성 이력 조회

### GET /api/v1/usage
OpenAI 텍스트 사용 비용 현황 ($20 경고 / $25 로컬 전환)

### GET /api/v1/exposure/{product_id}
지금 이 순간 노출해야 할 시간대 배너 조회 (S1 — 시간대별 제품 노출 알고리즘, 강사님 피드백 반영)
```json
{
  "time_slot": "commute_am",
  "time_slot_label": "출근 러시아워",
  "available": true,
  "tones": [
    { "tone": "emotional", "time_slot": "commute_am", "headline": "...", "subcopy": "...", "images": {...} }
  ]
}
```
현재 시각을 6개 시간대 슬롯으로 자동 판정(`app/backend/services/exposure.py`) 후, 해당 상품의
History에서 그 시간대 결과가 있으면 반환, 없으면 `available: false`. 실제 사이니지·스토어 배너
자동 전환의 기반 로직.

### POST /api/v1/videos
러시아워(출근/퇴근) 결과 한정 코믹 TTS 쇼츠 생성 요청입니다. 현재 요청·응답·승인 계약은
문서 첫 절의 **러시아워 쇼츠 승인 API**를 따릅니다. 요청에 `time_slot`을 받지 않고,
`result_id`로 찾은 실제 결과의 시간대를 검증합니다.

### GET /api/v1/videos/{job_id}
쇼츠 렌더·발음 검수·승인·게시 상태를 조회합니다. 완료되면 실제 `video_url`과 TTS/장면/자막
무결성 메타데이터가 채워지고 History의 해당 결과에도 반영됩니다.

---

## 2. Model Server 계약 (app/backend ↔ model_server, R2·R3 소유)

### POST {MODEL_SERVER_URL}/infer

요청
```json
{
  "product_id": "prd_001",
  "product_image_url": "http://backend:8000/files/uploads/prd_001.png",
  "tone": "emotional",
  "image_prompt": "Create a product advertisement background for ... (영어)",
  "negative_prompt": "blurry, distorted product, extra logo, watermark",
  "time_slot": "commute_am"
}
```

응답
```json
{
  "status": "done",
  "generated_image_url": "/files/outputs/bg.png",
  "product_preserved": true,
  "gen_time_sec": 8.4,
  "gpu_queue_wait_sec": 0.0,
  "preservation_method": "source_alpha_composite",
  "stage_times_sec": {
    "preprocess": 0.8,
    "gpu_queue_wait": 0.0,
    "generate": 6.9,
    "composite": 0.2,
    "save": 0.1
  },
  "cache_hit": true,
  "model_profile": "fast_composite",
  "num_inference_steps": 4,
  "background_size": 768,
  "output_size": 1024,
  "peak_vram_gb": null
}
```

`image_prompt`/`negative_prompt`는 `app/prompt/builder.py`가 만들어서 전달합니다.
`product_preserved`는 R2/R3가 자체 검증 후 반환 — 평가 1순위 지표(제품 보존율)와 연동됩니다.
기존 필드는 그대로 유지하며, 성능·보존 메타데이터는 선택 필드입니다.
`gpu_queue_wait_sec`는 프로세스 내부 GPU 잠금 획득 전 대기시간이고,
`stage_times_sec.generate`는 실제 GPU 모델 호출시간입니다. 전체 `gen_time_sec`에는
두 시간이 모두 포함됩니다.
`product_image_url`은 model_server에서 접근 가능한 HTTP(S) 절대 URL이어야 합니다.
backend는 저장된 상대경로를 `BACKEND_PUBLIC_URL` 기준 절대 URL로 변환해 전송합니다.
이미 절대 URL인 경우에도 `BACKEND_PUBLIC_URL`과 같은 origin만 허용합니다.
model_server는 `MODEL_IMAGE_ALLOWED_ORIGINS`에 등록된 origin만 내려받고 redirect를
거부합니다.
`generated_image_url`이 상대경로면 backend가 `MODEL_SERVER_URL`을 붙여 다운로드합니다.

코믹 쇼츠 1건은 기존 광고 대표 이미지 1장을 그대로 재사용하고, 위 계약을 바꾸지 않은 `/infer`
요청을 정확히 2번 **순차 호출**해 자기인식·소구점 장면을 만듭니다. `product_preserved=true`인
응답만 사용합니다. TTS와 FFmpeg 렌더링은 CPU 백엔드 소유이며 모델 서버 GPU/VRAM을 사용하지 않습니다.

### GET {MODEL_SERVER_URL}/health

모델 가중치를 로드하지 않고 프로세스 상태를 확인합니다.

```json
{ "status": "ok", "model_loaded": false }
```

### POST {MODEL_SERVER_URL}/warmup

최초 사용자 요청 전에 모델 가중치를 명시적으로 로드합니다. 성공하면
`model_loaded: true`를 반환합니다. 다운로드·로드 시간은 실제 생성 지연시간과
분리해서 기록합니다. `torch.compile`을 켠 경우 첫 `/infer`에서 그래프가
컴파일되므로 측정 전에 실제 payload로 추가 워밍업이 필요합니다.

성공:

```json
{ "status": "ok", "model_loaded": true }
```

실패 시 내부 예외 내용은 노출하지 않습니다.

```json
{
  "status": "failed",
  "model_loaded": false,
  "error_message": "model_load_failed"
}
```

### R3에게 전달할 핵심 경계 (요약)
- **모델 입력**: 제품 이미지는 model_server가 접근 가능한 절대 URL로 전달. backend가 상대 정적 경로를 `BACKEND_PUBLIC_URL`과 결합하며 바이너리 직접 전송은 안 함
- **시간대/톤 enum**: `app/prompt/schemas.py`의 `TimeSlotLiteral`(6종) / `ToneLiteral`(4종) 그대로 사용
- **생성 단위**: 기본 광고는 `시간대 × 톤`, 코믹 쇼츠는 선택된 결과당 추가 `/infer` 2회 순차 호출. 출력 규격과 TTS/영상 합성은 `app/backend` 소유
- **성공 응답**: 위 스키마 그대로 (`status: "done"`)
- **실패 응답**: `status: "failed"`, `error_message: string` 포함해서 반환 (아래 참고)
```json
{ "status": "failed", "error_message": "CUDA OOM", "generated_image_url": null }
```
- **타임아웃**: `app/backend`는 `httpx.AsyncClient(timeout=120)`으로 호출 (120초). 그 이상 걸리면 클라이언트에서 타임아웃 예외 발생 → job이 `failed`로 처리됨. R3 쪽에서도 이 시간 내 응답하거나, 더 걸릴 경우 큐/폴링 방식으로 별도 협의 필요
- **오류 코드**: HTTP 5xx는 모델 서버 내부 오류로 간주해 재시도 없이 즉시 `failed` 처리. 429는 대기열 초과로 간주해 재시도 로직을 붙일 수 있음(아직 미구현)

## 개발 순서 제안
1. R2/R3: `model_server/README.md`의 Mock 서버부터 (오늘 중 공유 요청)
2. R4+R5: `/api/v1/products`, `/api/v1/generations`, `/api/v1/jobs/{id}` 뼈대 먼저 → Mock 서버 붙여서 더미 E2E 관통 (Gate 0 조건)
3. 시간대 필드는 Sprint 0부터 스키마에 포함 완료 (`app/prompt/schemas.py`)

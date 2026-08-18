# Model Server

담당: 성치용, 유수빈, 김재헌

SDXL 광고 배경을 생성하고 원본 상품을 보존하는 별도 FastAPI 추론 서버입니다.
backend 연동 계약은 [API 계약](../docs/api_contract.md), L4 검증 절차는
[벤치마크 체크리스트](../docs/L4_BENCHMARK_CHECKLIST.md)를 따릅니다.

## 프로필

- `fast_composite` (기본): SDXL + LCM-LoRA 4-step으로 빈 광고 배경을 만든 뒤,
  기본 768×768 배경을 1024×1024로 확대한 후 rembg로 분리한 1024×1024 원본 상품
  캔버스를 알파 합성합니다. 비정사각형 프리셋은 `FAST_BACKGROUND_SIZE=768`,
  `IMAGE_SIZE=1024`를 기준으로 같은 배율의 8픽셀 그리드 크기를 계산하므로 환경변수
  튜닝을 바꿔도 원래 비율을 유지합니다.
- `quality_regenerate`: SDXL + 공식 Canny ControlNet + IP-Adapter를 30-step으로
  실행하는 비교군입니다. 제품 보존 여부를 측정하지 않았으므로 성공 응답에서도
  `product_preserved`를 임의로 `true`로 표시하지 않습니다.

공통으로 모델은 프로세스당 한 번만 로드하고, 상품 전처리와 IP-Adapter 임베딩을
TTL/LRU 캐시하며, GPU 호출은 한 번에 하나씩 실행합니다. 두 프로필 모두
`madebyollin/sdxl-vae-fp16-fix`를 명시적으로 사용해 SDXL 기본 VAE의 FP32
디코딩 전환을 피합니다.

## 설치

Python 3.11 이상이 필요하며 L4 기준 환경은 Python 3.11 또는 3.12를 사용합니다.
PyTorch CUDA wheel은 VM 드라이버와 맞는
공식 인덱스에서 먼저 설치한 뒤 나머지 의존성을 설치합니다.

```bash
python -m venv ~/serving/venv
source ~/serving/venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r model_server/requirements-torch-cu132.txt
python -m pip install -r model_server/requirements.txt
```

`model_server/requirements-torch-cu132.txt`는 PyTorch, torchvision 버전과 공식
CUDA wheel 인덱스를 함께 고정합니다. 나머지 직접 의존성은
`model_server/requirements.txt`에 정확한 버전으로 고정되어 있습니다.

설치 용량은 PyTorch와 SDXL 가중치 때문에 수 GB 이상입니다. 모델 가중치는 Git에
커밋하지 않습니다.

## 실행과 워밍업

```bash
uvicorn model_server.main:app --host 0.0.0.0 --port 8001 --workers 1
curl http://127.0.0.1:8001/health
curl -X POST http://127.0.0.1:8001/warmup
```

> **운영 필수:** NVIDIA L4 한 장에는 model server 프로세스와 Uvicorn worker를
> 정확히 하나만 실행합니다. `--workers 1`을 제거하거나 복제본이 같은 GPU를
> 공유하게 구성하면 프로세스 내부 GPU 잠금이 요청을 직렬화하지 못합니다.

`/warmup`은 첫 사용자 요청 전에 모델 다운로드·로드를 끝내기 위한 엔드포인트입니다.
실패하면 내부 예외 문자열 대신
`{"status":"failed","model_loaded":false,"error_message":"model_load_failed"}`를
반환합니다.
`ENABLE_TORCH_COMPILE=true`일 때 실제 그래프 컴파일은 첫 `/infer`에서 일어나므로,
측정 전 동일 payload로 한 번 더 추론 워밍업해야 합니다.
CPU 추론은 실수로 대형 모델을 내려받지 않도록 기본 차단됩니다.
GPU 모델을 프로세스마다 따로 올리므로 `--workers 1`을 유지해야 합니다. 동시 요청은
프로세스 내부 GPU 잠금으로 직렬화됩니다. 성공 응답의 `gpu_queue_wait_sec`와
`stage_times_sec.gpu_queue_wait`는 GPU 잠금 획득 전 대기시간을 나타내며,
`stage_times_sec.generate`는 실제 모델 호출시간만 나타냅니다.
`/infer`와 `/warmup`은 인증 없는 내부 서비스 엔드포인트이므로 인터넷에 직접 공개하지
말고 GCP 방화벽 또는 reverse proxy에서 backend만 접근하도록 제한합니다.

## backend 연동

backend가 별도 프로세스 또는 호스트라면 다음 값을 실제 접근 가능한 주소로 지정합니다.

```dotenv
MODEL_SERVER_URL=http://model-server:8001
BACKEND_PUBLIC_URL=http://backend:8000
MODEL_IMAGE_ALLOWED_ORIGINS=http://backend:8000
MODEL_OUTPUT_DIR=/srv/ad-creative-studio/data/outputs
USE_MOCK_GENERATION=false
```

`MODEL_IMAGE_ALLOWED_ORIGINS`는 model server가 상품 이미지를 내려받을 수 있는
HTTP(S) origin의 쉼표 구분 목록입니다. 요청 URL은 이 목록과 일치해야 하고 redirect는
허용하지 않습니다.

모델 서버 설정은 루트 [환경변수 예시](../.env.example)에 정리되어 있습니다.

## 벤치마크

요청 JSON을 준비하고 모델이 워밍업된 뒤 실행합니다.

```bash
python -m tools.benchmark_latency \
  --payload docs/examples/model_server_infer_payload.json \
  --url http://127.0.0.1:8001/infer \
  --warmup 1 \
  --runs 10
```

출력에는 전체 P50/P95, preprocess/gpu_queue_wait/generate/composite/save 단계별 중앙값,
`model_profile`, step, `output_format`, `background_width`/`background_height`,
`output_width`/`output_height`가 포함됩니다. 기존 `background_size`/`output_size`는
정사각형 요청에서만 값이 있고 비정사각형에서는 `null`입니다.
실제 L4 성능과 이미지 품질은 아직 로컬 테스트만으로 확정할 수 없습니다.

광고 생성 프리셋은 `thumbnail`(1:1), `sns_card`(4:5), `story_vertical`(9:16),
`wide_banner`(16:9) 네 가지입니다. `output_format`을 생략한 기존 호출은
`thumbnail`로 동작합니다. 두 비율을 선택한 백엔드 요청도 GPU에서는 병렬화하지 않고
두 `/infer` 요청을 순차 실행합니다.

2026-08-10 서빙 담당자 보고에서는 fast 768 후보의 warm 10회 결과가 다음과
같았습니다. 원본 결과 JSON과 `background_size=768`, `output_size=1024` 메타데이터는
아직 이 저장소에서 직접 검증하지 않았으므로 외부 보고값으로만 취급합니다.

| Step | P50 | P95 | Peak VRAM | 제품 보존 응답 |
|---:|---:|---:|---:|---:|
| 4 | 2.37s | 3.98s | 10.85GB | 10/10 true |
| 6 | 2.97s | 4.52s | 10.85GB | 10/10 true |
| 8 | 3.46s | 5.00s | 10.85GB | 10/10 true |

기본값은 4-step을 유지합니다. FP16-safe VAE 적용 전후의 속도와 동일 seed 이미지
차이는 L4에서 다시 비교한 뒤 merge 여부를 판단합니다.

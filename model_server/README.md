# Model Server

담당: 성치용, 유수빈, 김재헌

SDXL 광고 배경을 생성하고 원본 상품을 보존하는 별도 FastAPI 추론 서버입니다.
backend 연동 계약은 [API 계약](../docs/api_contract.md), L4 검증 절차는
[벤치마크 체크리스트](../docs/L4_BENCHMARK_CHECKLIST.md)를 따릅니다.

## 프로필

- `fast_composite` (기본): SDXL + LCM-LoRA 4-step으로 빈 광고 배경을 만든 뒤,
  rembg로 분리한 원본 상품을 알파 합성합니다. 제품 픽셀 보존과 낮은 지연시간이 목적입니다.
- `quality_regenerate`: SDXL + 공식 Canny ControlNet + IP-Adapter를 30-step으로
  실행하는 비교군입니다. 제품 보존 여부를 측정하지 않았으므로 성공 응답에서도
  `product_preserved`를 임의로 `true`로 표시하지 않습니다.

공통으로 모델은 프로세스당 한 번만 로드하고, 상품 전처리와 IP-Adapter 임베딩을
TTL/LRU 캐시하며, GPU 호출은 한 번에 하나씩 실행합니다.

## 설치

Python 3.11 또는 3.12 환경을 권장합니다. PyTorch CUDA wheel은 VM 드라이버와 맞는
공식 인덱스에서 먼저 설치한 뒤 나머지 의존성을 설치합니다.

```bash
python -m venv ~/serving/venv
source ~/serving/venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.12.1 torchvision==0.27.1 \
  --index-url https://download.pytorch.org/whl/cu132
python -m pip install -r model_server/requirements.txt
```

설치 용량은 PyTorch와 SDXL 가중치 때문에 수 GB 이상입니다. 모델 가중치는 Git에
커밋하지 않습니다.

## 실행과 워밍업

```bash
uvicorn model_server.main:app --host 0.0.0.0 --port 8001 --workers 1
curl http://127.0.0.1:8001/health
curl -X POST http://127.0.0.1:8001/warmup
```

`/warmup`은 첫 사용자 요청 전에 모델 다운로드·로드를 끝내기 위한 엔드포인트입니다.
`ENABLE_TORCH_COMPILE=true`일 때 실제 그래프 컴파일은 첫 `/infer`에서 일어나므로,
측정 전 동일 payload로 한 번 더 추론 워밍업해야 합니다.
CPU 추론은 실수로 대형 모델을 내려받지 않도록 기본 차단됩니다.
GPU 모델을 프로세스마다 따로 올리므로 `--workers 1`을 유지해야 합니다. 동시 요청은
프로세스 내부 GPU 잠금으로 직렬화됩니다.
`/infer`와 `/warmup`은 인증 없는 내부 서비스 엔드포인트이므로 인터넷에 직접 공개하지
말고 GCP 방화벽 또는 reverse proxy에서 backend만 접근하도록 제한합니다.

## backend 연동

backend가 별도 프로세스 또는 호스트라면 다음 값을 실제 접근 가능한 주소로 지정합니다.

```dotenv
MODEL_SERVER_URL=http://model-server:8001
BACKEND_PUBLIC_URL=http://backend:8000
MODEL_OUTPUT_DIR=/srv/ad-creative-studio/data/outputs
USE_MOCK_GENERATION=false
```

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

출력에는 전체 P50/P95와 preprocess/generate/composite/save 단계별 중앙값이 포함됩니다.
실제 L4 성능과 이미지 품질은 아직 로컬 테스트만으로 확정할 수 없습니다.

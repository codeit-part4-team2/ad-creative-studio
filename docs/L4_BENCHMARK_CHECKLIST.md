# NVIDIA L4 Benchmark Checklist

## 목적

같은 상품, 프롬프트, seed, 최종 1024×1024 출력 조건에서 기존 품질 경로와 fast
경로의 warm latency와 시각 품질을 비교합니다. fast 경로는 배경 생성 크기만 1024와
768로 나눠 측정합니다. 최초 모델 다운로드·로딩·컴파일 시간은 별도 cold-start 값으로 기록합니다.

## 환경 기록

```bash
nvidia-smi
python --version
python -c "import torch,diffusers,transformers; print(torch.__version__, diffusers.__version__, transformers.__version__)"
python -c "import torch,torchvision; assert torch.__version__.split('+')[0] == '2.12.1'; assert torchvision.__version__.split('+')[0] == '0.27.1'"
pgrep -af "uvicorn model_server.main:app"
python -m pip freeze --all > benchmark-environment.txt
```

아래 항목을 결과와 함께 저장합니다.

- GPU 이름, 드라이버, CUDA, 총 VRAM
- Python, PyTorch, Diffusers, Transformers 버전
- `uvicorn model_server.main:app ... --workers 1` 프로세스가 하나만 실행되는지
- Git commit 또는 전달받은 소스 SHA-256
- 프로필, step, guidance scale, 배경 생성 크기, 최종 출력 크기, compile 여부
- `MODEL_IMAGE_ALLOWED_ORIGINS` 값과 backend 접근 가능 여부
- GCP 방화벽 또는 reverse proxy에서 model server 8001 포트를 backend에만 허용했는지

## 실험 행렬

| 실험 | 프로필 | 배경 크기 | 최종 크기 | Step | Compile |
|---|---|---:|---:|---:|---|
| A | `quality_regenerate` | 1024 | 1024 | 30 | false |
| B0 | `fast_composite` | 1024 | 1024 | 4 | false |
| B | `fast_composite` | 768 | 1024 | 4 | false |
| C | `fast_composite` | 768 | 1024 | 6 | false |
| D | `fast_composite` | 768 | 1024 | 8 | false |
| E | 선정된 fast 설정 | 768 | 1024 | 선택 | true |

각 실험은 모델 로드 후 워밍업 1회, 측정 10회 이상 수행합니다. 서로 다른 프로필은 같은 프로세스에 동시에 올리지 않습니다.
요청 예시는 `docs/examples/model_server_infer_payload.json`을 복사해 실제 업로드 URL로
바꿔 사용합니다.

## 성능 판정

- API 전체 P50/P95
- 응답 `background_size`와 `output_size`가 실험 행렬과 일치하는지
- `preprocess`, `gpu_queue_wait`, `generate`, `composite`, `save` 단계별 중앙값
- 첫 요청 cold-start 시간
- 캐시 miss와 hit 각각의 시간
- peak VRAM과 OOM 여부

순차 지연시간 측정과 별도로, 서로 다른 `product_id`와 `product_image_url` 두 건을
동시에 요청합니다. 두 요청의 preprocess가 서로를 막지 않는지 확인하고, GPU generate
단계는 의도대로 직렬 실행되는지 기록합니다. 같은 상품의 반복 요청만 사용하면 키별
캐시 동시성 문제를 발견할 수 없습니다.

## FP16-safe VAE 후속 비교

fast 경로가 `madebyollin/sdxl-vae-fp16-fix`를 명시적으로 사용한 후보와 이전 stock
SDXL VAE 결과를 같은 seed, 상품, 프롬프트, 768 배경, 4-step 조건으로 비교합니다.

- P50/P95와 `generate`, `gpu_queue_wait` 단계 중앙값
- peak VRAM, OOM, 실패 건수
- `AutoencoderKL` dtype 및 deprecated `upcast_vae` 경고 발생 여부
- 동일 seed 생성 이미지의 배경 디테일, 색상, 밴딩, NaN 또는 검은 이미지 여부
- 응답 `background_size=768`, `output_size=1024` 확인

모델 카드가 stock VAE와 미세한 출력 차이를 명시하므로 경고가 사라졌다는 사실만으로
채택하지 않고, 속도와 시각 품질을 함께 판정합니다.

## 품질 판정

소형가전 상품 최소 20개와 네 톤을 사용합니다.

- 상품 색상, 로고, 버튼, 포트, 외곽 형태 보존
- 배경에 중복 상품이 생성되지 않았는지
- 상품과 표면의 위치·그림자 자연스러움
- 시간대/톤 프롬프트 반영
- 4·6·8 step 블라인드 선호도

fast 경로는 원본 상품을 합성하므로 `product_preserved=true`를 반환합니다. 다만 rembg가 상품 일부를 누락한 경우까지 성공으로 간주하면 안 되므로 마스크 품질은 별도 실패율로 기록합니다.

## 완료 기준

- 선정된 fast 설정의 P95가 팀이 정한 목표 이하
- OOM 0건
- 테스트 상품의 마스크 치명 오류율이 합의 기준 이하
- 4/6/8-step 중 지연시간과 블라인드 품질 기준을 함께 만족하는 설정이 선정됨
- 결과 JSON, 생성 이미지, 환경 로그를 팀 저장소 밖 검토 폴더에 먼저 보관

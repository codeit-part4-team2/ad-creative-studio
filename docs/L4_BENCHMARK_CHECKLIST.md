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

## VRAM 최적화 실험 근거 (8/14)

`fast_composite`(운영 확정 프로필, 768 배경/4-step) 기준 peak VRAM 8.28GB, P50 1.72s를
baseline(8/11 확정)으로 삼아 세 가지 최적화 후보를 개별 격리 검증했습니다.

(peak VRAM 8.28GB는 8/11 동시성 테스트 원본 결과이며, 근거 스크린샷은
docs/verification/concurrency_test_20260811.png에 있습니다.
P50 1.72s는 docs/model_server_handoff.md의 8/11 확정 항목과 동일합니다.)

세 실험 모두 위 "실험 행렬" 절의 규칙대로 워밍업 1회 + 측정 10회 반복으로 P50을 기록했습니다. peak VRAM은 slicing/tiling 두 후보만 별도 동시성 테스트로 측정했고,
offload는 P50 결과(3.8배 저하)만으로 판단이 충분해 VRAM 측정을 생략했습니다.

| 후보 | peak VRAM | P50 | 결론 |
|---|---:|---:|---|
| baseline | 8.28GB | 1.72s | — |
| `enable_vae_slicing()` | 8.29GB (변화 없음) | 1.80s (+4.7%) | 이득 없음, 코드 제거 |
| `enable_vae_tiling()` | 7.54GB (-8.8%) | 1.87s (+8.7%) | 옵션 플래그로 보류 |
| `enable_model_cpu_offload()` | 측정 불필요 | 6.57s (+282%) | 명확한 손해, 즉시 롤백 |

**VAE slicing** — diffusers 표준 최적화 기법이나 batch=1 환경에서는 쪼갤 배치 자체가
없어 VRAM 이득이 없고 분기 처리 오버헤드만 남습니다. 코드에서 완전히 제거했습니다.

**VAE tiling** — 유일하게 실측 이득이 있었던 후보입니다. 다만 baseline 8.28GB는 L4 24GB의 약 34.5%로 이미 여유가 충분하고, tiling으로 확보되는 절대 용량(0.74GB)이 지금
당장 기능·해상도 확장을 열어줄 수준은 아닙니다. 반면 모든 요청에 8.7% 지연이 붙고,
타일 경계·디테일 품질 리스크는 아직 검증하지 않았습니다. `ENABLE_VAE_TILING` 환경변수로
기본 `false` 유지하며, 코드는 `model_server/pipelines.py`에 조건부로 남겨둡니다.

- **재검토 발동 조건**: peak VRAM이 16.8~18GB를 초과하거나 OOM이 관측될 때, 동일 seed
  기준 품질(PSNR) 비교와 P95 재측정을 거쳐 활성화 여부를 재판단합니다.

**텍스트 인코더 CPU 오프로드** — SDXL의 텍스트 인코더 2개(~1.4GB, fp16)를 프롬프트
인코딩 이후 유휴 상태로 GPU에 물고 있는 구조에 착안해 `enable_model_cpu_offload()`를
시도했습니다. 4-step처럼 스텝당 연산이 짧은 파이프라인에서는 컴포넌트 간 CPU↔GPU 전송
비용이 연산 시간을 압도해 P50이 3.8배(+282%) 느려졌습니다. VRAM 이득을 따질 필요가
없을 만큼 명확한 손해라 별도 재측정 없이 즉시 롤백했고, 코드·브랜치·`.env` 전부
원상복구했습니다. 옵션 플래그도 남기지 않았습니다.

**최종 운영 구성**: slicing 코드 제거 / tiling 옵션 플래그·기본 OFF / model_cpu_offload
전체 롤백. `fast_composite` 파이프라인 자체는 실험 전과 동일하게 동작합니다.

## 품질 판정

소형가전 상품 최소 20개와 네 톤을 사용합니다.

- 상품 색상, 로고, 버튼, 포트, 외곽 형태 보존
- 배경에 중복 상품이 생성되지 않았는지
- 제품 뒤에 대형 시계·손목시계·타이머·다이얼처럼 제품과 경쟁하는 원형 소품이 없는지
- 두 번째 가전·포장·상품처럼 오인되는 큰 배경 물체가 없는지
- 소프트박스·삼각대·스튜디오 조명 등 촬영 장비가 프레임에 노출되지 않았는지
- 제품 배치 영역 뒤가 비어 있고, 장식 소품이 프레임 가장자리의 작은 크기로 제한되는지
- 상품과 표면의 위치·그림자 자연스러움
- 시간대/톤 프롬프트 반영

위 경쟁 물체 또는 촬영 장비가 하나라도 보이면 `product_preserved=true`여도 품질 실패로
판정합니다. 현재 자동 보존 판정은 이 배경 의미 오염을 검출하지 않으므로 사람 육안 판정을
대체하지 않습니다.
- 4·6·8 step 블라인드 선호도

fast 경로는 원본 상품을 합성하므로 `product_preserved=true`를 반환합니다. 다만 rembg가 상품 일부를 누락한 경우까지 성공으로 간주하면 안 되므로 마스크 품질은 별도 실패율로 기록합니다.

## 완료 기준

- 선정된 fast 설정의 P95가 팀이 정한 목표 이하
- OOM 0건
- 테스트 상품의 마스크 치명 오류율이 합의 기준 이하
- 4/6/8-step 중 지연시간과 블라인드 품질 기준을 함께 만족하는 설정이 선정됨
- 결과 JSON, 생성 이미지, 환경 로그를 팀 저장소 밖 검토 폴더에 먼저 보관

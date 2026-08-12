# Model Server Handoff

## 확정된 운영 설정 (2026-08-11, 서빙 담당자 실측 완료)

- 프로필: `fast_composite` / 배경 768 / 4-step / FP16-safe VAE (`madebyollin/sdxl-vae-fp16-fix`)
- 실행 명령:
```bash
uvicorn model_server.main:app --host 0.0.0.0 --port 8001 --workers 1 --env-file .env
```
- `.env` 파일은 `load_dotenv()` 코드가 없어 코드에서 자동 로드되지 않으므로, 반드시 `--env-file .env` 옵션으로 명시 전달해야 함 (export 없이 이 옵션만으로 반영 확인됨)
- L4 실측: P50 1.72s / P95 1.77s (quality_regenerate 30-step 대비 약 10배 빠름)
- VAE 비교(stock vs FP16-safe, seed=42): PSNR 51.37dB, 속도 약 10% 우위로 FP16-safe 유지 확정

## 쇼츠 TTS(MeloTTS) 연동 설정 (2026-08-12, 서빙 담당자 실측 완료)

- backend는 `app/backend/services/tts_provider.py`에서 `melo.api.TTS`를 직접 import하는 구조라, backend 프로세스 자체가 melo 패키지를 가진 인터프리터로 실행되어야 함
- backend `requirements.txt`에는 torch가 없어(GPU 불필요), model_server(CUDA venv)와 물리적으로 분리된 별도 CPU venv를 사용
- venv 위치: `~/ad-studio-runtime/backend-venv` (Python 3.11, CPU 전용)
- 설치 절차:
```bash
  python3.11 -m venv ~/ad-studio-runtime/backend-venv
  ~/ad-studio-runtime/backend-venv/bin/python -m pip install -e ".[video]"
  ~/ad-studio-runtime/backend-venv/bin/python -m pip install -r requirements-tts.txt
  ~/ad-studio-runtime/backend-venv/bin/python -m pip install -r requirements.txt
```
- MeloTTS 소스: `~/ad-studio-runtime/src/MeloTTS`, 고정 커밋 `209145371cff8fc3bd60d7be902ea69cbdb7965a`
- 한국어 모델: `~/ad-studio-runtime/models/melotts-korean/{config.json,checkpoint.pth}`
  - SHA-256은 `tts_provider.py`의 `MELOTTS_CONFIG_SHA256`/`MELOTTS_CHECKPOINT_SHA256`과 반드시 일치해야 함 (코드에서 자동 검증)
- `.env`에 아래 3개 경로 필수 (각자 로컬 `.env`에 개별 추가해야 함, git에 커밋되지 않음):
MELOTTS_SOURCE_DIR=<본인 경로>/ad-studio-runtime/src/MeloTTS
MELOTTS_CONFIG_PATH=<본인 경로>/ad-studio-runtime/models/melotts-korean/config.json
MELOTTS_CHECKPOINT_PATH=<본인 경로>/ad-studio-runtime/models/melotts-korean/checkpoint.pth
- backend 실행 명령 (반드시 backend-venv 파이썬으로 실행):
```bash
  ~/ad-studio-runtime/backend-venv/bin/python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --env-file .env
```
- model_server는 기존과 동일하게 `venv-pr15`(CUDA) 유지, 변경 없음
- 검증: `pip check` 충돌 없음, `tools/evaluate_korean_tts.py` 스모크 테스트로 WAV 7개 생성 확인, `nvidia-smi`로 GPU/VRAM 영향 없음(0MiB) 확인

## 로컬 통합 상태

- 최신 확인 원격: `main@0d07c0b` (PR #16 병합 상태)
- 작업 브랜치: `codex/model-server-optimization`
- 원격 브랜치: `Adam-1228/ad-creative-studio:codex/model-server-optimization`
- 팀 저장소 Draft PR: `codeit-part4-team2/ad-creative-studio#15`
- merge: PM 승인 전까지 수행하지 않음 (L4 실측은 2026-08-11 완료, 아래 확정 설정 섹션 참고)
- 모델 가중치 다운로드 및 NVIDIA L4 실제 추론: 수행하지 않음

2026-08-10 서빙 담당자 실험 A 보고에서 `quality_regenerate`, 1024×1024, 30-step은
NVIDIA L4 warm 10회 기준 P50 17.39초, P95 17.59초, peak VRAM 16.25GB, 실패 0건으로
측정됐습니다. 이 수치는 전달받은 외부 측정이며 fast 경로의 성능을 의미하지 않습니다.

같은 날 전달받은 fast 보고값은 4-step P50/P95 2.37/3.98초, 6-step
2.97/4.52초, 8-step 3.46/5.00초이며 peak VRAM은 모두 10.85GB였습니다.
서로 다른 상품 두 건의 동시 요청에서는 preprocess가 병렬로 완료되고 GPU generate가
직렬화됐으며 OOM은 없었다고 보고됐습니다. 이 값들은 담당자 메시지로 전달된 외부
측정이며 원본 JSON, 실행 commit, `background_size`, `output_size`는 아직 직접
대조하지 않았습니다.

## 검증 결과

- Python 3.13.13 전체 테스트: `181 passed in 27.83s`
- 전체 Python 소스 `compileall`: 통과
- `app`, `model_server`, `tests`, `tools`, `scripts` Ruff 검사: 통과
- `git diff --check`: 통과
- 변경 트리 비밀정보 패턴 검사: 발견 0건
- API import 시 Diffusers, Transformers, rembg, OpenCV 로드: 0개
- 현재 Python 3.13 환경 `pip check`: 손상 의존성 0개
- pristine-copy wheel: model_server 10개 파일, tests/experiments 포함 0개
- wheel SHA-256:
  `75922489732B93F449914D6EAE1722524AA2C4B0C3A2FB13837D0AC53A9B9063`

Python 3.12 인터프리터의 구문 컴파일은 통과했지만 해당 인터프리터에 pytest가 없어
전체 3.12 테스트는 실행하지 못했습니다. 팀 CI가 Python 3.12에서 최종 확인해야 합니다.

## 핵심 변경

1. 기본 경로를 SDXL + LCM-LoRA 4-step 배경 생성과 원본 상품 알파 합성으로 구성
2. 30-step SDXL Canny ControlNet + IP-Adapter를 품질 비교군으로 유지
3. rembg 세션, 상품 전처리, Canny, IP-Adapter 임베딩 캐시
4. GPU 추론 직렬화와 단계별 시간·peak VRAM 메타데이터
5. backend 상대 상품 URL을 절대 URL로 변환하고 모델 결과 정적 파일 서빙
6. `/health`, `/warmup`, P50/P95 벤치마크 도구 추가
7. GPU가 없을 때 기본적으로 모델 로드를 차단해 대용량 오다운로드 방지
8. 서로 다른 상품의 전처리는 병렬 실행하고 같은 상품의 중복 계산만 합치는 키별 캐시 동시성
9. backend 동일 origin 및 model server 허용 origin 검사, 이미지 redirect 차단
10. `/warmup` 구조화 실패 응답과 L4 직접 의존성 정확한 버전 고정
11. fast 경로의 SDXL 배경만 기본 768×768로 생성하고 1024×1024로 정규화한 뒤 제품 합성
12. 응답과 벤치마크 결과에 배경 크기와 최종 출력 크기를 분리 기록
13. fast와 quality 경로에 FP16-safe SDXL VAE를 명시적으로 주입
14. GPU 잠금 대기시간을 `gpu_queue_wait_sec`와 단계별 timing으로 분리 기록
15. `requirements-torch-cu132.txt`에 L4용 torch/torchvision과 CUDA 인덱스를 함께 고정
16. 같은 캐시 실패를 기다리는 스레드마다 독립된 예외 객체를 전달
17. 이미지 픽셀 상한을 EXIF 처리와 픽셀 디코딩 전에 검사

## 서빙 담당자 확인 순서

1. `nvidia-smi`에서 NVIDIA L4와 드라이버 확인
2. `requirements-torch-cu132.txt`의 CUDA용 PyTorch와 `requirements.txt`의 나머지 의존성 설치
3. `BACKEND_PUBLIC_URL`과 `MODEL_IMAGE_ALLOWED_ORIGINS`를 실제 backend origin으로 지정
4. backend를 8000, model_server를 8001에서 `--workers 1`로 한 프로세스만 실행하고 8001 접근을 backend로 제한
5. `POST /warmup` 후 `GET /health`의 `model_loaded=true` 확인
6. `USE_MOCK_GENERATION=false`로 실제 E2E 한 건 실행
7. `docs/L4_BENCHMARK_CHECKLIST.md`의 1024/768 배경, 순차·동시 요청 및 4/6/8-step 비교 측정
8. 이전 stock VAE와 현재 FP16-safe VAE의 768/4-step 동일 seed 비교 측정

## 아직 검증되지 않은 항목

- fast 보고값의 원본 JSON, 정확한 실행 commit (`background_size=768`, `output_size=1024`는 2026-08-11 실험 B 응답으로 확인 완료)
- FP16-safe VAE의 NVIDIA L4 **cold-start** latency 및 대량 반복 요청 시 OOM 여부 (warm P50/P95·peak VRAM은 2026-08-11 실측 완료, 아래 확정 설정 섹션 참고)
- SDXL·LCM-LoRA·ControlNet·IP-Adapter 가중치 다운로드와 라이선스 승인 상태
- 상품 20개 이상에 대한 rembg 치명 마스크 오류율
- 4-step 이미지의 시간대·톤 반영 및 6/8-step 대비 블라인드 선호도
- VM에서 backend의 `BACKEND_PUBLIC_URL` 접근 가능 여부
- L4 클린 환경에서 두 requirements 파일의 연속 설치와 `pip check`

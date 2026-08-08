# Model Server Handoff

## 로컬 통합 상태

- 기준 원격: `main@43511b6c5c4d9ff2d29a872416ce57591775856c`
- 작업 브랜치: `codex/model-server-optimization`
- 원격 브랜치/PR: 확인 시점에 `main` 한 개, 열린 PR 없음
- 커밋·push·merge·PR: 수행하지 않음
- 모델 가중치 다운로드 및 NVIDIA L4 실제 추론: 수행하지 않음

## 검증 결과

- Python 3.13.13 전체 테스트: `159 passed in 23.78s`
- Python 3.13/3.12 `compileall`: 통과
- `git diff --check`: 통과, unmerged path 0개
- 변경 트리 비밀정보 패턴 검사: 발견 0건
- API import 시 Diffusers, Transformers, rembg, OpenCV 로드: 0개
- 현재 Python 3.13 환경 `pip check`: 손상 의존성 0개
- pristine-copy wheel: 47 entries, app 33, model_server 10,
  tests/experiments 포함 0개
- wheel SHA-256:
  `AB80096142C20BD765BE93FD32ABE6000600B07133A8839A2E52121B823FAD26`

Python 3.12 인터프리터의 구문 컴파일은 통과했지만 해당 인터프리터에 pytest가 없어
전체 3.12 테스트는 실행하지 못했습니다. 팀 CI가 Python 3.12에서 최종 확인해야 합니다.
로컬 환경에는 ruff가 설치되어 있지 않아 별도 lint 실행은 하지 않았습니다.

## 핵심 변경

1. 기본 경로를 SDXL + LCM-LoRA 4-step 배경 생성과 원본 상품 알파 합성으로 구성
2. 30-step SDXL Canny ControlNet + IP-Adapter를 품질 비교군으로 유지
3. rembg 세션, 상품 전처리, Canny, IP-Adapter 임베딩 캐시
4. GPU 추론 직렬화와 단계별 시간·peak VRAM 메타데이터
5. backend 상대 상품 URL을 절대 URL로 변환하고 모델 결과 정적 파일 서빙
6. `/health`, `/warmup`, P50/P95 벤치마크 도구 추가
7. GPU가 없을 때 기본적으로 모델 로드를 차단해 대용량 오다운로드 방지

## 서빙 담당자 확인 순서

1. `nvidia-smi`에서 NVIDIA L4와 드라이버 확인
2. CUDA용 PyTorch와 `model_server/requirements.txt` 설치
3. backend를 8000, model_server를 8001로 실행
4. `POST /warmup` 후 `GET /health`의 `model_loaded=true` 확인
5. `USE_MOCK_GENERATION=false`로 실제 E2E 한 건 실행
6. `docs/L4_BENCHMARK_CHECKLIST.md`의 4/6/8-step 및 품질 비교군 측정

## 아직 검증되지 않은 항목

- NVIDIA L4의 실제 cold/warm latency, P50/P95, peak VRAM, OOM
- SDXL·LCM-LoRA·ControlNet·IP-Adapter 가중치 다운로드와 라이선스 승인 상태
- 상품 20개 이상에 대한 rembg 치명 마스크 오류율
- 4-step 이미지의 시간대·톤 반영 및 6/8-step 대비 블라인드 선호도
- VM에서 backend의 `BACKEND_PUBLIC_URL` 접근 가능 여부

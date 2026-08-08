# Model Server Handoff

## 로컬 통합 상태

- 기준 원격: `main@43511b6c5c4d9ff2d29a872416ce57591775856c`
- 작업 브랜치: `codex/model-server-optimization`
- 원격 브랜치: `Adam-1228/ad-creative-studio:codex/model-server-optimization`
- 팀 저장소 Draft PR: `codeit-part4-team2/ad-creative-studio#15`
- merge: PM 승인 및 L4 실측 전까지 수행하지 않음
- 모델 가중치 다운로드 및 NVIDIA L4 실제 추론: 수행하지 않음

## 검증 결과

- Python 3.13.13 전체 테스트: `169 passed in 15.02s`
- Python 3.12 `compileall`: 통과
- 변경 Python 파일 Ruff 검사: 통과
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

## 서빙 담당자 확인 순서

1. `nvidia-smi`에서 NVIDIA L4와 드라이버 확인
2. CUDA용 PyTorch와 정확히 고정된 `model_server/requirements.txt` 설치
3. `BACKEND_PUBLIC_URL`과 `MODEL_IMAGE_ALLOWED_ORIGINS`를 실제 backend origin으로 지정
4. backend를 8000, model_server를 8001로 실행하고 8001 접근을 backend로 제한
5. `POST /warmup` 후 `GET /health`의 `model_loaded=true` 확인
6. `USE_MOCK_GENERATION=false`로 실제 E2E 한 건 실행
7. `docs/L4_BENCHMARK_CHECKLIST.md`의 순차·동시 요청 및 4/6/8-step 비교 측정

## 아직 검증되지 않은 항목

- NVIDIA L4의 실제 cold/warm latency, P50/P95, peak VRAM, OOM
- SDXL·LCM-LoRA·ControlNet·IP-Adapter 가중치 다운로드와 라이선스 승인 상태
- 상품 20개 이상에 대한 rembg 치명 마스크 오류율
- 4-step 이미지의 시간대·톤 반영 및 6/8-step 대비 블라인드 선호도
- VM에서 backend의 `BACKEND_PUBLIC_URL` 접근 가능 여부

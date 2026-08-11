# 🔌 소형가전 AI 광고 콘텐츠 생성 서비스

코드잇 AI 엔지니어 10기 파트4 4팀 고급 프로젝트 — 쇼핑몰에 입점한 소형가전 판매 소상공인이
제품 사진 1장을 올리면 브랜드 톤 4종과 판매 시간대에 맞춘 광고 이미지·문구 세트를 자동 생성하는 서비스입니다.

> **기간**: 2026-08-05 ~ 08-28 (제출), 발표 08-31
> **팀**: Codeit AI 10기 Part4 Team 4

---

## 팀 구성

| 이름 | 역할 | 담당 |
|---|---|---|
| 안은남 | PM & 데이터/평가 리드 (팀장) | 서비스 기획·스코프 관리, 스프린트 운영, 데이터셋 수집·전처리·EDA, 평가 하네스, 보고서 총괄 |
| 성치용 | 생성 모델 개발 | 베이스 모델 선정·학습 파이프라인·튜닝 |
| 유수빈 | 생성 모델 개발 | 톤 4종 데이터 정의·톤별 LoRA·품질 평가 |
| 김재헌 | 추론 파이프라인 & 서빙 (인프라 오너) | ControlNet/IP-Adapter 파이프라인, 추론 최적화, GCP VM·CUDA·배포 단독 소유 |
| 박재철 | 프롬프트/텍스트 + 서비스 개발 (R4+R5) | 광고 문구·프롬프트 자동 보강, OpenAI 예산 관리, Streamlit UI/UX, FastAPI 백엔드 |

---

## 프로젝트 목표

온라인 이커머스(쿠팡/스마트스토어/알리/테무)에서 소형가전을 사입해 재판매하는 소상공인은
제품 사진 촬영·광고 이미지 제작·SNS 업로드를 매번 직접 해야 하고, 시간대·계절·행사마다
광고 이미지를 새로 만들어야 합니다.

본 프로젝트는 생성형 AI를 통해

- 제품 보존형 광고 이미지 자동 생성 (제품은 그대로, 배경·조명·연출만 교체)
- 톤 4종(감성/모던/실용/프리미엄) 동시 생성 — 사장님은 고르기만 하면 됨
- 시간대(아침/출근러시아워/오후/퇴근러시아워/저녁/심야)별 소구점·비주얼·문구 자동 전환
- 쇼핑몰 규격(썸네일 1:1, 상세배너, SNS카드 4:5) 일괄 출력

기능을 지원하는 것을 목표로 합니다.

---

## 서비스 파이프라인

```
사용자 (쇼핑몰 소형가전 판매 소상공인)
  ↓
Streamlit — 상품 업로드 → 목적/시간대 선택 → 생성 (박재철)
  ↓
FastAPI — 상태관리, Job 큐, History (박재철)
  ↓
Prompt Builder — 톤×시간대 템플릿 결합, 제품 보존 지시, 문구 생성 (박재철)
  ↓
model_server — SDXL/SD1.5 + 톤 LoRA×4 + ControlNet/IP-Adapter, 제품 보존 마스킹 (성치용·유수빈·김재헌)
  ↓
PIL 오버레이 — 한글 문구, 규격별 배치 (박재철)
  ↓
결과 (이미지 + 문구) → History 저장
```

> 이미지 생성 프롬프트는 영어(모델 성능 최적화), 광고 문구는 한국어(사용자 노출용)로 분리합니다.
> 이미지 내 한글은 모델이 그리지 않고 PIL로 오버레이합니다 — 문구만 고칠 때 이미지를 재생성하지 않아도 됩니다.

---

## 프로젝트 구조

```
ad-service-v2/
├── app/
│   ├── frontend/            # Streamlit — streamlit_app.py + pages/(Product·Generate·History)
│   ├── backend/              # FastAPI
│   │   ├── api/               # products / generations / jobs / history / usage
│   │   ├── schemas/           # Pydantic 요청/응답 스키마
│   │   └── services/          # openai_client, model_server_client, generation_service, overlay, store
│   └── prompt/                # Prompt Builder — 톤×시간대 템플릿, 문구 생성 규칙
├── model_server/              # 로컬 GPU 추론 서버 자리 (성치용·유수빈·김재헌 담당)
├── eval/                      # 평가 자산 — eval_criteria.md, metrics.py, golden_dataset/
├── data/{samples,outputs,uploads}/  # 실제 파일은 .gitignore 처리
├── notebooks/{model,data,eval}/  # 실험 노트북 (nbstripout 필터 적용, 아래 참고)
├── scripts/                   # 실행 스크립트
├── deploy/                    # GCP VM 배포 자산 (systemd 등, 김재헌 담당)
├── docs/                      # api_contract.md, prompt_spec.md, architecture.md, test_results_gate0.txt
├── tests/                     # pytest
└── .github/                   # PR/Issue 템플릿, CI(pytest 자동 실행)
```

---

## 환경 설정

### 사전 요구사항
- Python 3.11+
- GCP VM (L4 24GB) 접속 권한 — model_server 실행용 (김재헌 관리)
- OpenAI API Key — 텍스트 전용, 팀 공용 (박재철 관리, $20 경고/$25 상한)

### 설치
```bash
git clone https://github.com/{조직}/{repo명}.git
cd ad-service-v2

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

pip install -e ".[dev,frontend]"    # 개발·테스트·웹 UI 전부
# 또는
pip install -r requirements.txt

nbstripout --install --attributes .gitattributes    # 노트북 작업 시 필수 (최초 1회, venv 활성화 상태에서) — notebooks/README.md 참고
```

### 실행
```bash
cp .env.example .env            # 실제 값 채우기, 커밋 금지

# 1) 백엔드 API (Mock 모델, 실제 model_server 없이도 동작)
# --env-file .env 필수 - 없으면 .env 값이 반영 안 되고 코드 기본값만 쓰인다
# (model_server와 동일한 실행 컨벤션, load_dotenv()를 코드에 넣지 않기로 팀 협의함)
uvicorn app.backend.main:app --reload --port 8000 --env-file .env   # http://127.0.0.1:8000/docs

# 2) 프론트엔드 (다른 터미널)
streamlit run app/frontend/streamlit_app.py            # http://localhost:8501

# 또는 스크립트로 한 번에
./scripts/run_local_stack.sh

# 3) 테스트
pytest -q
```

> model_server(R2·R3) 연동 방법은 [docs/api_contract.md](docs/api_contract.md) 참고.
> Mock↔실제 모델 전환은 `app/backend/services/generation_service.py`의
> `generation_service` 한 줄만 바꾸면 됩니다.

---

## 평가 지표

| 단계 | 지표 |
|---|---|
| 1순위 | **Product Preservation** (제품 보존율) — 다른 지표보다 먼저 측정 |
| 생성 품질/속도 | 정확도와 적합도, 일관성과 안정성, 응답 속도·부하 처리 |
| 서비스 완성도 | 유저 중심 인터페이스, 제어 가능성 |

세부 측정 방법은 [eval/eval_criteria.md](eval/eval_criteria.md) 참고.

---

## 브랜치 전략

| 브랜치 | 용도 |
|---|---|
| `main` | 항상 실행 가능한 상태 유지. 직접 push 금지 |
| `develop` | 통합 브랜치 |
| `feature/<역할>-<내용>` | 예: `feature/r4r5-wizard-ui`, `feature/r3-controlnet` |

- PR 최소 1인 리뷰 (기본 리뷰어: 안은남)
- 8/22 Gate 2 이후 신규 기능 PR 금지 (기능 프리즈)
- 흐름: `feature/* → develop → main`
- PR 전 브랜치 정비, 충돌 해결 책임, branch protection 설정 등 세부 규칙은 [docs/git_workflow.md](docs/git_workflow.md) 참고

---

## 기준 커밋

`gate0-service-v0.1` 태그 — Gate 0(더미 모델 E2E 관통) 기준. 이후 실제 모델 연동 중
문제가 생기면 이 태그로 되돌릴 수 있습니다. 테스트 결과: [docs/test_results_gate0.txt](docs/test_results_gate0.txt)

---

## 오늘(Sprint 0) 완료 기준
- [x] 저장소 생성, `.gitignore`에서 `.env`/모델/업로드 이미지 차단, `.env.example` 커밋
- [x] Streamlit → FastAPI 실제 연동: 업로드→선택→생성요청→job 폴링→결과 관통 (더미 모델, 진짜 API)
- [x] `PromptRequest`/`PromptResult` 스키마 확정, 톤 4종·시간대 6종 템플릿 구조 작성
- [x] `docs/api_contract.md` 작성 (R3 model_server 계약 포함: enum, 생성단위, 성공/실패, 타임아웃)
- [x] 생성 단위를 시간대×톤으로 수정 (출력 규격은 후처리로 분리)
- [x] Mock/실제 모델 서버 교체 가능한 `generation_service.py` 인터페이스, 실패 시 job "failed" 처리
- [x] 테스트 36개 작성·통과
- [ ] 팀원 초대, 브랜치 전략 공유
- [ ] R3와 API 입력·출력 최종 합의
- [ ] 협업일지에 결정 이유·수정 가능 항목 기록

---

## 협업일지

각자 Notion에 작성 후 팀 채널에 매일 링크 공유. (링크 추가 예정)

## 보고서 PDF

(제출 전 링크 추가 예정)

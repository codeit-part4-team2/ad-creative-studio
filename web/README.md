# web — 소형가전 광고 생성기 (Next.js 프론트엔드)

Streamlit(`app/frontend/`)과 별개로 병행 개발 중인 실제 서비스용 웹 프론트엔드입니다.
Streamlit은 기능 검증용 프로토타입으로 유지하고, 이쪽이 최종 데모/서비스 화면입니다.

## 기술 스택
- Next.js 16 (App Router) + TypeScript
- Tailwind CSS v4
- shadcn/ui 스타일 컴포넌트 (CLI가 `ui.shadcn.com` 네트워크 제약으로 안 돼서 표준 소스를 직접 작성함 — 나중에 CLI 쓸 수 있는 환경이면 `npx shadcn@latest add <component>`로 그대로 대체 가능)
- TanStack Query (서버 상태/폴링)
- Pretendard + IBM Plex Mono (로컬 npm 패키지 번들, Google Fonts CDN 미사용)

## 시작하기

```bash
cd web
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE를 FastAPI 주소로
npm run dev
```

FastAPI 백엔드(`app/backend`)가 `http://localhost:8000`에서 먼저 떠 있어야 합니다.

## 디자인 시스템
`app/globals.css`에 CSS 변수로 정의:
- **컬러**: ink(배경) / porcelain(전경) / copper(accent) / sage(성공) / slate(중립)
- **타이포**: 본문 Pretendard, job_id·상태뱃지 등 "데이터"는 IBM Plex Mono
- **시그니처**: `.receipt-card`/`.receipt-divider`/`.receipt-tear` — 영수증(주문서) 모티프의 결과 카드

## 폴더 구조
```
app/
├── page.tsx              # 대시보드
├── create/page.tsx        # 광고 만들기 Wizard (Streamlit 버전과 동일 흐름)
├── result/[jobId]/page.tsx  # 생성 결과 (폴링 + 단계형 로딩 UX)
├── history/page.tsx       # 생성 이력
└── publishing/page.tsx    # YouTube 게시 (준비 중 placeholder)

components/
├── ui/            # shadcn 스타일 기본 컴포넌트
├── layout/         # SideNav
├── creative/        # ResultReceiptCard, GenerationProgress
└── providers/       # TanStack QueryProvider

lib/
├── api/            # FastAPI 클라이언트 (products/generations/history/videos)
├── types/api.ts     # 백엔드 스키마와 1:1 대응하는 타입
└── constants.ts      # 시간대/톤 라벨, 로딩 단계 정의
```

## 백엔드와의 계약
`lib/types/api.ts`가 `app/backend/schemas`의 실제 응답 형태를 그대로 옮긴 것입니다.
백엔드 스키마가 바뀌면 이 파일부터 맞추면 됩니다 — API 호출 로직은 `lib/api/`에만 있어서
페이지 컴포넌트를 건드릴 필요가 없습니다.

## 아직 안 된 것 (의도적)
- YouTube 게시(`/publishing`)는 실제 API 연동 전, placeholder만 있음
- 이미지 최적화(`next/image`)는 `unoptimized`로 켜뒀음 — FastAPI가 배포되면
  `next.config.ts`에 `images.remotePatterns`를 실제 도메인으로 설정하고 최적화 켜는 게 좋음
- 로딩 화면 임계값(`lib/constants.ts`의 `LOADING_STAGES`)은 Streamlit과 동일하게
  `quality_regenerate` 실측(P50 17.4s) 기준 — 실제 E2E 체감시간 나오면 재조정 필요

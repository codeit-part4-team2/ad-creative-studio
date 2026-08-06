# E2E Integration Checklist

담당: 박재철 — 병렬 개발 중 "통합 준비"를 미리 해두는 문서.
[x] = 이미 확인됨(자동 테스트 또는 수동 검증) · 🔴 = 실제 갭 발견, 손봐야 함 · ⏳ = R2/R3/평가팀 완료 필요

## 1. 환경
- [ ] `.env`에 `MODEL_SERVER_URL` 설정 (⏳ R3 서버 완성 후)
- [x] `USE_MOCK_GENERATION` env 토글 추가 완료 — `.env`의 `USE_MOCK_GENERATION=false`로 전환
- [x] `USE_LLM_COPY=true` 코드 반영 완료 (실제 key로 재검증 필요)
- [x] FastAPI 서버 정상 실행
- [x] Streamlit 서버 정상 실행
- [ ] 모델 서버 Health Check 성공 (⏳ R3)
- [ ] GPU 및 모델 로딩 상태 확인 (⏳ R3)

## 2. 상품 업로드
- [x] JPG 업로드 성공
- [x] PNG 업로드 성공
- [x] 허용되지 않은 확장자 거절
- [x] 최대 파일 크기 초과 거절
- [x] 업로드 이미지 정적 조회 가능
- [x] 상품 정보와 셀링포인트 저장 확인

## 3. Prompt Builder
- [x] 제품명 반영
- [x] 셀링포인트 반영
- [x] 선택한 톤 반영
- [x] 선택한 시간대 반영
- [x] 제품 보존 지시 포함
- [x] 허위 할인·효능 문구 생성 방지
- [x] 프로모션 데이터가 있을 때만 할인 문구 사용

## 4. 모델 서버 연동 (⏳ R3 완료 필요)
- [ ] 요청 이미지가 정상 전달됨
- [ ] image prompt 전달됨
- [ ] negative prompt 전달 여부 확인
- [ ] tone 전달됨
- [ ] time slot 전달됨
- [ ] 생성 결과 이미지 반환
- [ ] 타임아웃 처리
- [ ] 모델 서버 4xx/5xx 처리
- [ ] 잘못된 응답 스키마 처리
- [ ] 생성 실패 시 job 상태가 `failed`로 변경됨

## 5. 광고 문구 생성
- [ ] OpenAI 실제 호출 성공 (수동 확인은 됐음, CI엔 안 넣음 - 비용 발생)
- [x] 헤드라인 14자 제한
- [x] 서브카피 28자 제한
- [ ] 🔴 톤별 문구 차이 확인 — 규칙 기반은 다름, 실제 LLM 켰을 때 재확인 필요
- [x] 시간대별 소구점 차이 확인
- [x] API 오류 시 규칙 기반 fallback 작동
- [x] 토큰 사용량 및 비용 기록

## 6. Overlay
- [x] 헤드라인이 이미지에 삽입됨
- [x] 서브카피가 이미지에 삽입됨
- [x] 한글 폰트 정상 출력 — NanumGothic 실제 배치 완료 (`assets/fonts/`)
- [x] 긴 문구 자동 줄바꿈 — 글자 단위 자동 줄바꿈 구현 완료
- [x] 글자가 이미지 밖으로 벗어나지 않음 — 하단 정렬 기준 블록 높이 계산으로 방지
- [x] 톤별 글자 색상·위치 확인
- [ ] 원본 이미지와 overlay 결과 분리 저장 (⏳ 실제 모델 이미지 들어오면 재확인)

## 7. 규격별 출력
- [x] 썸네일 1:1 생성
- [x] SNS 카드 4:5 생성
- [x] 상세 배너 가로형 생성
- [x] 각 규격이 실제로 다른 크기의 PNG인지 확인
- [ ] 제품이 과도하게 잘리지 않는지 확인 (⏳ 실제 제품 이미지 필요)
- [x] 파일별 다운로드 성공 — `GET /api/v1/download/{job_id}` 구현 완료
- [x] 전체 ZIP 다운로드 — `GET /api/v1/download/{job_id}/all` 구현 완료

## 8. 상태 관리
- [x] `queued → processing → completed`
- [x] 진행률 증가
- [x] 현재 처리 단계 표시
- [x] 예상 시간 표시
- [x] 새로고침 후 상태 복구 (서버가 살아있는 동안은 정상)
- [x] 중복 생성 요청 방지 — 진행 중인 job 있으면 409 반환하도록 구현 완료
- [ ] 🔴 실패 후 재시도 — 명시적 재시도 흐름 없음 (새 요청은 가능)

## 9. History / Favorite
- [x] 생성 완료 후 History 저장
- [x] 상품·톤·시간대 정보 표시
- [x] 이미지 다운로드 (7번 다운로드 구현 완료와 연동)
- [x] 즐겨찾기 등록
- [x] 즐겨찾기 해제
- [x] 즐겨찾기 필터
- [ ] 🔴 재생성 기능 — History에서 바로 재생성하는 흐름 없음
- [x] 서버 재시작 후 데이터 유지 — `var/store.json` 파일 영속화 구현 완료 (data/ 밖에 저장 — data/는 정적 서빙되므로 store.json을 그 안에 두면 안 됨)

## 10. 제품 보존 (⏳ R2/R3 완료 필요)
- [ ] 제품 형태 유지
- [ ] 색상 유지
- [ ] 로고 유지
- [ ] 버튼·손잡이 등 주요 구조 유지
- [ ] 배경만 변경되었는지 확인
- [ ] 원본과 결과 비교 화면 제공

## 11. 최종 데모
- [x] 상품 1장 업로드
- [x] 시간대 선택
- [x] 톤 선택(4종 자동)
- [x] 광고 생성
- [x] AI 문구 생성 (규칙 기반, LLM 옵션 있음)
- [x] 문구 오버레이
- [x] 규격별 출력
- [x] History 저장
- [x] Favorite 등록
- [x] 다운로드 완료 (7번과 연동, 구현 완료)

## 12. 러시아워 쇼츠 (신규 — 쇼츠 담당자 연동 대기)
- [x] `result_id`를 `ToneResult`에 추가, `GET /generations/{id}` 응답에 포함
- [x] `POST /api/v1/videos`, `GET /api/v1/videos/{job_id}` — Mock으로 요청~조회 흐름 완성
- [x] `result_id → scenes` 조립 로직 (`video_generation_service.build_scenes_from_result`)
- [x] 출근/퇴근 시간대만 허용하는 검증 (그 외 400) — `time_slot`은 요청으로 안 받고
      `result_id`로 찾은 실제 결과 기준 자동 판정 (사용자가 잘못된 time_slot을 보내는
      경우를 원천 차단, 팀 리뷰 반영)
- [x] History 화면에 "🎬 러시아워 쇼츠 만들기" 버튼 + `st.video()` 결과 표시
- [x] 완료 시 History의 해당 결과에 `video_url` 반영
- [ ] ⏳ 쇼츠 담당자의 `generate_rush_hour_short(scenes, output_filename)` 완성 후
      `RushHourVideoGenerationService` 구현 + `USE_MOCK_VIDEO=false` 전환. **연동 전 반드시
      합의할 것 3가지**(팀 리뷰):
      1) 담당자 함수의 정확한 입출력 형식(파라미터명·반환값이 scenes/output_path→MP4경로
         계약과 일치하는지)
      2) `video_url`에 실제 MP4 파일이 존재하는지 (Mock 단계는 URL 문자열만 검증했음,
         최종 통합 시 실제 파일 존재 테스트 추가 필요)
      3) MoviePy·FFmpeg·한글 폰트 등 실행환경이 서비스 서버에도 설치돼 있는지
         (담당자에게 패키지 버전·설치 방법·실행 예시 요청)
- [ ] 쇼츠 job 상태 영속화(재시작 시 유지) — 지금은 인메모리만, `store.py` 패턴 적용 필요
- [ ] (참고, 지금 안 해도 됨) 실제 렌더링 연동 시 BackgroundTasks가 무거워질 수 있음 —
      MVP는 단일 요청 기준으로 충분, 다중 사용자 운영 시에만 별도 Worker/Queue 검토

---

## 다음 우선순위 (남은 🔴 — 급하진 않음, 여유 있을 때)
1. `USE_LLM_COPY=true` 실제 팀 key로 재검증, 톤별 문구 차이 확인
2. 생성 실패 시 재시도 흐름(버튼) 추가
3. History에서 바로 재생성하는 기능
4. 쇼츠(video) job 상태 영속화

# 러시아워 쇼츠 생성·내부 노출·YouTube 예약 게시 설계

- 작성일: 2026-08-08
- 기준 브랜치: `origin/main` (`43511b6`)
- 참고 구현: <https://github.com/Adam-1228/youtube-shorts-automation>
- 적용 대상: `ad-creative-studio`

## 1. 배경

서비스는 소상공인에게 제품 광고 제작을 의뢰받은 B2B 광고 업체를 가정한다. 현재 팀 저장소에는 출근·퇴근 러시아워 결과에 한해 쇼츠 생성을 요청하는 API, History 미리보기 UI, Mock 생성 서비스가 있다. 실제 MP4 렌더링, 승인 기록, 내부 영상 노출, YouTube 예약 게시 연결은 구현되지 않았다.

기존 `youtube-shorts-automation`의 MoviePy 합성 및 YouTube 업로드 구조는 참고하되, 일반 AI 콘텐츠용 Gemini 대본과 TTS는 사용하지 않는다. 광고 결과에 이미 저장된 제품 이미지·문구·셀링포인트만 사용하여 음악과 키네틱 자막 중심의 제품 쇼츠를 만든다.

## 2. 목표

1. 출근·퇴근 러시아워 광고 결과를 10~15초 세로형 MP4로 생성한다.
2. 사용자가 완성 영상을 미리 보고 명시적으로 승인하거나 반려할 수 있게 한다.
3. 승인된 영상만 해당 러시아워에 서비스 내부에서 노출한다.
4. 승인 시 선택하면 팀 테스트 채널에 비공개 업로드하고 미래 시각으로 공개 예약한다.
5. YouTube 실패가 내부 영상 노출을 취소하지 않도록 상태와 오류를 분리한다.
6. 단일 테스트 채널로 검증하되 향후 고객사별 채널 연결을 추가할 수 있는 경계를 둔다.

## 3. 비목표

- 이번 단계에서 고객사별 OAuth 계정·멀티테넌트 채널 관리를 구현하지 않는다.
- 승인 없는 완전 자동 게시를 구현하지 않는다.
- 일반 시간대 결과로 쇼츠를 만들지 않는다.
- TTS, 음성 대본, AI 음악 생성을 추가하지 않는다.
- YouTube 외 Instagram Reels, TikTok 게시를 구현하지 않는다.
- 게시 후 예약 취소·원격 영상 삭제 기능을 구현하지 않는다.
- Redis, Celery 또는 별도 영상 마이크로서비스를 도입하지 않는다.

## 4. 사용자 흐름

1. 사용자가 광고 생성 결과 중 `commute_am` 또는 `commute_pm` 결과를 선택한다.
2. History에서 **러시아워 쇼츠 만들기**를 누른다.
3. 백엔드가 영상 작업을 생성하고 실제 렌더러가 MP4를 만든다.
4. History가 렌더링 상태를 폴링하고 완료된 영상을 재생한다.
5. 사용자가 영상, 자막, 음악, 제품 보존을 확인한다.
6. 사용자가 예약 날짜·시각을 확인하고 승인하거나 반려한다.
7. 승인된 영상은 예약 시각부터 내부 러시아워 노출 후보가 된다.
8. `publish_to_youtube=true`이면 백엔드가 팀 테스트 채널에 비공개로 업로드하고 동일한 미래 시각에 공개되도록 예약한다.
9. YouTube 업로드·예약 결과는 내부 노출과 별도로 표시한다.

## 5. 아키텍처

현재 FastAPI 애플리케이션 안에 모듈형으로 구현한다. CPU 기반 영상 합성은 백엔드에서 실행하며 SDXL L4 모델 서버에 영상 렌더링 부하를 주지 않는다.

### 5.1 구성요소

- `StoryboardBuilder`
  - `result_id`로 제품, 광고 결과, 이미지, 셀링포인트를 조회한다.
  - 저장된 사실만 사용하여 결정론적 장면 목록을 만든다.
- `MusicCatalog`
  - 톤별 승인 음악을 조회하고 라이선스 manifest를 검증한다.
- `RushHourVideoRenderer`
  - Pillow로 한글 자막 이미지를 만들고 MoviePy/FFmpeg로 9:16 MP4를 합성한다.
  - 동기·CPU 작업이므로 이벤트 루프 밖에서 실행한다.
- `VideoWorkflowService`
  - 렌더링, 승인, 반려 및 상태 전이를 관리한다.
- `ExposureService`
  - 현재 KST 슬롯과 일치하는 가장 최근 승인 영상을 반환한다.
- `YouTubePublisher`
  - OAuth 인증, 재개 가능한 비공개 업로드 및 미래 `publishAt` 설정을 담당한다.
  - 인터페이스 뒤에 두어 CI에서는 fake 구현을 사용한다.

### 5.2 처리 경계

```text
광고 ToneResult
  -> StoryboardBuilder
  -> MusicCatalog
  -> RushHourVideoRenderer
  -> MP4 미리보기
  -> 사용자 승인
      -> 내부 Exposure 활성화
      -> YouTubePublisher 예약 게시(선택)
```

`POST /videos`와 `POST /videos/{id}/approve`는 긴 작업 완료를 기다리지 않고 `202`를 반환한다. 백엔드는 단일 프로세스 MVP에 맞춰 제한된 작업 실행기를 사용한다. 동시에 하나의 렌더링과 하나의 게시 작업만 수행하며, 동일 작업의 중복 실행을 잠금으로 막는다.

## 6. 데이터 모델과 영속화

기존 `var/store.json`에 `video_jobs` 컬렉션을 추가한다. 정적 파일로 노출되는 `data/`에는 상태나 OAuth 정보를 저장하지 않는다.

영상 작업은 다음 필드를 가진다.

```json
{
  "video_job_id": "video_1234abcd",
  "result_id": "res_005528a3",
  "product_id": "prd_001",
  "tone": "practical",
  "time_slot": "commute_am",
  "render_status": "completed",
  "approval_status": "approved",
  "publish_status": "scheduled",
  "video_url": "/files/videos/video_1234abcd.mp4",
  "video_sha256": "...",
  "source_fingerprint": "...",
  "music_key": "practical_upbeat_01",
  "music_warning": null,
  "silent_publish_confirmed": false,
  "activation_at": "2026-08-10T08:00:00+09:00",
  "approved_at": "2026-08-08T18:30:00+09:00",
  "youtube_video_id": "...",
  "youtube_error": null,
  "created_at": "2026-08-08T18:20:00+09:00",
  "updated_at": "2026-08-08T18:31:00+09:00"
}
```

### 6.1 상태 값

- `render_status`: `queued | processing | completed | failed`
- `approval_status`: `pending | approved | rejected`
- `publish_status`: `not_requested | pending | scheduled | failed | auth_required | needs_review | schedule_expired`

각 상태를 분리하여 YouTube 게시 실패가 렌더링 완료나 내부 승인 상태를 덮어쓰지 않게 한다.

### 6.2 무결성 필드

- `source_fingerprint`: 제품 이미지 URL, 헤드라인, 서브카피, 셀링포인트, 톤, 시간대를 정규화하여 해시한 값이다.
- `video_sha256`: 승인 대상 MP4 바이트의 SHA-256이다.
- 승인 시 두 값을 다시 계산한다. 원본이나 MP4가 바뀌면 `409 Conflict`로 승인하지 않고 재렌더링을 요구한다.
- 같은 승인 요청은 현재 상태를 그대로 반환한다. 이미 다른 시각으로 YouTube 예약된 작업을 재승인하면 `409 Conflict`를 반환한다.

### 6.3 재시작 복구

- `render_status`가 `queued` 또는 `processing`이면 `failed`로 바꾸고 재생성을 안내한다.
- `publish_status=pending`인데 `youtube_video_id`가 없으면 `needs_review`로 바꾼다. 서버가 중간에 종료된 게시를 자동 재실행하지 않아 중복 업로드를 방지한다.
- `approved`, `scheduled` 기록은 유지한다. 이번 MVP는 예약 성공까지만 자동 판정하며 실제 공개 완료 상태는 주장하지 않는다.

## 7. API 계약

### 7.1 영상 생성

`POST /api/v1/videos`

```json
{ "result_id": "res_005528a3" }
```

- `commute_am`, `commute_pm` 결과만 허용한다.
- 동일 `result_id`의 작업이 `queued` 또는 `processing`이면 `409`를 반환한다.
- 성공 응답: `202`

```json
{
  "video_job_id": "video_1234abcd",
  "render_status": "queued"
}
```

### 7.2 상태 조회

`GET /api/v1/videos/{video_job_id}`

렌더링, 승인, 게시 상태와 `video_url`, 경고, 예약 시각, `youtube_video_id`를 반환한다. 내부 예외 메시지와 OAuth 토큰은 반환하지 않는다.

### 7.3 승인

`POST /api/v1/videos/{video_job_id}/approve`

```json
{
  "activation_at": "2026-08-10T08:00:00+09:00",
  "publish_to_youtube": true,
  "allow_silent": false
}
```

- `render_status=completed`이고 실제 MP4가 존재해야 한다.
- `activation_at`은 KST 오프셋이 포함된 미래 시각이어야 하며 최소 10분의 여유가 있어야 한다.
- `commute_am`은 `08:00 <= 시각 < 09:30`, `commute_pm`은 `18:00 <= 시각 < 19:30`만 허용한다.
- UI 기본값은 같은 슬롯의 다음 시작 시각인 08:00 또는 18:00이다.
- 음악 경고가 있을 때 `allow_silent=true`를 명시하지 않으면 `409`를 반환한다.
- 승인과 내부 활성화 기록을 먼저 원자적으로 저장한다.
- YouTube 게시를 선택하면 `publish_status=pending`으로 저장하고 게시 작업을 시작한다.
- 성공 응답: `202`

### 7.4 반려

`POST /api/v1/videos/{video_job_id}/reject`

- `approval_status=pending`인 작업만 반려할 수 있다.
- 이미 YouTube에 예약된 영상의 취소는 이번 범위가 아니므로 `409`를 반환한다.
- 반려 후 새 렌더링 요청을 생성할 수 있다.

### 7.5 YouTube 연결 상태

`GET /api/v1/youtube/status`

```json
{
  "configured": true,
  "connection_id": "demo_merchant_channel",
  "token_available": true
}
```

채널의 비밀정보나 토큰 경로는 반환하지 않는다. 이번 MVP의 OAuth 초기 인증은 배포 운영자가 팀 테스트 채널로 한 번 수행한다.

### 7.6 내부 노출

기존 `GET /api/v1/exposure/{product_id}` 응답에 아래 필드를 추가한다.

```json
{
  "video": {
    "video_job_id": "video_1234abcd",
    "video_url": "/files/videos/video_1234abcd.mp4"
  }
}
```

- 현재 KST가 작업의 `time_slot`과 일치해야 한다.
- `approval_status=approved`이고 `activation_at <= now`인 가장 최근 영상만 반환한다.
- YouTube 게시 상태와 관계없이 내부 승인 조건만으로 노출한다.
- 슬롯 밖이거나 승인 영상이 없으면 `video`는 `null`이다.

## 8. 영상 구성 규칙

### 8.1 장면

기본 길이는 12.5초다.

1. 2.5초: 헤드라인과 제품 등장
2. 3.0초: 서브카피
3. 4.0초: 실제 등록된 셀링포인트 최대 2개
4. 3.0초: 제품명과 일반 CTA `지금 확인해보세요`

셀링포인트가 없으면 세 번째 장면을 생략하고 CTA를 4.5초로 늘려 총 길이를 10초로 만든다. 영상 허용 범위는 10~15초다. 할인율, 쿠폰, 효능, 마감 시각은 제품 데이터에 명시되어 있지 않으면 추가하지 않는다.

### 8.2 이미지

- 소스 우선순위: `sns_card` -> `thumbnail` -> 첫 번째 가용 이미지.
- 로컬 정적 파일 경로만 허용하고 `data/outputs` 밖으로 나가는 경로는 거부한다.
- 4:5 이미지는 비율을 유지하여 중앙 배치하고, 세로 여백은 동일 이미지를 확대한 블러 배경으로 채운다.
- 제품이 잘릴 수 있는 강제 중앙 크롭을 사용하지 않는다.
- 확대·이동 효과는 약하게 적용하고 제품 바운딩 영역을 프레임 밖으로 이동시키지 않는다.

### 8.3 자막

- Pillow와 프로젝트의 한글 폰트를 사용하여 자막을 이미지로 만든다.
- 좌우 8%, 위 10%, 아래 15%를 안전 여백으로 둔다.
- 헤드라인, 셀링포인트 핵심 단어, CTA에만 강조 색을 사용한다.
- 자막이 안전 영역을 넘으면 폰트 크기를 줄이고, 최소 크기에서도 넘으면 렌더링을 실패시킨다.

### 8.4 음악

- TTS와 `narration`은 사용하지 않는다.
- `assets/music/manifest.json`에 등록된 파일만 사용한다.
- 각 manifest 항목은 `key`, `file`, `tone`, `title`, `source_url`, `license`, `commercial_use`, `attribution_required`, `attribution_text`, `sha256`, `bpm`을 가진다.
- 초기 카탈로그는 감성·모던·실용·프리미엄용 트랙 각 1개로 구성한다.
- 내부 웹 노출과 YouTube 업로드 양쪽에 사용할 수 있는 상업적 이용 허용 근거가 있는 트랙만 등록한다.
- 음악은 영상 길이에 맞게 자르거나 반복하고 0.5초 페이드 인·아웃을 적용한다.
- FFmpeg `loudnorm`을 사용해 목표 `I=-16 LUFS`, `TP=-1.5 dB`로 정규화한다.
- 음악 파일이나 라이선스 검증이 실패하면 무음 미리보기를 만들고 `music_warning`을 저장한다.

### 8.5 출력

- 컨테이너: MP4
- 영상: H.264, 1080x1920, 30fps, `yuv420p`
- 음성: AAC. 무음 승인 영상에는 무음 AAC 트랙을 넣어 출력 형식을 일정하게 유지한다.
- 출력 경로: `data/videos/{video_job_id}.mp4`

## 9. YouTube 게시

### 9.1 인증과 구성

- OAuth 범위는 업로드에 필요한 최소 범위로 제한한다.
- 환경변수로 `YOUTUBE_CLIENT_SECRETS_FILE`, `YOUTUBE_TOKEN_FILE`, `YOUTUBE_CONNECTION_ID`를 받는다.
- 비밀 파일과 토큰은 저장소 및 정적 제공 디렉터리 밖에 둔다.
- 팀 테스트 채널 한 개만 연결한다. 데이터 모델의 `connection_id`는 향후 고객사별 연결을 위한 경계다.

### 9.2 예약 게시 요청

- `videos.insert`의 재개 가능한 업로드를 사용한다.
- `privacyStatus=private`와 미래 RFC 3339 `publishAt`을 함께 전송한다.
- 제목은 제품명과 헤드라인으로 만들고 설명에는 서브카피와 `#Shorts`를 포함한다.
- AI 생성 광고임을 고려해 `containsSyntheticMedia=true`로 전송한다.
- `selfDeclaredMadeForKids=false`를 명시한다.
- 업로드 응답의 영상 ID를 즉시 저장하고 `publish_status=scheduled`로 전환한다.

### 9.3 안전 규칙

- 과거 `publishAt`은 즉시 공개될 수 있으므로 API 호출 전 다시 검증한다.
- OAuth 오류는 `auth_required`, 네트워크·API 오류는 `failed`로 저장한다.
- 프로세스 종료로 성공 여부를 확정할 수 없으면 `needs_review`로 두고 자동 재업로드하지 않는다.
- 실제 공개 예약은 검증되지 않은 API 프로젝트의 비공개 제한에 영향을 받을 수 있으므로 팀 테스트 채널에서 별도 수동 검증한다.

## 10. 오류 처리

- 잘못된 `result_id`: `404`
- 러시아워가 아닌 결과: `400`
- 중복 렌더링, 승인 무결성 불일치, 잘못된 상태 전이: `409`
- 잘못된 예약 시각 또는 파일 경로: `422`
- 렌더링 내부 오류: 작업을 `failed`로 저장하고 외부 응답에는 일반화된 메시지만 제공한다.
- OAuth 만료: 내부 승인은 유지하고 `publish_status=auth_required`로 저장한다.
- YouTube 실패: 내부 노출은 유지하고 재시도 또는 재인증 안내를 제공한다.
- 음악 누락: 무음 미리보기와 경고를 제공하며 명시적 무음 승인이 없으면 게시하지 않는다.

## 11. 테스트 전략

### 11.1 단위 테스트

- `result_id`에서 장면과 로컬 이미지 경로를 올바르게 구성한다.
- 출근·퇴근 이외 슬롯을 거부한다.
- 등록되지 않은 할인·효능 문구를 추가하지 않는다.
- 음악 manifest 필수 필드, 파일 해시, 상업 이용 가능 플래그를 검사한다.
- KST 변환, 슬롯 범위, 10분 리드타임을 검증한다.
- 상태 전이, 중복 승인, 중복 업로드를 차단한다.
- 원본 변경과 MP4 변경을 해시로 탐지한다.

### 11.2 렌더링 통합 테스트

- 실제 MP4 파일이 존재하고 크기가 0보다 크다.
- `ffprobe` 결과가 1080x1920, H.264, AAC, 10~15초다.
- 한글 자막 렌더링과 안전 영역 계산이 성공한다.
- 4:5 원본이 강제 크롭되지 않는다.
- 음악 누락 시 무음 AAC 영상과 경고가 생성된다.

### 11.3 API 통합 테스트

- 생성 -> 상태 조회 -> 미리보기 -> 승인 -> 내부 노출 흐름을 검증한다.
- 승인 전 내부 노출과 YouTube 호출이 발생하지 않는다.
- 반려 후 새 작업을 만들 수 있다.
- 동일 승인 요청은 멱등적이고 다른 재승인은 `409`다.
- YouTube fake가 실패해도 내부 노출은 유지된다.
- 재시작 후 승인·예약 상태가 복구되고 진행 중 작업은 안전하게 정리된다.

### 11.4 외부 연동 수동 검증

1. 팀 테스트 채널 OAuth 연결 상태를 확인한다.
2. 출근·퇴근 영상 각 1개를 비공개 업로드한다.
3. 영상의 채널, 제목, 설명, 세로 비율, 음악, 자막을 확인한다.
4. 사용자 승인 후 미래 시각 예약 게시 1건을 검증한다.
5. 검증 결과와 영상 ID를 PR 체크리스트에 기록한다. 실제 공개·취소·삭제는 별도 명시적 승인 없이 수행하지 않는다.

## 12. 보안과 운영

- 업로드 이미지와 음악 파일 경로는 허용 루트 아래로 정규화하고 경로 탈출을 차단한다.
- OAuth 비밀정보와 토큰을 로그, API 응답, `store.json`에 기록하지 않는다.
- 영상 게시 로그에는 `video_job_id`, 연결 ID, 예약 시각, YouTube 영상 ID, 결과 코드만 남긴다.
- 서버는 MVP 동안 단일 worker로 실행한다. 다중 worker로 전환할 때 파일 저장소와 프로세스 내 잠금을 DB·분산 잠금으로 교체한다.
- 모든 직접 Python 의존성은 재현 가능한 정확 버전으로 고정한다.

## 13. 단계별 전달

### 단계 A: 실제 영상과 내부 노출

- 결정론적 storyboard, 음악 catalog, 실제 renderer를 구현한다.
- 영상 작업을 영속화한다.
- History 미리보기·승인·반려 UI를 구현한다.
- 승인된 영상을 러시아워 내부 노출 응답에 연결한다.

### 단계 B: YouTube 예약 게시

- Publisher 인터페이스와 fake를 구현한다.
- 단일 팀 테스트 채널 OAuth와 실제 Publisher를 연결한다.
- 승인 화면에 게시 선택과 예약 시각을 추가한다.
- 비공개 업로드와 예약 게시를 수동 검증한다.

단계 A와 B는 하나의 후속 기능 브랜치에서 연속 구현하되, 커밋을 분리하여 B의 외부 연동이 지연되어도 A를 독립 검토할 수 있게 한다.

## 14. 수용 기준

- 기존 테스트가 모두 통과한다.
- 출근·퇴근 결과로 실제 재생 가능한 9:16 MP4가 생성된다.
- 영상은 10~15초이며 제품을 자르지 않고 한글 자막이 안전 영역 안에 표시된다.
- TTS 없이 승인된 음악과 자막만 사용한다.
- 승인 전에는 내부 영상 노출과 YouTube 업로드가 일어나지 않는다.
- 승인 영상은 `activation_at` 이후 해당 러시아워에만 내부 노출된다.
- YouTube fake 기반 자동 테스트가 통과한다.
- 사용자 승인 후 팀 테스트 채널에서 비공개 업로드와 미래 예약 1건을 확인한다.
- YouTube 실패 시 내부 노출이 유지된다.
- 재시작 이후 승인·예약 기록이 유지되고 중복 업로드가 발생하지 않는다.

## 15. 브랜치와 통합 순서

이 문서는 모델 최적화 Draft PR #15와 분리된 `origin/main` 기반 브랜치에서 관리한다. 실제 구현은 PR #15의 L4 검증과 병합이 끝난 뒤 최신 `main`에서 새 기능 브랜치를 만들거나, 이 설계 브랜치를 최신 `main`으로 갱신한 후 시작한다. 모델 최적화 변경과 쇼츠 기능을 한 PR에 섞지 않는다.

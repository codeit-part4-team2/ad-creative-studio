# app/backend

FastAPI API, 영속 상태, 광고 생성 및 러시아워 쇼츠 승인 워크플로를 담당합니다.

담당: 박재철

## 러시아워 쇼츠 구성

- `services/storyboard.py`: 저장된 광고 결과만으로 10~15초 장면과 소스 지문 생성
- `services/music_catalog.py`: 상업용 라이선스·파일 경로·SHA-256 검증
- `services/video_renderer.py`: Pillow 프레임과 FFmpeg를 이용한 1080x1920 H.264/AAC 생성
- `services/video_workflow.py`: 렌더링, 무결성 검사, 승인/거절, 내부 활성화, YouTube 상태 전이
- `services/youtube_publisher.py`: 비공개 예약 업로드 경계와 재시도/오류 분류
- `api/videos.py`: 영상 생성·조회·승인·거절 API
- `api/youtube.py`: 비밀 정보를 제외한 연결 상태 API

영상 작업은 `store.VIDEO_JOBS`에 저장되고 `var/store.json`으로 원자적 영속화됩니다. 서버 재시작 중
중단된 렌더는 `failed`, 완료 여부가 불확실한 업로드는 `needs_review`로 복구합니다. 렌더링과 외부
업로드 중에는 전역 상태 잠금을 잡지 않으며, 각각 별도 실행 잠금으로 중복 작업을 막습니다.

승인되지 않은 영상은 내부 노출과 YouTube 업로드 모두 불가능합니다. YouTube 실패는 내부 승인을
취소하지 않습니다. 실제 OAuth 토큰, 음악 파일, 렌더 결과는 Git에 포함하지 않습니다.

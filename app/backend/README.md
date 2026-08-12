# app/backend

FastAPI API, 영속 상태, 광고 생성 및 러시아워 쇼츠 승인 워크플로를 담당합니다.

담당: 박재철

## 러시아워 쇼츠 구성

- `services/comic_script.py`: 상품 사실만 사용하는 4문장 무표정 AI 코믹 대본과 발음 검수 기준 생성
- `services/storyboard.py`: 저장된 광고 결과를 4장면·10~15초 스토리보드와 소스 지문으로 변환
- `services/scene_images.py`: 기존 대표 이미지 1장을 재사용하고 기존 `/infer` 계약으로 추가 이미지 2장을 순차 생성
- `services/tts_provider.py`: 고정된 MeloTTS 한국어 모델을 CPU에서 로드하고 WAV·SHA-256 생성
- `services/video_renderer.py`: 3장의 정적 이미지, 4개 TTS WAV, 밝은 자막을 1080x1920 H.264/AAC로 렌더링
- `services/video_workflow.py`: 렌더링, 발음/무결성 검사, 승인/거절, 내부 활성화, YouTube 상태 전이
- `services/youtube_publisher.py`: 비공개 예약 업로드 경계와 재시도/오류 분류
- `api/videos.py`: 영상 생성·조회·승인·거절 API
- `api/youtube.py`: 비밀 정보를 제외한 연결 상태 API

영상 작업은 `store.VIDEO_JOBS`에 저장되고 `var/store.json`으로 원자적 영속화됩니다. 서버 재시작 중
중단된 렌더는 `failed`, 완료 여부가 불확실한 업로드는 `needs_review`로 복구합니다. 렌더와 외부
게시 작업은 각각 서비스 전역 잠금으로 직렬화합니다. 따라서 동시에 들어온 두 번째 작업은 실패하거나
`pending`에 고립되지 않고 첫 번째 작업이 끝난 뒤 이어서 실행됩니다. 운영은 프로세스 1개 기준입니다.

승인되지 않은 영상은 내부 노출과 YouTube 업로드 모두 불가능합니다. YouTube 실패는 내부 승인을
취소하지 않습니다. 실제 OAuth 토큰, TTS 모델, 합성 음성, 렌더 결과는 Git에 포함하지 않습니다.

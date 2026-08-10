# 프로젝트 설정

## 러시아워 쇼츠 로컬 설정

Python 의존성을 설치합니다.

```powershell
python -m pip install -e ".[video]"
```

FFmpeg 실행 파일이 PATH에 있는지 확인합니다. 두 명령이 모두 성공해야 실제 MP4 렌더링을 실행할 수 있습니다.

```powershell
ffmpeg -version
ffprobe -version
```

기본 환경은 YouTube 업로드를 사용하지 않습니다.

```dotenv
VIDEO_DIR=data/videos
VIDEO_FONT_PATH=assets/fonts/NanumGothic-Regular.ttf
FFMPEG_BIN=ffmpeg
FFPROBE_BIN=ffprobe
VIDEO_FFMPEG_PRESET=veryfast
MUSIC_ASSET_DIR=assets/music/private
MUSIC_MANIFEST_PATH=assets/music/private/manifest.json
YOUTUBE_CONNECTION_ID=demo_merchant_channel
YOUTUBE_UPLOAD_ENABLED=false
```

실제 음악은 `assets/music/README.md`의 상업 이용 증빙과 SHA-256 규칙을 통과한 뒤
`assets/music/private`에 배치합니다. 검증된 음악이 없으면 시스템은 무음 미리보기를 만들며,
운영자가 별도 체크하지 않으면 승인할 수 없습니다.

YouTube OAuth 파일과 토큰은 저장소 및 `data/` 밖에 둡니다. 정확한 팀 테스트 채널과 계정을 확인하고,
사용자가 OAuth 실행을 명시적으로 승인한 경우에만 아래 명령을 실행합니다.

```powershell
$env:YOUTUBE_CLIENT_SECRETS_FILE="C:\secure\youtube\client_secrets.json"
$env:YOUTUBE_TOKEN_FILE="C:\secure\youtube\youtube_token.json"
python scripts/authorize_youtube.py
```

인증 후에도 기본값은 `YOUTUBE_UPLOAD_ENABLED=false`입니다. 비공개 업로드와 미래 예약 게시는 각각
별도의 승인 및 실측 확인을 거쳐야 합니다. OAuth 스크립트는 CI나 애플리케이션 시작 시 자동 실행하지 않습니다.

## GCP 모델 서버 VM

- 인스턴스: `sprint-ai-serving-vm`
- 리전/영역: `us-central1-c`
- 머신 유형: `g2-standard-4` (vCPU 4, 메모리 16GB)
- GPU: NVIDIA L4 x1
- OS: Ubuntu 22.04 LTS, NVIDIA 드라이버 595.71.05, CUDA 13.2 사전 설치

접속 순서:

1. 승인된 계정(`spai계정@codeit-sprint.kr`)으로 Google Cloud Console에 로그인합니다.
2. [sprint-ai-chunk2-02 VM 인스턴스](https://console.cloud.google.com/compute/instances?hl=ko&project=sprint-ai-chunk2-02) 화면을 엽니다.
3. `sprint-ai-serving-vm`의 SSH 버튼으로 접속합니다.
4. `nvidia-smi`를 실행해 NVIDIA L4가 표시되는지 확인합니다.

VM은 추가 생성하지 않으며 API 키와 OAuth 자료는 `.env` 또는 저장소 밖의 비밀 경로에만 둡니다.

가상환경은 프로젝트 안이 아니라 `~/serving/venv`에 있습니다.

```bash
source ~/serving/venv/bin/activate
cd ~/ad-creative-studio
```

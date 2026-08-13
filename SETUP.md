# 프로젝트 설정

## 러시아워 코믹 TTS 쇼츠

쇼츠 런타임은 Python 3.12를 기준으로 검증했습니다. 기본·영상 의존성과 CPU TTS 의존성을 분리해 설치합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[video]"
python -m pip install -r requirements-tts.txt
python -m pip check
```

FFmpeg와 ffprobe가 모두 PATH에 있어야 실제 MP4 렌더링과 미디어 검증을 수행할 수 있습니다.

```powershell
ffmpeg -version
ffprobe -version
```

### 고정 MeloTTS 소스와 한국어 모델

서비스는 시작하거나 합성하는 동안 모델을 자동 다운로드하지 않습니다. 저장소 밖에 아래 리비전의
MeloTTS 소스와 모델을 준비하고, 파일 SHA-256을 확인한 뒤 절대 경로를 환경 변수로 전달합니다.

- MeloTTS 소스 커밋: `209145371cff8fc3bd60d7be902ea69cbdb7965a`
- 한국어 모델 리비전: `0207e5adfc90129a51b6b03d89be6d84360ed323`
- `config.json` SHA-256: `74543376976dfadde45ba34336fa79c7e95509f43a7c2e701b22c0f71fd7695c`
- `checkpoint.pth` SHA-256: `48e3ff3fd0b5348e095f0468e60ae727507564100f58142ef3a922ead6e0a4d0`

```powershell
git clone https://github.com/myshell-ai/MeloTTS.git C:\models\MeloTTS
git -C C:\models\MeloTTS checkout 209145371cff8fc3bd60d7be902ea69cbdb7965a
git -C C:\models\MeloTTS rev-parse HEAD

$env:MELOTTS_SOURCE_DIR="C:\models\MeloTTS"
$env:MELOTTS_CONFIG_PATH="C:\models\MeloTTS-KR\config.json"
$env:MELOTTS_CHECKPOINT_PATH="C:\models\MeloTTS-KR\checkpoint.pth"
Get-FileHash $env:MELOTTS_CONFIG_PATH -Algorithm SHA256
Get-FileHash $env:MELOTTS_CHECKPOINT_PATH -Algorithm SHA256
```

`tts_provider.py`도 같은 해시를 다시 확인한 후에만 체크포인트를 로드합니다. TTS는 CPU에서 실행되며
L4 모델 서버의 VRAM을 사용하지 않습니다. 실제 배포 승인 전에는 자동 ASR 결과만으로 끝내지 말고,
상품명·숫자·시간·단위·영문 약어·받침·AI 자기인식 문장을 한국어 화자가 직접 청취해야 합니다.

### 애플리케이션 환경

```dotenv
MODEL_SERVER_URL=http://localhost:8001
VIDEO_DIR=data/videos
VIDEO_WORK_DIR=var/video-work
VIDEO_FONT_PATH=assets/fonts/NanumGothic-Regular.ttf
FFMPEG_BIN=ffmpeg
FFPROBE_BIN=ffprobe
VIDEO_FFMPEG_PRESET=veryfast
MELOTTS_SOURCE_DIR=C:\models\MeloTTS
MELOTTS_CONFIG_PATH=C:\models\MeloTTS-KR\config.json
MELOTTS_CHECKPOINT_PATH=C:\models\MeloTTS-KR\checkpoint.pth
YOUTUBE_CONNECTION_ID=demo_merchant_channel
YOUTUBE_UPLOAD_ENABLED=false
```

애플리케이션은 `.env`를 암묵적으로 읽지 않습니다. 로컬 실행 시 아래처럼 명시적으로 전달합니다.

```powershell
uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --env-file .env
```

대표 광고 이미지 1장은 재사용하고 추가 장면 2장은 기존 모델 서버 `/infer` 계약으로 순차 생성합니다.
렌더와 YouTube 게시 큐는 서비스 전역에서 각각 직렬화하므로 운영 프로세스는 1개로 실행합니다.

### YouTube 연결

OAuth 파일과 토큰은 저장소 및 `data/` 밖에 둡니다. 정확한 팀 테스트 채널과 계정을 확인하고 사용자가
OAuth 실행을 명시적으로 승인한 경우에만 아래 명령을 실행합니다.

```powershell
$env:YOUTUBE_CLIENT_SECRETS_FILE="C:\secure\youtube\client_secrets.json"
$env:YOUTUBE_TOKEN_FILE="C:\secure\youtube\youtube_token.json"
python scripts/authorize_youtube.py
```

인증 후에도 기본값은 `YOUTUBE_UPLOAD_ENABLED=false`입니다. 비공개 업로드와 미래 예약 게시는 각각
별도 승인과 실측 확인을 거쳐야 하며, OAuth 스크립트는 CI나 애플리케이션 시작 시 자동 실행하지 않습니다.

## GCP 모델 서버 VM

- 인스턴스: `sprint-ai-serving-vm`
- 리전/영역: `us-central1-c`
- 머신 유형: `g2-standard-4` (vCPU 4, 메모리 16GB)
- GPU: NVIDIA L4 x1
- OS: Ubuntu 22.04 LTS, NVIDIA 드라이버 595.71.05, CUDA 13.2 사전 설치

접속 순서:

1. 승인된 Codeit Sprint 계정으로 Google Cloud Console에 로그인합니다.
2. [sprint-ai-chunk2-02 VM 인스턴스](https://console.cloud.google.com/compute/instances?hl=ko&project=sprint-ai-chunk2-02) 화면을 엽니다.
3. `sprint-ai-serving-vm`의 SSH 버튼으로 접속합니다.
4. `nvidia-smi`를 실행해 NVIDIA L4가 표시되는지 확인합니다.

VM은 추가 생성하지 않으며 API 키와 OAuth 자료는 `.env` 또는 저장소 밖의 비밀 경로에만 둡니다.
가상환경은 프로젝트 안이 아니라 `~/serving/venv`에 있습니다.

```bash
source ~/serving/venv/bin/activate
cd ~/ad-creative-studio
```

### VM 백엔드용 CPU TTS 격리 환경

모델 서버의 `~/serving/venv`에는 CUDA용 `torch 2.12.1+cu132`가 설치되어 있습니다.
MeloTTS는 CPU용 `torch 2.5.1`, `numpy 1.26.4`를 사용하므로 같은 가상환경에 설치하면 안 됩니다.
아래처럼 백엔드/TTS 전용 가상환경을 별도로 사용합니다. 전체 설치에는 약 3.4GB의 추가 다운로드와
그보다 넉넉한 여유 디스크가 필요하므로, 먼저 읽기 전용 점검을 하고 운영 담당자 승인을 받은 뒤 설치합니다.

```bash
df -h "$HOME"
python3.11 --version
ffmpeg -version
ffprobe -version
pgrep -af "uvicorn model_server.main:app"
```

승인 후 저장소 루트에서 다음 순서로 준비합니다. 소스와 모델은 Git 저장소 밖
`$HOME/ad-studio-runtime`에 두며 서비스 실행 중에는 어떤 파일도 자동 다운로드하지 않습니다.

```bash
TTS_RUNTIME_ROOT="$HOME/ad-studio-runtime"
mkdir -p "$TTS_RUNTIME_ROOT/src" "$TTS_RUNTIME_ROOT/models/melotts-korean"

python3.11 -m venv "$TTS_RUNTIME_ROOT/backend-venv"
"$TTS_RUNTIME_ROOT/backend-venv/bin/python" -m pip install --upgrade pip
"$TTS_RUNTIME_ROOT/backend-venv/bin/python" -m pip install -e ".[video]"
"$TTS_RUNTIME_ROOT/backend-venv/bin/python" -m pip install -r requirements-tts.txt
"$TTS_RUNTIME_ROOT/backend-venv/bin/python" -m pip check

git clone https://github.com/myshell-ai/MeloTTS.git "$TTS_RUNTIME_ROOT/src/MeloTTS"
git -C "$TTS_RUNTIME_ROOT/src/MeloTTS" checkout 209145371cff8fc3bd60d7be902ea69cbdb7965a
git -C "$TTS_RUNTIME_ROOT/src/MeloTTS" rev-parse HEAD

curl --fail --location \
  "https://huggingface.co/myshell-ai/MeloTTS-Korean/resolve/0207e5adfc90129a51b6b03d89be6d84360ed323/config.json" \
  --output "$TTS_RUNTIME_ROOT/models/melotts-korean/config.json"
curl --fail --location \
  "https://huggingface.co/myshell-ai/MeloTTS-Korean/resolve/0207e5adfc90129a51b6b03d89be6d84360ed323/checkpoint.pth" \
  --output "$TTS_RUNTIME_ROOT/models/melotts-korean/checkpoint.pth"

sha256sum "$TTS_RUNTIME_ROOT/models/melotts-korean/config.json"
sha256sum "$TTS_RUNTIME_ROOT/models/melotts-korean/checkpoint.pth"
```

출력 해시는 각각 아래 값과 정확히 일치해야 합니다.

- `config.json`: `74543376976dfadde45ba34336fa79c7e95509f43a7c2e701b22c0f71fd7695c`
- `checkpoint.pth`: `48e3ff3fd0b5348e095f0468e60ae727507564100f58142ef3a922ead6e0a4d0`

`deploy/backend.env.example`을 `$TTS_RUNTIME_ROOT/backend.env`로 복사한 다음 `REPLACE_*` 값을
VM의 실제 절대 경로로 바꾸고 `chmod 600`을 적용합니다. 그 뒤 7문장 실제 WAV를 생성해
런타임과 발음을 함께 점검합니다.

```bash
set -a
source "$TTS_RUNTIME_ROOT/backend.env"
set +a

"$TTS_RUNTIME_ROOT/backend-venv/bin/python" tools/evaluate_korean_tts.py \
  --output-dir "$TTS_RUNTIME_ROOT/tts-review" \
  --config "$MELOTTS_CONFIG_PATH" \
  --checkpoint "$MELOTTS_CHECKPOINT_PATH"
```

`results.json` 생성만으로 발음 승인을 대신하지 않습니다. UI/UX 담당자가 7개 WAV와 실제 쇼츠를
직접 듣고 상품명·숫자·시간·단위·영문 혼용·받침 연음·AI 자기인식 문장의 발음을 확인해야 합니다.
운영 프로세스는 `deploy/ad-service-api.service.example`을 VM 절대 경로에 맞게 복사해 사용하며,
파일 저장소와 프로세스 내 락 구조 때문에 백엔드도 `--workers 1`로 실행합니다.

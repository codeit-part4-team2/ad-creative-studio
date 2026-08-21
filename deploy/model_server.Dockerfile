# deploy/model_server.Dockerfile
# 빌드는 repo 루트에서: docker build -f deploy/model_server.Dockerfile -t model_server .
#
# 베이스를 nvidia/cuda가 아니라 python:3.11-slim으로 씀 — VM에 이미 NVIDIA 드라이버(595.71)가
# 있고 nvidia-container-toolkit이 컨테이너에 드라이버를 연결해주므로, OS 레이어에 CUDA 툴킷을
# 따로 깔 필요가 없음. torch(cu132) pip 패키지가 필요한 CUDA 런타임 라이브러리
# (nvidia-cudnn-cu13, nvidia-cublas-cu13 등)를 자체적으로 pip 의존성에 포함하고 있어서,
# nvidia/cuda 베이스와 병행하면 같은 라이브러리가 두 번 깔리는 중복이 생겼었음.
FROM python:3.11-slim

WORKDIR /app

# torch는 cu132 전용 인덱스에서 먼저 설치 (버전 고정: torch==2.12.1, torchvision==0.27.1)
COPY model_server/requirements-torch-cu132.txt ./model_server/requirements-torch-cu132.txt
RUN python3.11 -m pip install --no-cache-dir -r model_server/requirements-torch-cu132.txt

# 나머지 의존성(fastapi, diffusers 등)
COPY model_server/requirements.txt ./model_server/requirements.txt
RUN python3.11 -m pip install --no-cache-dir -r model_server/requirements.txt

# deploy/ (queue_manager.py 등)
COPY deploy/ ./deploy/
COPY model_server/ ./model_server/
COPY app/ ./app/

ENV PYTHONUNBUFFERED=1
EXPOSE 8001

# workers=1 고정 — InferenceEngine의 threading.Lock GPU 직렬화 전제와 일치
CMD ["python3.11", "-m", "uvicorn", "model_server.main:app", \
     "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
# deploy/backend.Dockerfile
# 빌드는 repo 루트에서: docker build -f deploy/backend.Dockerfile -t backend .
FROM python:3.12-slim

# TTS 라이브러리가 ffmpeg 등을 요구할 수 있어 포함 (불필요하면 삭제)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 호스트 spai1024 계정과 UID/GID 맞추기
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} appuser && \
    useradd -u ${UID} -g ${GID} -m -s /bin/bash appuser

WORKDIR /app

# 루트의 requirements.txt / requirements-tts.txt 사용
COPY requirements.txt ./requirements.txt
COPY requirements-tts.txt ./requirements-tts.txt
RUN pip install --no-cache-dir -r requirements.txt -r requirements-tts.txt

COPY app/ ./app/
COPY assets/ ./assets

RUN chown -R appuser:appuser /app

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

USER appuser

CMD ["uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
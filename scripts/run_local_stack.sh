#!/usr/bin/env bash
# 로컬에서 FastAPI + Streamlit 동시 기동 (개발 편의용)
set -e

trap 'kill 0' EXIT

uvicorn app.backend.main:app --reload --port 8000 --env-file .env &
sleep 1
streamlit run app/frontend/streamlit_app.py

wait

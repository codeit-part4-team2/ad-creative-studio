# deploy/

담당: 김재헌

<!-- systemd 유닛, VM 환경 스냅샷, 배포 방법 등은 담당자가 채워주세요 -->

GCP VM 상시 배포 자산 (systemd 유닛, 환경 스냅샷 등). 인프라 단독 소유 원칙에 따라 **김재헌(R3)** 담당.

예정 구조 (참고용, 이전 프로젝트 사례):
```
deploy/
├── systemd/
│   ├── ad-service-api.service
│   └── ad-service-frontend.service
└── env_snapshot.txt   # VM에서 실제 동작 확인된 패키지 버전 스냅샷
```

도커 도입 여부는 8/24 재검토 예정 (12 미확정 항목 5번).

## ⚠️ .env 로딩 주의 (systemd 유닛 작성 시 필수 확인)

backend/model_server 둘 다 `.env` 값은 `uvicorn --env-file .env` 플래그로만
반영됩니다 (`load_dotenv()`를 코드에 넣지 않기로 팀 협의 — PR #18 참고). systemd
유닛의 `ExecStart`에 이 플래그를 빠뜨리면 `.env`를 아무리 고쳐도 조용히 무시되고
코드 기본값만 쓰이는 버그가 재발합니다. `ad-service-api.service` 작성 시 반드시
`--env-file /경로/.env`를 포함해주세요.

systemd에서는 `deploy/ad-service-api.service.example`처럼 `EnvironmentFile=`로 모든 값을 프로세스
환경에 직접 넣는 방식도 사용할 수 있습니다. `EnvironmentFile=`을 사용하면 `--env-file`을 중복으로
붙이지 않습니다. 두 방식 중 하나는 반드시 있어야 하며, VM에서는 실제 프로세스 환경으로
`MELOTTS_*`, `MODEL_SERVER_URL`, `VIDEO_*` 반영 여부를 확인합니다.

쇼츠 백엔드/TTS는 GPU 모델 서버의 `~/serving/venv`와 분리한 CPU 전용 가상환경을 사용합니다.
설치·해시·7문장 발음 스모크 순서는 `SETUP.md`의 “VM 백엔드용 CPU TTS 격리 환경”을 따릅니다.

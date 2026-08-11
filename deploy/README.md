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
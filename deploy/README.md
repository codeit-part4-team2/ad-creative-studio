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

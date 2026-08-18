# 광고 비율 프리셋 팀 인계

## 확정 업무 순서

1. 성치용 + Codex: 모델·백엔드 API와 네이티브 비율 생성 코드를 PR 브랜치로 전달
2. 김재헌A: 해당 브랜치를 VM에 반영하고 L4 성능·VRAM·출력 크기 검증
3. 박재철: 확정된 API를 이용해 최대 2개 선택 UI와 결과 미리보기 연결
4. 유수빈: 네 비율의 크롭·구도·가독성·제품 보존 디자인 검수
5. 팀장: 통합 결과 피드백과 수정·머지 판단

각 단계의 완료는 다음 담당자의 확인을 대신하지 않는다.

## 김재헌A 서버 인계

`POST /infer`에 다음 필드가 추가된다.

```json
{
  "output_format": "sns_card"
}
```

허용값과 기본 환경변수 기준 fast profile 크기는 다음과 같다. `FAST_BACKGROUND_SIZE`와
`IMAGE_SIZE`를 바꾸면 각 프리셋은 비율을 유지하며 8픽셀 그리드로 함께 조정된다.

| key | 비율 | SDXL 배경 | 제품 합성 출력 |
|---|---:|---:|---:|
| `thumbnail` | 1:1 | 768x768 | 1024x1024 |
| `sns_card` | 4:5 | 672x840 | 896x1120 |
| `story_vertical` | 9:16 | 576x1024 | 720x1280 |
| `wide_banner` | 16:9 | 1024x576 | 1280x720 |

필드를 생략한 기존 쇼츠 장면 호출은 `thumbnail`로 동작한다. 응답의 실제 크기는
`background_width`, `background_height`, `output_width`, `output_height`로 확인한다.
정사각형 호환 필드인 `background_size`와 `output_size`는 비정사각형에서 `null`이다.

L4 측정 항목은 `docs/L4_BENCHMARK_CHECKLIST.md`의 "네이티브 광고 비율 인수 테스트"를
따른다. 특히 두 비율 요청은 GPU에서 순차 실행되고 동일 제품의 두 번째 호출이
세그멘테이션 캐시를 재사용해야 한다.

## 박재철 UI 인계

생성 요청의 `output_formats`에 서로 다른 프리셋을 1개 또는 2개 보낸다. 생략 시
기존 다운로드와 러시아워 쇼츠를 함께 유지하도록 `["thumbnail", "story_vertical"]`이다.

```json
{
  "product_id": "prd_001",
  "time_slots": ["commute_pm"],
  "output_formats": ["sns_card", "story_vertical"]
}
```

UI 요구사항:

- `정사각형 1:1`을 기본 선택한다.
- 두 개를 선택하면 나머지 체크박스를 비활성화하고 최대 2개 안내를 표시한다.
- 생성량을 `톤 수 x 시간대 수 x 비율 수`로 표시한다.
- 결과 이미지는 정사각형 컨테이너로 강제 크롭하지 않고 실제 비율로 표시한다.
- 결과의 `images` 키별 탭과 다운로드 버튼을 제공한다.
- 러시아워 쇼츠 버튼은 `story_vertical`의 `source_image_url`이 있을 때만 활성화한다.
- 과거 History의 `detail_banner`는 계속 표시·다운로드하되 새 생성 선택지에는 넣지 않는다.

우선 확인 파일:

- `web/app/create/page.tsx`
- `web/lib/api/generations.ts`
- `web/lib/types/api.ts`
- `web/components/creative/result-card.tsx`
- 레거시 Streamlit 데모를 계속 사용한다면 `app/frontend/pages/5_Create_Ad_NEW.py`

## 유수빈 디자인 체크

각 비율에서 다음 항목을 실제 생성 이미지로 확인한다.

- 제품이 잘리거나 가로·세로로 늘어나지 않는다.
- 흰 레터박스가 없다.
- 카피가 제품과 겹치거나 화면 밖으로 나가지 않는다.
- 제품보다 큰 시계·조명 장비·경쟁 제품·대형 원형 소품이 배경 중심을 차지하지 않는다.
- 9:16은 쇼츠 안전 영역에서 제품과 자막이 함께 읽힌다.

## 현재 확인 경계

로컬 테스트는 API 계약, 정확한 크기, 순차 호출, 캐시 재사용, 무여백 오버레이를
검증한다. L4 latency/VRAM, 실제 UI 동작, 최종 이미지 디자인은 각 담당자의 외부
검증 전까지 완료로 표시하지 않는다.

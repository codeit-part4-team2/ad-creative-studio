import type { TimeSlot, Tone } from "@/lib/types/api";

export const TIME_SLOT_OPTIONS: { value: TimeSlot; label: string; desc: string }[] = [
  { value: "morning", label: "☀ 아침", desc: "여유·준비" },
  { value: "commute_am", label: "🚇 출근 러시아워", desc: "즉시결정·짧은 관여" },
  { value: "afternoon", label: "🏢 오후", desc: "비교·정보탐색" },
  { value: "commute_pm", label: "🚇 퇴근 러시아워", desc: "즉시결정·보상심리" },
  { value: "evening", label: "🌇 저녁", desc: "여유·라이프스타일" },
  { value: "late_night", label: "🌙 심야", desc: "긴급성·한정" },
];

export const TONE_LABEL: Record<Tone, string> = {
  emotional: "감성",
  modern: "모던",
  practical: "실용",
  premium: "프리미엄",
};

// 다운로드 버튼에 API 값(thumbnail 등)을 그대로 노출하면 사용자가 뭘 받는 건지
// 알기 어렵다는 디자인 피드백 반영 - 화면 표시용 한글 라벨만 매핑, API 요청/응답
// 값 자체는 절대 안 바꾼다.
export const FORMAT_LABEL: Record<string, string> = {
  thumbnail: "정사각형 (1:1)",
  sns_card: "SNS 피드 (4:5)",
  story_vertical: "쇼츠·스토리 (9:16)",
  wide_banner: "웹 배너 (16:9)",

  // Legacy History 호환용
  detail_banner: "상세페이지용",
};

export const OUTPUT_FORMAT_OPTIONS = [
  {
    value: "thumbnail",
    label: "정사각형",
    ratio: "1:1",
  },
  {
    value: "sns_card",
    label: "SNS 피드",
    ratio: "4:5",
  },
  {
    value: "story_vertical",
    label: "쇼츠·스토리",
    ratio: "9:16",
  },
  {
    value: "wide_banner",
    label: "웹 배너",
    ratio: "16:9",
  },
] as const;

export const MAX_OUTPUT_FORMATS = 2;

export const MAX_TIME_SLOTS = 3;

export const RUSH_HOUR_SLOTS: TimeSlot[] = ["commute_am", "commute_pm"];

// Streamlit Wizard와 동일한 로딩 단계 - 실제 backend stage가 아직 없어 경과시간 기준.
// 완료/실패 판정은 반드시 job.status로 하고, 이 목록은 화면 표시용 정성적 신호만 준다.
export const LOADING_STAGES: { atSeconds: number; label: string; subtext?: string }[] = [
  { atSeconds: 0, label: "상품 정보를 확인했어요" },
  { atSeconds: 2, label: "시간대에 맞는 광고 콘셉트를 구성했어요" },
  { atSeconds: 5, label: "제품이 돋보이는 배경을 만들고 있어요", subtext: "좋은 상태로 제품을 포장하고 있습니다 :)" },
  { atSeconds: 12, label: "광고 문구를 자연스럽게 조합하고 있어요" },
  { atSeconds: 15, label: "거의 다 됐어요 - 최종 결과를 정리하고 있어요" },
];

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

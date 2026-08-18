import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// 결과/이력 화면에서 job_id 대신 보여줄 "생성 일시" 포맷 - 두 파일에 중복돼
// 있던 걸 하나로 뽑음 (PR 리뷰에서 지적됨).
export function formatCreatedAt(unixSeconds: number): string {
  return new Date(unixSeconds * 1000).toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// 헤드라인이 보통 "[톤] 제품명" 형태라, 대괄호 톤 태그만 떼면 제품명에 가까운
// 사람이 읽을 수 있는 라벨이 된다. 마찬가지로 두 파일에 중복돼 있던 걸 하나로 뽑음.
export function stripToneTag(headline: string): string {
  return headline.replace(/^\[[^\]]+\]\s*/, "");
}
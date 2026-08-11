"use client";

import { useCallback, useState } from "react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { createVideo, getVideoStatus } from "@/lib/api/videos";

const POLL_INTERVAL_MS = 2000;
const MAX_POLLS = 60; // 최대 2분 - 그 이상 걸리면 폴링 멈추고 마지막 상태로 갱신만 함

/**
 * "4초 기다리면 끝났겠지" 추측 대신, 실제 video job 상태(getVideoStatus)를
 * completed/failed가 될 때까지 폴링한다. 로딩 상태는 지금 만들고 있는 result_id
 * 하나만 기억해서, 같은 화면의 다른 결과 카드까지 같이 비활성화되지 않게 한다
 * (result_card.tsx가 shortsMutation.isPending을 카드 전체가 공유 구독하던 문제).
 */
export function useShortsCreation(invalidateKey: QueryKey) {
  const queryClient = useQueryClient();
  const [pendingResultId, setPendingResultId] = useState<string | null>(null);

  const createShorts = useCallback(
    async (resultId: string) => {
      setPendingResultId(resultId);
      try {
        const { video_job_id } = await createVideo(resultId);
        for (let i = 0; i < MAX_POLLS; i++) {
          await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
          const status = await getVideoStatus(video_job_id);
          if (status.status === "completed" || status.status === "failed") break;
        }
      } finally {
        setPendingResultId(null);
        queryClient.invalidateQueries({ queryKey: invalidateKey });
      }
    },
    [queryClient, invalidateKey]
  );

  const isCreatingFor = useCallback(
    (resultId: string) => pendingResultId === resultId,
    [pendingResultId]
  );

  return { createShorts, isCreatingFor };
}

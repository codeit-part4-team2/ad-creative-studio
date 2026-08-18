"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getJobStatus, getGenerationResult } from "@/lib/api/generations";
import { getHistory } from "@/lib/api/history";
import { useShortsCreation } from "@/lib/hooks/use-shorts-creation";
import { formatCreatedAt, stripToneTag } from "@/lib/utils";
import { GenerationProgress } from "@/components/creative/generation-progress";
import { ResultReceiptCard } from "@/components/creative/result-card";
import { StepProgress } from "@/components/creative/step-progress";
import { Button } from "@/components/ui/button";
import { RequireAuth } from "@/components/auth/require-auth";

function ResultContent({ jobId }: { jobId: string }) {
  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJobStatus(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 2000;
    },
  });

  const resultQuery = useQuery({
    queryKey: ["generation-result", jobId],
    queryFn: () => getGenerationResult(jobId),
    enabled: jobQuery.data?.status === "completed",
  });

  // job_id 같은 내부 식별자를 사용자 화면에 그대로 보여줄 이유가 없다는 디자인
  // 피드백 반영 - History에서 이 job의 created_at을 찾아 생성 일시로 대체 표시한다
  // (job_id 자체는 데이터에서 지우지 않고 화면에만 안 보이게 한다).
    const done = jobQuery.data?.status === "completed";

  // job이 완료돼야 백엔드가 History에 이 job을 추가한다(app/backend/api/generations.py) -
  // 완료 전에 미리 불러오면 아직 없어서 "생성 일시"가 영영 안 뜨는 레이스 컨디션이
  // 있었다(PR 리뷰에서 지적됨). done이 되고 나서만 조회하도록 수정.
  const historyQuery = useQuery({
    queryKey: ["history", false],
    queryFn: () => getHistory(false),
    enabled: done,
  });
  const createdAt = historyQuery.data?.find((h) => h.job_id === jobId)?.created_at;
  const createdAtLabel = createdAt ? formatCreatedAt(createdAt) : null;
  // 헤드라인이 보통 "[톤] 제품명" 형태라, 대괄호 톤 태그만 떼면 제품명에 가까운
  // 사람이 읽을 수 있는 라벨이 된다 (백엔드에 product_name 필드가 따로 없어서
  // 이 방식으로 대체 - 별도 API 추가 없이 화면 표시만 바꾸는 최소 변경).
  const productLikeLabel = resultQuery.data?.results[0]?.headline
    ? stripToneTag(resultQuery.data.results[0].headline)
    : undefined;

  const { createShorts, isCreatingFor } = useShortsCreation(["generation-result", jobId]);

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <StepProgress currentIndex={done ? 4 : 3} />

      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">GENERATED CREATIVE</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {productLikeLabel || "Choose your favorite variation."}
            {createdAtLabel ? ` · ${createdAtLabel} 생성` : ""}
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href="/create">새 광고 만들기</Link>
        </Button>
      </div>

      {jobQuery.data?.status === "failed" && (
        <div className="creative-card p-6 text-destructive">
          생성 실패: {jobQuery.data.error_message ?? "알 수 없는 오류"}
        </div>
      )}

      {jobQuery.data?.status !== "completed" && jobQuery.data?.status !== "failed" && (
        <GenerationProgress job={jobQuery.data} />
      )}

      {done && resultQuery.data && (
        <div className="grid gap-4 md:grid-cols-2">
          {resultQuery.data.results.map((r) => (
            <ResultReceiptCard
              key={r.result_id}
              result={r}
              jobId={jobId}
              onCreateShorts={createShorts}
              isCreatingShorts={isCreatingFor(r.result_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ResultPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  return (
    <RequireAuth>
      <ResultContent jobId={jobId} />
    </RequireAuth>
  );
}

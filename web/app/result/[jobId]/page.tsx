"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getJobStatus, getGenerationResult } from "@/lib/api/generations";
import { useShortsCreation } from "@/lib/hooks/use-shorts-creation";
import { GenerationProgress } from "@/components/creative/generation-progress";
import { ResultReceiptCard } from "@/components/creative/result-card";
import { Button } from "@/components/ui/button";

export default function ResultPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);

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

  const { createShorts, isCreatingFor } = useShortsCreation(["generation-result", jobId]);

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-8 py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">④ 결과</h1>
          <p className="mt-1 font-mono text-xs text-muted-foreground">job_id: {jobId}</p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href="/create">🔄 새 광고 만들기</Link>
        </Button>
      </div>

      {jobQuery.data?.status === "failed" && (
        <div className="receipt-card p-6 text-destructive">
          생성 실패: {jobQuery.data.error_message ?? "알 수 없는 오류"}
        </div>
      )}

      {jobQuery.data?.status !== "completed" && jobQuery.data?.status !== "failed" && (
        <GenerationProgress job={jobQuery.data} />
      )}

      {jobQuery.data?.status === "completed" && resultQuery.data && (
        <div className="space-y-4">
          <p className="font-medium text-success">광고가 완성됐어요 🎉</p>
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
        </div>
      )}
    </div>
  );
}

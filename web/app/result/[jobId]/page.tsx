"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getJobStatus, getGenerationResult } from "@/lib/api/generations";
import { useShortsCreation } from "@/lib/hooks/use-shorts-creation";
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

  const { createShorts, isCreatingFor } = useShortsCreation(["generation-result", jobId]);
  const done = jobQuery.data?.status === "completed";

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <StepProgress currentIndex={done ? 4 : 3} />

      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">GENERATED CREATIVE</h1>
          <p className="mt-1 text-sm text-muted-foreground">Choose your favorite variation.</p>
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

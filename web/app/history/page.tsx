"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getHistory, toggleFavorite, downloadAllUrl } from "@/lib/api/history";
import { resolveAssetUrl } from "@/lib/api/client";
import { useShortsCreation } from "@/lib/hooks/use-shorts-creation";
import { ResultReceiptCard } from "@/components/creative/result-card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Star, Download } from "lucide-react";
import { RequireAuth } from "@/components/auth/require-auth";

function HistoryContent() {
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const queryClient = useQueryClient();

  const historyQuery = useQuery({
    queryKey: ["history", favoriteOnly],
    queryFn: () => getHistory(favoriteOnly),
  });

  const favoriteMutation = useMutation({
    mutationFn: toggleFavorite,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["history"] }),
  });

  const { createShorts, isCreatingFor } = useShortsCreation(["history"]);

  // Dashboard와 동일하게 최신순 정렬 - 백엔드는 오래된 순서로 준다
  const sortedHistory = [...(historyQuery.data ?? [])].sort(
    (a, b) => (b.created_at ?? 0) - (a.created_at ?? 0)
  );

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-8 py-10">
      <div>
        <h1 className="text-2xl font-semibold">생성 이력</h1>
        <label className="mt-3 flex items-center gap-2 text-sm">
          <Checkbox checked={favoriteOnly} onCheckedChange={() => setFavoriteOnly((v) => !v)} />
          <Star className="h-3.5 w-3.5" /> 즐겨찾기만 보기
        </label>
      </div>

      {historyQuery.isLoading && <p className="text-sm text-muted-foreground">불러오는 중...</p>}

      {historyQuery.data?.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {favoriteOnly ? "즐겨찾기한 광고가 없습니다." : "아직 생성한 광고가 없습니다. 광고 만들기에서 첫 광고를 만들어보세요."}
        </p>
      )}

      <div className="space-y-8">
        {sortedHistory.map((entry) => (
          <div key={entry.job_id} className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => favoriteMutation.mutate(entry.job_id)}
                  className="text-[var(--copper)]"
                  aria-label="즐겨찾기 토글"
                >
                  <Star className={entry.favorite ? "h-4 w-4 fill-current" : "h-4 w-4"} />
                </button>
                <p className="font-mono text-sm">
                  {entry.job_id} · {entry.results.length}개 결과
                </p>
              </div>
              <Button asChild variant="outline" size="sm">
                <a href={resolveAssetUrl(downloadAllUrl(entry.job_id))} download>
                  <Download /> 전체 다운로드 (ZIP)
                </a>
              </Button>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {entry.results.map((r) => (
                <ResultReceiptCard
                  key={r.result_id}
                  result={r}
                  jobId={entry.job_id}
                  onCreateShorts={createShorts}
                  isCreatingShorts={isCreatingFor(r.result_id)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HistoryPage() {
  return (
    <RequireAuth>
      <HistoryContent />
    </RequireAuth>
  );
}

"use client";

import Image from "next/image";
import { Button } from "@/components/ui/button";
import { resolveAssetUrl } from "@/lib/api/client";
import {
  TONE_LABEL,
  FORMAT_LABEL,
  RUSH_HOUR_SLOTS,
  TIME_SLOT_OPTIONS,
} from "@/lib/constants";
import type { ToneResult } from "@/lib/types/api";
import { Play, Download, Film, Layers, Pencil } from "lucide-react";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateGenerationCopy } from "@/lib/api/generations";

export function ResultReceiptCard({
  result,
  jobId,
  onCreateShorts,
  isCreatingShorts,
}: {
  result: ToneResult;
  jobId: string;
  onCreateShorts?: (resultId: string) => void;
  isCreatingShorts?: boolean;
}) {
  const [isEditingCopy, setIsEditingCopy] = useState(false);
  const [headline, setHeadline] = useState(result.headline);
  const [subcopy, setSubcopy] = useState(result.subcopy);

  const queryClient = useQueryClient();

  const updateCopyMutation = useMutation({
    mutationFn: () =>
      updateGenerationCopy(jobId, {
        resultId: result.result_id,
        headline: headline.trim(),
        subcopy: subcopy.trim(),
      }),
    onSuccess: async () => {
      setIsEditingCopy(false);

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["generation-result", jobId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["history", false],
        }),
      ]);
    },
  });

  const isRushHour =
    result.time_slot && RUSH_HOUR_SLOTS.includes(result.time_slot);
  const firstImageUrl = Object.values(result.images)[0];
  const timeSlotLabel = TIME_SLOT_OPTIONS.find(
    (o) => o.value === result.time_slot,
  )?.label;

  return (
    <div className="creative-card">
      {firstImageUrl && (
        <div className="relative aspect-square w-full bg-muted">
          <Image
            src={resolveAssetUrl(firstImageUrl)}
            alt={`${TONE_LABEL[result.tone]} 대표 이미지`}
            fill
            unoptimized
            className="object-contain"
          />
        </div>
      )}

      <div className="space-y-3 p-5">
        <div>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold">
                {TONE_LABEL[result.tone]}
                {timeSlotLabel ? ` · ${timeSlotLabel}` : ""}
              </p>

              {!isEditingCopy && (
                <>
                  <p className="mt-1 text-sm">{result.headline}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {result.subcopy}
                  </p>
                </>
              )}
            </div>

            {!isEditingCopy && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setHeadline(result.headline);
                  setSubcopy(result.subcopy);
                  setIsEditingCopy(true);
                }}
              >
                <Pencil className="h-3.5 w-3.5" />
                문구 수정
              </Button>
            )}
          </div>

          {isEditingCopy && (
            <div className="mt-4 space-y-3 rounded-md border border-border p-3">
              <div className="space-y-1.5">
                <label
                  htmlFor={`headline-${result.result_id}`}
                  className="text-xs font-medium"
                >
                  헤드라인
                </label>

                <input
                  id={`headline-${result.result_id}`}
                  value={headline}
                  onChange={(e) => setHeadline(e.target.value)}
                  className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-1 focus:ring-foreground"
                />
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor={`subcopy-${result.result_id}`}
                  className="text-xs font-medium"
                >
                  서브카피
                </label>

                <input
                  id={`subcopy-${result.result_id}`}
                  value={subcopy}
                  onChange={(e) => setSubcopy(e.target.value)}
                  className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-1 focus:ring-foreground"
                />
              </div>

              {updateCopyMutation.isError && (
                <p className="text-xs text-destructive">
                  문구 수정에 실패했습니다.
                </p>
              )}

              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={updateCopyMutation.isPending}
                  onClick={() => {
                    setHeadline(result.headline);
                    setSubcopy(result.subcopy);
                    setIsEditingCopy(false);
                  }}
                >
                  취소
                </Button>

                <Button
                  type="button"
                  size="sm"
                  disabled={
                    updateCopyMutation.isPending ||
                    !headline.trim() ||
                    !subcopy.trim()
                  }
                  onClick={() => updateCopyMutation.mutate()}
                >
                  {updateCopyMutation.isPending ? "저장 중..." : "저장"}
                </Button>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {Object.entries(result.images).map(([fmt, url]) => (
            <Button key={fmt} asChild variant="outline" size="sm">
              <a href={resolveAssetUrl(url)} download>
                <Download /> {FORMAT_LABEL[fmt] ?? fmt}
              </a>
            </Button>
          ))}
        </div>

        {/* 러시아워 코믹 콘텐츠 - 팀원 결정에 따라 이 섹션 안에서만 옵션을 갈아끼우면 된다 */}
        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
          {result.video_url ? (
            <Button asChild variant="secondary" size="sm">
              <a
                href={resolveAssetUrl(result.video_url)}
                target="_blank"
                rel="noreferrer"
              >
                <Play /> 코믹 쇼츠 보기
              </a>
            </Button>
          ) : isRushHour && onCreateShorts ? (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onCreateShorts(result.result_id)}
              disabled={isCreatingShorts}
            >
              <Film />{" "}
              {isCreatingShorts ? "코믹 쇼츠 만드는 중..." : "코믹 쇼츠 만들기"}
            </Button>
          ) : (
            <Button size="sm" variant="outline" disabled>
              <Film /> 코믹 쇼츠 (출근/퇴근만)
            </Button>
          )}
          <Button size="sm" variant="outline" disabled title="준비 중">
            <Layers /> SNS 콘텐츠
          </Button>
        </div>
      </div>
    </div>
  );
}

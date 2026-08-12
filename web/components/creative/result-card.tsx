"use client";

import Image from "next/image";
import { Button } from "@/components/ui/button";
import { resolveAssetUrl } from "@/lib/api/client";
import { TONE_LABEL, RUSH_HOUR_SLOTS } from "@/lib/constants";
import type { ToneResult } from "@/lib/types/api";
import { Play, Download, Film, Layers } from "lucide-react";

export function ResultReceiptCard({
  result,
  onCreateShorts,
  isCreatingShorts,
}: {
  result: ToneResult;
  jobId: string;
  onCreateShorts?: (resultId: string) => void;
  isCreatingShorts?: boolean;
}) {
  const isRushHour = result.time_slot && RUSH_HOUR_SLOTS.includes(result.time_slot);
  const firstImageUrl = Object.values(result.images)[0];

  return (
    <div className="creative-card">
      {firstImageUrl && (
        <div className="relative aspect-square w-full bg-muted">
          <Image
            src={resolveAssetUrl(firstImageUrl)}
            alt={`${TONE_LABEL[result.tone]} 대표 이미지`}
            fill
            unoptimized
            className="object-cover"
          />
        </div>
      )}

      <div className="space-y-3 p-5">
        <div>
          <p className="text-sm font-semibold">
            {TONE_LABEL[result.tone]}
            {result.time_slot ? ` · ${result.time_slot}` : ""}
          </p>
          <p className="mt-0.5 text-sm text-muted-foreground">{result.headline}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {Object.entries(result.images).map(([fmt, url]) => (
            <Button key={fmt} asChild variant="outline" size="sm">
              <a href={resolveAssetUrl(url)} download>
                <Download /> {fmt}
              </a>
            </Button>
          ))}
        </div>

        {/* 러시아워 코믹 콘텐츠 - 팀원 결정에 따라 이 섹션 안에서만 옵션을 갈아끼우면 된다 */}
        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
          {result.video_url ? (
            <Button asChild variant="secondary" size="sm">
              <a href={resolveAssetUrl(result.video_url)} target="_blank" rel="noreferrer">
                <Play /> 코믹 쇼츠 보기
              </a>
            </Button>
          ) : isRushHour && onCreateShorts ? (
            <Button size="sm" variant="secondary" onClick={() => onCreateShorts(result.result_id)} disabled={isCreatingShorts}>
              <Film /> {isCreatingShorts ? "코믹 쇼츠 만드는 중..." : "코믹 쇼츠 만들기"}
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

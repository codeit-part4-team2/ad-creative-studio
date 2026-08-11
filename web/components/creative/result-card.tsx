"use client";

import Image from "next/image";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { resolveAssetUrl } from "@/lib/api/client";
import { TONE_LABEL, RUSH_HOUR_SLOTS } from "@/lib/constants";
import type { ToneResult } from "@/lib/types/api";
import { Play, Download } from "lucide-react";

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
  const isRushHour = result.time_slot && RUSH_HOUR_SLOTS.includes(result.time_slot);

  return (
    <div className="receipt-card">
      <div className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="font-mono text-xs text-muted-foreground">#{result.result_id}</p>
            <p className="mt-1 text-base font-semibold">
              {TONE_LABEL[result.tone]}
              {result.time_slot ? ` · ${result.time_slot}` : ""}
            </p>
          </div>
          <Badge variant="outline">{jobId}</Badge>
        </div>

        <div className="receipt-divider" />

        <div className="grid grid-cols-3 gap-3">
          {Object.entries(result.images).map(([fmt, url]) => (
            <div key={fmt} className="space-y-1">
              <p className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                {fmt}
              </p>
              <div className="relative aspect-square overflow-hidden rounded-md border border-border bg-muted">
                <Image
                  src={resolveAssetUrl(url)}
                  alt={`${TONE_LABEL[result.tone]} ${fmt}`}
                  fill
                  unoptimized
                  className="object-cover"
                />
              </div>
            </div>
          ))}
        </div>

        <div className="receipt-divider" />

        <p className="text-sm font-medium">{result.headline}</p>
        <p className="mt-1 text-sm text-muted-foreground">{result.subcopy}</p>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          {Object.entries(result.images).map(([fmt, url]) => (
            <Button key={fmt} asChild variant="outline" size="sm">
              <a href={resolveAssetUrl(url)} download>
                <Download /> {fmt}
              </a>
            </Button>
          ))}

          {result.video_url ? (
            <Button asChild variant="secondary" size="sm">
              <a href={resolveAssetUrl(result.video_url)} target="_blank" rel="noreferrer">
                <Play /> 쇼츠 보기
              </a>
            </Button>
          ) : isRushHour && onCreateShorts ? (
            <Button
              size="sm"
              onClick={() => onCreateShorts(result.result_id)}
              disabled={isCreatingShorts}
            >
              🎬 러시아워 쇼츠 만들기
            </Button>
          ) : null}
        </div>
      </div>
      <div className="receipt-tear" />
    </div>
  );
}

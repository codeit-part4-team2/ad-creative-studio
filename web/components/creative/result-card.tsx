"use client";

import Image from "next/image";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { resolveAssetUrl } from "@/lib/api/client";
import { TONE_LABEL, RUSH_HOUR_SLOTS } from "@/lib/constants";
import type { ToneResult } from "@/lib/types/api";
import { Play, Download, Film, Layers } from "lucide-react";

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
  const firstImageUrl = Object.values(result.images)[0];

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

        {/* 실제 광고 이미지 - 대표 규격 하나를 크게, 나머지는 아래 작게 */}
        {firstImageUrl && (
          <div className="relative mb-3 aspect-square w-full overflow-hidden rounded-md border border-border bg-muted">
            <Image
              src={resolveAssetUrl(firstImageUrl)}
              alt={`${TONE_LABEL[result.tone]} 대표 이미지`}
              fill
              unoptimized
              className="object-cover"
            />
          </div>
        )}
        <div className="grid grid-cols-3 gap-2">
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

        {/* 기본 액션 - 다운로드 */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {Object.entries(result.images).map(([fmt, url]) => (
            <Button key={fmt} asChild variant="outline" size="sm">
              <a href={resolveAssetUrl(url)} download>
                <Download /> {fmt}
              </a>
            </Button>
          ))}
        </div>

        <div className="receipt-divider" />

        {/* 콘텐츠 확장 - 팀원 결정에 따라 이 섹션 안에서만 옵션을 갈아끼우면 된다.
            지금은 러시아워 쇼츠(기술 검증 완료, 디자인 고도화 대기)만 실제로 연결돼 있고,
            나머지는 자리만 잡아둔 상태다. */}
        <p className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          콘텐츠 확장
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {result.video_url ? (
            <Button asChild variant="secondary" size="sm">
              <a href={resolveAssetUrl(result.video_url)} target="_blank" rel="noreferrer">
                <Play /> 쇼츠 보기
              </a>
            </Button>
          ) : isRushHour && onCreateShorts ? (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onCreateShorts(result.result_id)}
              disabled={isCreatingShorts}
            >
              <Film /> {isCreatingShorts ? "쇼츠 만드는 중..." : "쇼츠 만들기"}
            </Button>
          ) : (
            <Button size="sm" variant="outline" disabled>
              <Film /> 쇼츠 만들기 (출근/퇴근 광고만)
            </Button>
          )}
          <Button size="sm" variant="outline" disabled title="준비 중">
            <Layers /> SNS 콘텐츠 만들기
          </Button>
        </div>
      </div>
      <div className="receipt-tear" />
    </div>
  );
}

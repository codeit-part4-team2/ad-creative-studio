"use client";

import Link from "next/link";
import Image from "next/image";
import { useQuery } from "@tanstack/react-query";
import { getHistory } from "@/lib/api/history";
import { resolveAssetUrl } from "@/lib/api/client";
import { TONE_LABEL } from "@/lib/constants";
import { Button } from "@/components/ui/button";

import { RequireAuth } from "@/components/auth/require-auth";

function DashboardContent() {
  const historyQuery = useQuery({ queryKey: ["history", false], queryFn: () => getHistory(false) });

  const entries = historyQuery.data ?? [];
  const generatedCount = entries.reduce((sum, e) => sum + e.results.length, 0);
  const savedCount = entries.filter((e) => e.favorite).length;
  const publishedCount = entries.reduce(
    (sum, e) => sum + e.results.filter((r) => r.video_url).length,
    0
  );

  // 최근 결과 4개 - HISTORY는 백엔드가 오래된 순서로 append하므로, created_at 기준
  // 최신순으로 명시적으로 정렬한 뒤 앞에서 4개를 뽑는다 (배열 순서에 기대지 않음).
  const recentCreatives = [...entries]
    .sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0))
    .flatMap((entry) => entry.results.map((r) => ({ entry, result: r })))
    .slice(0, 4);

  return (
    <div className="mx-auto w-full max-w-[1440px] px-8 py-12 lg:px-12">
      {/* Hero */}
      <section>
        <h1 className="text-4xl font-bold leading-tight tracking-tight md:text-5xl">
          Turn one product photo
          <br />
          into ready-to-run ads.
        </h1>
        <p className="mt-4 max-w-md text-sm text-muted-foreground">
          제품 사진 한 장으로 시간대에 맞는 광고 크리에이티브를 생성합니다.
        </p>
        <Button asChild variant="accent" size="lg" className="mt-6">
          <Link href="/create">CREATE NEW AD →</Link>
        </Button>
      </section>

      <div className="my-10 border-t border-border" />

      {/* Overview */}
      <section>
        <p className="text-xs font-semibold tracking-wide text-muted-foreground">OVERVIEW</p>
        <div className="mt-4 grid grid-cols-3 gap-6 md:w-1/2">
          <div>
            <p className="text-3xl font-bold">{generatedCount}</p>
            <p className="mt-1 text-xs tracking-wide text-muted-foreground">GENERATED</p>
          </div>
          <div>
            <p className="text-3xl font-bold">{savedCount}</p>
            <p className="mt-1 text-xs tracking-wide text-muted-foreground">SAVED</p>
          </div>
          <div>
            <p className="text-3xl font-bold">{publishedCount}</p>
            <p className="mt-1 text-xs tracking-wide text-muted-foreground">PUBLISHED</p>
          </div>
        </div>
      </section>

      <div className="my-10 border-t border-border" />

      {/* Recent Creative */}
      <section>
        <p className="text-xs font-semibold tracking-wide text-muted-foreground">RECENT CREATIVE</p>

        {recentCreatives.length === 0 ? (
          <div className="mt-6 rounded-lg border border-dashed border-border py-16 text-center">
            <p className="text-sm font-medium">NO CREATIVE YET</p>
            <p className="mt-1 text-sm text-muted-foreground">Create your first AI-powered ad.</p>
            <Button asChild variant="accent" className="mt-4">
              <Link href="/create">CREATE NEW AD →</Link>
            </Button>
          </div>
        ) : (
          <>
            <div className="mt-6 grid grid-cols-2 gap-6 md:grid-cols-4">
              {recentCreatives.map(({ entry, result }) => {
                const firstImage = Object.values(result.images)[0];
                return (
                  <Link key={result.result_id} href={`/result/${entry.job_id}`} className="block">
                    <div className="relative aspect-square overflow-hidden rounded-lg border border-border bg-muted">
                      {firstImage && (
                        <Image
                          src={resolveAssetUrl(firstImage)}
                          alt={result.headline}
                          fill
                          unoptimized
                          className="object-contain transition-transform hover:scale-[1.02]"
                        />
                      )}
                    </div>
                    <p className="mt-2 text-sm font-medium">{result.headline}</p>
                    <p className="text-xs tracking-wide text-muted-foreground">
                      {result.time_slot?.toUpperCase()} · {TONE_LABEL[result.tone]}
                    </p>
                  </Link>
                );
              })}
            </div>
            <Button asChild variant="link" className="mt-4 px-0">
              <Link href="/history">VIEW ALL →</Link>
            </Button>
          </>
        )}
      </section>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}

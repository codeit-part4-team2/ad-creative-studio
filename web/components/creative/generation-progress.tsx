"use client";

import { useEffect, useState } from "react";
import { LOADING_STAGES } from "@/lib/constants";
import type { JobStatusResponse } from "@/lib/types/api";

export function GenerationProgress({ job }: { job: JobStatusResponse | undefined }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => setElapsed((Date.now() - start) / 1000), 500);
    return () => clearInterval(id);
  }, []);

  let currentIdx = 0;
  LOADING_STAGES.forEach((s, i) => {
    if (elapsed >= s.atSeconds) currentIdx = i;
  });

  return (
    <div className="creative-card p-6">
      <p className="font-medium">광고를 만들고 있어요 ✨</p>
      <div className="border-t border-border my-3" />
      <ul className="space-y-2 text-sm">
        {LOADING_STAGES.map((s, i) => (
          <li key={s.label}>
            <div className="flex items-center gap-2">
              <span>{i < currentIdx ? "✅" : i === currentIdx ? "🎨" : "⬜"}</span>
              <span className={i < currentIdx ? "text-muted-foreground" : ""}>{s.label}</span>
            </div>
            {i === currentIdx && s.subtext && (
              <p className="ml-6 text-xs text-muted-foreground">{s.subtext}</p>
            )}
          </li>
        ))}
      </ul>
      {job && (
        <>
          <div className="border-t border-border my-3" />
          <p className="font-mono text-xs text-muted-foreground">
            현재 {job.completed_count} / {job.total_count}개 생성 완료
          </p>
        </>
      )}
    </div>
  );
}

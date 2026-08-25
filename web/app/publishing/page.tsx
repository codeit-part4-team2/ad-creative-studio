"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { RequireAuth } from "@/components/auth/require-auth";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { getHistory } from "@/lib/api/history";
import { approveVideo, getVideoStatus } from "@/lib/api/videos";
import {
  getYouTubeStatus,
  type YouTubeStatusResponse,
} from "@/lib/api/youtube";
import { resolveAssetUrl } from "@/lib/api/client";
import {
  canRetryPublish,
  canSubmitPublish,
  needsPronunciationConfirmation,
} from "@/lib/publishing-state";

import type {
  ToneResult,
  VideoJobResponse,
  VideoPublishStatus,
} from "@/lib/types/api";

type PublishableVideo = {
  result: ToneResult;
  video: VideoJobResponse;
};

const TIME_SLOT_LABELS: Record<string, string> = {
  commute_am: "출근 러시아워",
  commute_pm: "퇴근 러시아워",
};

const TONE_LABELS: Record<string, string> = {
  emotional: "감성",
  modern: "모던",
  practical: "실용",
  premium: "프리미엄",
};

const PUBLISH_STATUS_LABELS: Record<VideoPublishStatus, string> = {
  not_requested: "게시 전",
  pending: "게시 처리 중",
  scheduled: "예약 게시 완료",
  failed: "게시 실패",
  auth_required: "YouTube 인증 필요",
  needs_review: "수동 확인 필요",
  schedule_expired: "예약 시간 만료",
};

function formatKst(value: string | null) {
  if (!value) return "-";

  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function kstLocalToIso(value: string) {
  const normalized = value.length === 16 ? `${value}:00` : value;

  return new Date(`${normalized}+09:00`).toISOString();
}

function PublishingContent() {
  const [youtubeStatus, setYoutubeStatus] =
    useState<YouTubeStatusResponse | null>(null);

  const [videos, setVideos] = useState<PublishableVideo[]>([]);
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);

  const [activationAt, setActivationAt] = useState("");
  const [loading, setLoading] = useState(true);
  const [publishingVideoId, setPublishingVideoId] = useState<string | null>(
    null,
  );
  const [pronunciationConfirmed, setPronunciationConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = useMemo(
    () => videos.find((item) => item.video.video_job_id === selectedVideoId),
    [videos, selectedVideoId],
  );

  const isPublishing = publishingVideoId === selected?.video.video_job_id;
  const isPublishRetry = selected ? canRetryPublish(selected.video) : false;
  const canSubmitSelected = selected ? canSubmitPublish(selected.video) : false;
  const needsPronunciationReview = selected
    ? needsPronunciationConfirmation(selected.video)
    : false;

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [youtube, history] = await Promise.all([
        getYouTubeStatus(),
        getHistory(false),
      ]);

      setYoutubeStatus(youtube);

      const resultMap = new Map<string, ToneResult>();

      for (const entry of history) {
        for (const result of entry.results) {
          if (result.video_job_id) {
            resultMap.set(result.video_job_id, result);
          }
        }
      }

      const loadedVideos = await Promise.all(
        [...resultMap.entries()].map(async ([videoJobId, result]) => {
          try {
            const video = await getVideoStatus(videoJobId);

            if (video.render_status !== "completed") {
              return null;
            }

            return { result, video };
          } catch {
            return null;
          }
        }),
      );

      const publishable = loadedVideos.filter(
        (item): item is PublishableVideo => item !== null,
      );

      setVideos(publishable);

      if (publishable.length > 0) {
        setSelectedVideoId((current) => {
          if (
            current &&
            publishable.some((item) => item.video.video_job_id === current)
          ) {
            return current;
          }

          return publishable[0].video.video_job_id;
        });
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "게시 정보를 불러오지 못했습니다.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    setPronunciationConfirmed(false);
  }, [selectedVideoId]);

  async function pollPublishStatus(videoJobId: string) {
    for (let i = 0; i < 15; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1000));

      const updated = await getVideoStatus(videoJobId);

      setVideos((current) =>
        current.map((item) =>
          item.video.video_job_id === videoJobId
            ? { ...item, video: updated }
            : item,
        ),
      );

      if (updated.publish_status !== "pending") {
        return updated;
      }
    }

    const finalStatus = await getVideoStatus(videoJobId);

    setVideos((current) =>
      current.map((item) =>
        item.video.video_job_id === videoJobId
          ? { ...item, video: finalStatus }
          : item,
      ),
    );

    return finalStatus;
  }

  async function handlePublish() {
    if (!selected) return;

    if (!activationAt) {
      setError("예약 게시 시간을 선택해주세요.");
      return;
    }

    setPublishingVideoId(selected.video.video_job_id);
    setError(null);

    try {
      const activationIso = kstLocalToIso(activationAt);

      const approved = await approveVideo(selected.video.video_job_id, {
        activation_at: activationIso,
        publish_to_youtube: true,
        pronunciation_confirmed:
          !needsPronunciationReview || pronunciationConfirmed,
      });

      setVideos((current) =>
        current.map((item) =>
          item.video.video_job_id === approved.video_job_id
            ? { ...item, video: approved }
            : item,
        ),
      );

      if (approved.publish_status === "pending") {
        await pollPublishStatus(approved.video_job_id);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "YouTube 예약 게시 요청에 실패했습니다.",
      );
    } finally {
      setPublishingVideoId(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-8 py-10">
      <div>
        <h1 className="text-2xl font-semibold">게시 관리</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          완성된 쇼츠를 검토하고 YouTube에 예약 게시합니다.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>YouTube 연결 상태</CardTitle>

          {youtubeStatus ? (
            <CardDescription>
              {youtubeStatus.configured && youtubeStatus.token_available ? (
                <>
                  <span className="font-medium text-green-600">● 연결됨</span>
                  {" · "}
                  {youtubeStatus.connection_id}
                </>
              ) : (
                <span className="font-medium text-red-600">● 연결 필요</span>
              )}
            </CardDescription>
          ) : (
            <CardDescription>연결 상태 확인 중...</CardDescription>
          )}
        </CardHeader>
      </Card>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <Card>
          <CardHeader>
            <CardDescription>
              게시 가능한 쇼츠를 불러오는 중입니다.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : videos.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>게시 가능한 쇼츠가 없습니다</CardTitle>
            <CardDescription>
              먼저 광고 결과에서 쇼츠 생성을 완료해주세요.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
          <div className="space-y-3">
            <h2 className="text-sm font-medium">완성된 쇼츠</h2>

            {videos.map(({ result, video }) => {
              const active = video.video_job_id === selectedVideoId;

              return (
                <button
                  key={video.video_job_id}
                  type="button"
                  onClick={() => setSelectedVideoId(video.video_job_id)}
                  className={`w-full rounded-lg border p-4 text-left transition ${
                    active ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                  }`}
                >
                  <div className="font-medium">
                    {result.headline || "쇼츠 광고"}
                  </div>

                  <div className="mt-1 text-xs text-muted-foreground">
                    {TIME_SLOT_LABELS[video.time_slot]}
                    {" · "}
                    {TONE_LABELS[video.tone] ?? video.tone}
                  </div>

                  <div className="mt-2 text-xs">
                    {PUBLISH_STATUS_LABELS[video.publish_status]}
                  </div>
                </button>
              );
            })}
          </div>

          {selected && (
            <Card>
              <CardHeader>
                <CardTitle>{selected.result.headline || "쇼츠 광고"}</CardTitle>

                <CardDescription>
                  {TIME_SLOT_LABELS[selected.video.time_slot]}
                  {" · "}
                  {TONE_LABELS[selected.video.tone] ?? selected.video.tone}
                </CardDescription>
              </CardHeader>

              <div className="space-y-5 px-6 pb-6">
                {selected.video.video_url && (
                  <video
                    controls
                    className="max-h-[420px] w-full rounded-lg bg-black"
                    src={resolveAssetUrl(selected.video.video_url)}
                  />
                )}
                {needsPronunciationReview && (
                  <label className="flex items-start gap-2 rounded-lg border p-3 text-sm">
                    <input
                      type="checkbox"
                      checked={pronunciationConfirmed}
                      onChange={(event) =>
                        setPronunciationConfirmed(event.target.checked)
                      }
                      className="mt-0.5"
                    />

                    <span>
                      상품명 발음을 확인했습니다.
                      <span className="mt-1 block text-xs text-muted-foreground">
                        쇼츠 영상을 재생해 상품명 발음을 확인한 뒤 체크해주세요.
                      </span>
                    </span>
                  </label>
                )}

                {selected.video.publish_status === "scheduled" ? (
                  <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                    <div className="font-medium text-green-700">
                      ✓ YouTube 예약 게시 완료
                    </div>

                    <div className="mt-2 space-y-1 text-sm text-green-800">
                      <div>
                        예약 시각: {formatKst(selected.video.activation_at)}
                      </div>

                      <div>
                        YouTube Video ID:{" "}
                        {selected.video.youtube_video_id ?? "-"}
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <div>
                      <label
                        htmlFor="activation-at"
                        className="mb-2 block text-sm font-medium"
                      >
                        예약 게시 시간
                      </label>

                      <input
                        id="activation-at"
                        type="datetime-local"
                        value={activationAt}
                        onChange={(event) =>
                          setActivationAt(event.target.value)
                        }
                        className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                      />

                      <p className="mt-2 text-xs text-muted-foreground">
                        한국 표준시(KST) 기준 · 출근 러시아워 08:00~09:30 · 퇴근
                        러시아워 18:00~19:30
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={handlePublish}
                      disabled={
                        isPublishing ||
                        !activationAt ||
                        !youtubeStatus?.configured ||
                        !youtubeStatus?.token_available ||
                        !canSubmitSelected ||
                        (needsPronunciationReview && !pronunciationConfirmed)
                      }
                      className="w-full rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isPublishing
                        ? "YouTube 예약 게시 처리 중..."
                        : isPublishRetry
                          ? "YouTube 예약 게시 재시도"
                          : "승인 및 YouTube 예약 게시"}
                    </button>
                  </>
                )}
                {selected.video.youtube_error && (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                    {selected.video.youtube_error}
                  </div>
                )}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

export default function PublishingPage() {
  return (
    <RequireAuth>
      <PublishingContent />
    </RequireAuth>
  );
}

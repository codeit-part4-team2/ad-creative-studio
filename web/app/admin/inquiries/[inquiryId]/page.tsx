"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Clock3, Shield } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  answerInquiry,
  getAdminInquiries,
  getAdminKey,
} from "@/lib/api/admin-inquiries";

function AdminInquiryContent({ inquiryId }: { inquiryId: string }) {
  const [adminKey, setAdminKey] = useState<string | null>(null);
  const [keyLoaded, setKeyLoaded] = useState(false);
  const [answer, setAnswer] = useState("");

  const queryClient = useQueryClient();

  useEffect(() => {
    let cancelled = false;

    Promise.resolve().then(() => {
      if (cancelled) return;

      setAdminKey(getAdminKey());
      setKeyLoaded(true);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  const inquiryQuery = useQuery({
    queryKey: ["admin-inquiry", inquiryId, adminKey],
    queryFn: async () => {
      if (!adminKey) {
        throw new Error("관리자 인증 정보가 없습니다.");
      }

      const inquiries = await getAdminInquiries(adminKey);
      const inquiry = inquiries.find((item) => item.inquiry_id === inquiryId);

      if (!inquiry) {
        throw new Error("문의를 찾을 수 없습니다.");
      }

      return inquiry;
    },
    enabled: keyLoaded && Boolean(adminKey),
    retry: false,
  });

  const answerMutation = useMutation({
    mutationFn: async () => {
      if (!adminKey) {
        throw new Error("관리자 인증 정보가 없습니다.");
      }

      return answerInquiry(inquiryId, answer.trim(), adminKey);
    },

    onSuccess: async () => {
      setAnswer("");

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["admin-inquiry", inquiryId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["admin-inquiries"],
        }),
      ]);
    },
  });

  if (!keyLoaded) {
    return null;
  }

  if (!adminKey) {
    return (
      <div className="mx-auto w-full max-w-[720px] px-8 py-20">
        <div className="rounded-lg border border-border bg-card p-6 text-center">
          <Shield className="mx-auto h-6 w-6 text-muted-foreground" />

          <p className="mt-3 text-sm font-medium">관리자 인증이 필요합니다.</p>

          <Button asChild variant="accent" className="mt-4">
            <Link href="/admin/inquiries">관리자 인증으로 돌아가기</Link>
          </Button>
        </div>
      </div>
    );
  }

  if (inquiryQuery.isLoading) {
    return (
      <div className="mx-auto w-full max-w-[1000px] px-8 py-12">
        <p className="text-sm text-muted-foreground">문의를 불러오는 중...</p>
      </div>
    );
  }

  if (inquiryQuery.isError || !inquiryQuery.data) {
    return (
      <div className="mx-auto w-full max-w-[1000px] px-8 py-12">
        <p className="text-sm text-destructive">문의를 불러오지 못했습니다.</p>

        <Button asChild variant="outline" className="mt-4">
          <Link href="/admin/inquiries">문의 목록으로 돌아가기</Link>
        </Button>
      </div>
    );
  }

  const inquiry = inquiryQuery.data;
  const answered = inquiry.status === "answered";

  return (
    <div className="mx-auto w-full max-w-[1000px] px-8 py-12">
      <Link
        href="/admin/inquiries"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        INQUIRY MANAGEMENT
      </Link>

      <article className="mt-8 rounded-lg border border-border bg-card">
        <div className="border-b border-border p-6">
          <div className="flex items-center justify-between gap-4">
            <span
              className={
                answered
                  ? "inline-flex items-center gap-1.5 rounded-full border border-foreground bg-foreground px-2.5 py-1 text-xs font-medium text-background"
                  : "inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground"
              }
            >
              {answered ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : (
                <Clock3 className="h-3.5 w-3.5" />
              )}

              {answered ? "답변완료" : "답변대기"}
            </span>

            <span className="text-xs text-muted-foreground">
              {new Date(inquiry.created_at * 1000).toLocaleString("ko-KR")}
            </span>
          </div>

          <h1 className="mt-4 text-2xl font-semibold">{inquiry.title}</h1>

          <p className="mt-2 text-xs text-muted-foreground">
            {inquiry.company_name} · {inquiry.customer_id}
          </p>
        </div>

        <div className="min-h-[220px] whitespace-pre-wrap p-6 text-sm leading-7">
          {inquiry.content}
        </div>
      </article>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">운영자 답변</h2>

        {answered && inquiry.answer && (
          <div className="mt-4 rounded-lg border border-border bg-card p-6">
            <p className="whitespace-pre-wrap text-sm leading-7">
              {inquiry.answer}
            </p>

            {inquiry.answered_at && (
              <p className="mt-4 text-xs text-muted-foreground">
                답변일{" "}
                {new Date(inquiry.answered_at * 1000).toLocaleString("ko-KR")}
              </p>
            )}
          </div>
        )}

        <div className="mt-4 rounded-lg border border-border bg-card p-6">
          <label htmlFor="admin-answer" className="text-sm font-medium">
            {answered ? "답변 수정" : "답변 작성"}
          </label>

          <textarea
            id="admin-answer"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            maxLength={5000}
            rows={7}
            placeholder={
              answered
                ? "새 답변을 입력하면 기존 답변이 변경됩니다."
                : "고객에게 전달할 답변을 입력하세요."
            }
            className="mt-2 w-full resize-none rounded-md border border-border bg-background px-3 py-3 text-sm outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-foreground"
          />

          {answerMutation.isError && (
            <p className="mt-2 text-sm text-destructive">
              답변 등록에 실패했습니다.
            </p>
          )}

          <div className="mt-4 flex justify-end">
            <Button
              variant="accent"
              disabled={answerMutation.isPending || !answer.trim()}
              onClick={() => answerMutation.mutate()}
            >
              {answerMutation.isPending
                ? "등록 중..."
                : answered
                  ? "답변 수정"
                  : "답변 등록"}
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}

export default function AdminInquiryDetailPage({
  params,
}: {
  params: Promise<{ inquiryId: string }>;
}) {
  const { inquiryId } = use(params);

  return <AdminInquiryContent inquiryId={inquiryId} />;
}

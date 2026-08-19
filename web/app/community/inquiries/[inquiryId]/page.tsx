"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Clock3 } from "lucide-react";
import { formatCreatedAt } from "@/lib/utils";
import { RequireAuth } from "@/components/auth/require-auth";
import { getInquiry } from "@/lib/api/inquiries";

function InquiryDetailContent({ inquiryId }: { inquiryId: string }) {
  const inquiryQuery = useQuery({
    queryKey: ["inquiry", inquiryId],
    queryFn: () => getInquiry(inquiryId),
  });

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
      </div>
    );
  }

  const inquiry = inquiryQuery.data;
  const answered = inquiry.status === "answered";

  return (
    <div className="mx-auto w-full max-w-[1000px] px-8 py-12">
      <Link
        href="/community"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Q&A / 문의
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
              {formatCreatedAt(inquiry.created_at)}
            </span>
          </div>

          <h1 className="mt-4 text-2xl font-semibold">{inquiry.title}</h1>

          <p className="mt-2 text-xs text-muted-foreground">
            {inquiry.company_name}
          </p>
        </div>

        <div className="min-h-[220px] whitespace-pre-wrap p-6 text-sm leading-7">
          {inquiry.content}
        </div>
      </article>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">운영자 답변</h2>

        {answered && inquiry.answer ? (
          <div className="mt-4 rounded-lg border border-border bg-card p-6">
            <p className="whitespace-pre-wrap text-sm leading-7">
              {inquiry.answer}
            </p>

            {inquiry.answered_at && (
              <p className="mt-4 text-xs text-muted-foreground">
                답변일 {formatCreatedAt(inquiry.answered_at)}
              </p>
            )}
          </div>
        ) : (
          <div className="mt-4 rounded-lg border border-dashed border-border bg-card px-6 py-10 text-center">
            <Clock3 className="mx-auto h-5 w-5 text-muted-foreground" />
            <p className="mt-3 text-sm font-medium">
              운영자 답변을 기다리고 있습니다.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              답변이 등록되면 이 화면에서 확인할 수 있습니다.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

export default function InquiryDetailPage({
  params,
}: {
  params: Promise<{ inquiryId: string }>;
}) {
  const { inquiryId } = use(params);

  return (
    <RequireAuth>
      <InquiryDetailContent inquiryId={inquiryId} />
    </RequireAuth>
  );
}

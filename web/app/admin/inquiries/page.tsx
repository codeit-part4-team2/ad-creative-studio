"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock3, Shield } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  getAdminInquiries,
  setAdminKey as saveAdminKey,
} from "@/lib/api/admin-inquiries";

import Link from "next/link";

export default function AdminInquiriesPage() {
  const [adminKeyInput, setAdminKeyInput] = useState("");
  const [adminKey, setAdminKey] = useState("");

  const inquiriesQuery = useQuery({
    queryKey: ["admin-inquiries", adminKey],
    queryFn: () => getAdminInquiries(adminKey),
    enabled: Boolean(adminKey),
    retry: false,
  });

  function handleAccess() {
    const key = adminKeyInput.trim();
    if (!key) return;

    saveAdminKey(key);
    setAdminKey(key);
  }

  if (!adminKey) {
    return (
      <div className="mx-auto w-full max-w-[520px] px-8 py-20">
        <div className="rounded-lg border border-border bg-card p-6">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            <h1 className="text-xl font-semibold">ADMIN INQUIRIES</h1>
          </div>

          <p className="mt-2 text-sm text-muted-foreground">
            운영자 문의 관리 페이지입니다.
          </p>

          <label htmlFor="admin-key" className="mt-6 block text-sm font-medium">
            Admin API Key
          </label>

          <input
            id="admin-key"
            type="password"
            value={adminKeyInput}
            onChange={(e) => setAdminKeyInput(e.target.value)}
            placeholder="관리자 키를 입력하세요"
            className="mt-2 h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-1 focus:ring-foreground"
          />

          <Button
            variant="accent"
            className="mt-4 w-full"
            disabled={!adminKeyInput.trim()}
            onClick={handleAccess}
          >
            운영자 문의 관리
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1200px] px-8 py-12">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs font-semibold tracking-wide text-muted-foreground">
            ADMIN
          </p>

          <h1 className="mt-2 text-3xl font-bold tracking-tight">
            Inquiry Management
          </h1>

          <p className="mt-2 text-sm text-muted-foreground">
            고객 문의를 확인하고 답변을 관리합니다.
          </p>
        </div>

        <Button
          variant="outline"
          onClick={() => {
            saveAdminKey(null);
            setAdminKey("");
            setAdminKeyInput("");
          }}
        >
          관리자 종료
        </Button>
      </div>

      {inquiriesQuery.isLoading && (
        <div className="mt-10 text-sm text-muted-foreground">
          문의를 불러오는 중...
        </div>
      )}

      {inquiriesQuery.isError && (
        <div className="mt-10 rounded-lg border border-destructive/30 p-6">
          <p className="text-sm text-destructive">
            관리자 인증에 실패했거나 문의를 불러오지 못했습니다.
          </p>

          <Button
            variant="outline"
            className="mt-4"
            onClick={() => {
              setAdminKey("");
              setAdminKeyInput("");
            }}
          >
            다시 인증
          </Button>
        </div>
      )}

      {inquiriesQuery.data && (
        <div className="mt-8 overflow-hidden rounded-lg border border-border bg-card">
          <div className="grid grid-cols-[140px_1fr_180px_160px] border-b border-border bg-muted/40 px-5 py-3 text-xs font-semibold tracking-wide text-muted-foreground">
            <span>상태</span>
            <span>제목</span>
            <span>고객사</span>
            <span>작성일</span>
          </div>

          {inquiriesQuery.data.length === 0 ? (
            <div className="px-5 py-12 text-center text-sm text-muted-foreground">
              등록된 문의가 없습니다.
            </div>
          ) : (
            inquiriesQuery.data.map((inquiry) => (
              <Link
                key={inquiry.inquiry_id}
                href={`/admin/inquiries/${inquiry.inquiry_id}`}
                className="grid grid-cols-[140px_1fr_180px_160px] items-center border-b border-border px-5 py-4 transition-colors last:border-b-0 hover:bg-muted/40"
              >
                <div>
                  <span className="inline-flex items-center gap-1.5 text-xs">
                    {inquiry.status === "answered" ? (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    ) : (
                      <Clock3 className="h-3.5 w-3.5" />
                    )}

                    {inquiry.status === "answered" ? "답변완료" : "답변대기"}
                  </span>
                </div>

                <span className="text-sm font-medium">{inquiry.title}</span>

                <span className="text-xs text-muted-foreground">
                  {inquiry.company_name}
                </span>

                <span className="text-xs text-muted-foreground">
                  {new Date(inquiry.created_at * 1000).toLocaleDateString(
                    "ko-KR",
                  )}
                </span>
              </Link>
            ))
          )}
        </div>
      )}
    </div>
  );
}

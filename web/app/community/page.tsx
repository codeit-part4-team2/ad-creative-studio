"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, Plus } from "lucide-react";
import Link from "next/link";

import { RequireAuth } from "@/components/auth/require-auth";
import { Button } from "@/components/ui/button";
import {
  createCommunityPost,
  getCommunityPosts,
  type CommunityPost,
} from "@/lib/api/community";
import { cn } from "@/lib/utils";
import { createInquiry, getInquiries, type Inquiry } from "@/lib/api/inquiries";

type CommunityTab = "board" | "inquiry";

function CommunityContent() {
  const [activeTab, setActiveTab] = useState<CommunityTab>("board");
  const [showWriteForm, setShowWriteForm] = useState(false);
  const [showInquiryForm, setShowInquiryForm] = useState(false);
  const [inquiryTitle, setInquiryTitle] = useState("");
  const [inquiryContent, setInquiryContent] = useState("");
  const [category, setCategory] = useState("자유");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");

  const queryClient = useQueryClient();

  const postsQuery = useQuery({
    queryKey: ["community-posts"],
    queryFn: getCommunityPosts,
  });

  const inquiriesQuery = useQuery({
    queryKey: ["inquiries"],
    queryFn: getInquiries,
  });

  const createInquiryMutation = useMutation({
    mutationFn: createInquiry,
    onSuccess: async () => {
      setInquiryTitle("");
      setInquiryContent("");
      setShowInquiryForm(false);

      await queryClient.invalidateQueries({
        queryKey: ["inquiries"],
      });
    },
  });

  const createPostMutation = useMutation({
    mutationFn: createCommunityPost,
    onSuccess: async () => {
      setCategory("자유");
      setTitle("");
      setContent("");
      setShowWriteForm(false);

      await queryClient.invalidateQueries({
        queryKey: ["community-posts"],
      });
    },
  });

  return (
    <div className="mx-auto w-full max-w-[1440px] px-8 py-12 lg:px-12">
      {/* Header */}
      <section>
        <p className="text-xs font-semibold tracking-wide text-muted-foreground">
          COMMUNITY
        </p>

        <h1 className="mt-2 text-3xl font-bold tracking-tight">
          Connect with AD STUDIO
        </h1>

        <p className="mt-2 text-sm text-muted-foreground">
          사용자들과 광고 제작 경험을 공유하고, 서비스에 대해 문의할 수
          있습니다.
        </p>
      </section>

      {/* Tabs */}
      <div className="mt-10 flex border-b border-border">
        <button
          type="button"
          onClick={() => setActiveTab("board")}
          className={cn(
            "border-b-2 px-5 py-3 text-sm font-medium transition-colors",
            activeTab === "board"
              ? "border-foreground text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground",
          )}
        >
          COMMUNITY BOARD
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("inquiry")}
          className={cn(
            "border-b-2 px-5 py-3 text-sm font-medium transition-colors",
            activeTab === "inquiry"
              ? "border-foreground text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground",
          )}
        >
          Q&A / 문의
        </button>
      </div>

      {/* Community Board */}
      {activeTab === "board" && (
        <section className="mt-8">
          <div className="flex items-end justify-between">
            <div>
              <h2 className="text-xl font-semibold">자유게시판</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                사용자들과 광고 제작 경험과 팁을 자유롭게 공유하세요.
              </p>
            </div>

            <Button
              variant="accent"
              size="sm"
              onClick={() => setShowWriteForm((prev) => !prev)}
            >
              <Plus className="h-4 w-4" />
              {showWriteForm ? "닫기" : "글쓰기"}
            </Button>
          </div>
          {showWriteForm && (
            <div className="mt-6 rounded-lg border border-border bg-card p-6">
              <div className="grid gap-5">
                <div className="space-y-2">
                  <label
                    htmlFor="community-category"
                    className="text-sm font-medium"
                  >
                    카테고리
                  </label>

                  <select
                    id="community-category"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-1 focus:ring-foreground"
                  >
                    <option value="광고 팁">광고 팁</option>
                    <option value="사용 후기">사용 후기</option>
                    <option value="자유">자유</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <label
                    htmlFor="community-title"
                    className="text-sm font-medium"
                  >
                    제목
                  </label>

                  <input
                    id="community-title"
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    maxLength={200}
                    placeholder="제목을 입력하세요"
                    className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-foreground"
                  />
                </div>

                <div className="space-y-2">
                  <label
                    htmlFor="community-content"
                    className="text-sm font-medium"
                  >
                    내용
                  </label>

                  <textarea
                    id="community-content"
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    maxLength={5000}
                    rows={7}
                    placeholder="내용을 입력하세요"
                    className="w-full resize-none rounded-md border border-border bg-background px-3 py-3 text-sm outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-foreground"
                  />
                </div>

                {createPostMutation.isError && (
                  <p className="text-sm text-destructive">
                    게시글 등록에 실패했습니다.
                  </p>
                )}

                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowWriteForm(false)}
                    disabled={createPostMutation.isPending}
                  >
                    취소
                  </Button>

                  <Button
                    type="button"
                    variant="accent"
                    disabled={
                      createPostMutation.isPending ||
                      !category.trim() ||
                      !title.trim() ||
                      !content.trim()
                    }
                    onClick={() =>
                      createPostMutation.mutate({
                        category: category.trim(),
                        title: title.trim(),
                        content: content.trim(),
                      })
                    }
                  >
                    {createPostMutation.isPending ? "등록 중..." : "등록"}
                  </Button>
                </div>
              </div>
            </div>
          )}
          <div className="mt-6 overflow-hidden rounded-lg border border-border bg-card">
            {/* Table Header */}
            <div className="grid grid-cols-[120px_1fr_160px_120px] border-b border-border bg-muted/40 px-5 py-3 text-xs font-semibold tracking-wide text-muted-foreground">
              <span>카테고리</span>
              <span>제목</span>
              <span>작성자</span>
              <span>작성일</span>
            </div>

            {/* Loading */}
            {postsQuery.isLoading && (
              <div className="px-5 py-10 text-center text-sm text-muted-foreground">
                게시글을 불러오는 중...
              </div>
            )}

            {/* Error */}
            {postsQuery.isError && (
              <div className="px-5 py-10 text-center text-sm text-destructive">
                게시글을 불러오지 못했습니다.
              </div>
            )}

            {/* Empty */}
            {postsQuery.data?.length === 0 && (
              <div className="px-5 py-10 text-center text-sm text-muted-foreground">
                아직 게시글이 없습니다.
              </div>
            )}

            {/* Posts */}
            {postsQuery.data?.map((post: CommunityPost) => (
              <Link
                key={post.post_id}
                href={`/community/${post.post_id}`}
                className="grid w-full grid-cols-[120px_1fr_160px_120px] items-center border-b border-border px-5 py-4 text-left transition-colors last:border-b-0 hover:bg-muted/40"
              >
                <span className="text-xs text-muted-foreground">
                  {post.category}
                </span>

                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-sm font-medium">
                    {post.title}
                  </span>

                  {post.comment_count > 0 && (
                    <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
                      <MessageSquare className="h-3 w-3" />
                      {post.comment_count}
                    </span>
                  )}
                </div>

                <span className="text-xs text-muted-foreground">
                  {post.company_name}
                </span>

                <span className="text-xs text-muted-foreground">
                  {new Date(post.created_at * 1000).toLocaleDateString("ko-KR")}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Inquiry */}
      {activeTab === "inquiry" && (
        <section className="mt-8">
          <div className="flex items-end justify-between">
            <div>
              <h2 className="text-xl font-semibold">Q&A / 문의</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                서비스 이용 중 궁금한 점을 AD STUDIO 운영팀에 문의하세요.
              </p>
            </div>

            <Button
              variant="accent"
              size="sm"
              onClick={() => setShowInquiryForm((prev) => !prev)}
            >
              <Plus className="h-4 w-4" />
              {showInquiryForm ? "닫기" : "문의하기"}
            </Button>
          </div>
          {showInquiryForm && (
            <div className="mt-6 rounded-lg border border-border bg-card p-6">
              <div className="grid gap-5">
                <div className="space-y-2">
                  <label
                    htmlFor="inquiry-title"
                    className="text-sm font-medium"
                  >
                    제목
                  </label>

                  <input
                    id="inquiry-title"
                    type="text"
                    value={inquiryTitle}
                    onChange={(e) => setInquiryTitle(e.target.value)}
                    maxLength={200}
                    placeholder="문의 제목을 입력하세요"
                    className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-foreground"
                  />
                </div>

                <div className="space-y-2">
                  <label
                    htmlFor="inquiry-content"
                    className="text-sm font-medium"
                  >
                    문의 내용
                  </label>

                  <textarea
                    id="inquiry-content"
                    value={inquiryContent}
                    onChange={(e) => setInquiryContent(e.target.value)}
                    maxLength={5000}
                    rows={7}
                    placeholder="문의 내용을 입력하세요"
                    className="w-full resize-none rounded-md border border-border bg-background px-3 py-3 text-sm outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-foreground"
                  />
                </div>

                {createInquiryMutation.isError && (
                  <p className="text-sm text-destructive">
                    문의 등록에 실패했습니다.
                  </p>
                )}

                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowInquiryForm(false)}
                    disabled={createInquiryMutation.isPending}
                  >
                    취소
                  </Button>

                  <Button
                    type="button"
                    variant="accent"
                    disabled={
                      createInquiryMutation.isPending ||
                      !inquiryTitle.trim() ||
                      !inquiryContent.trim()
                    }
                    onClick={() =>
                      createInquiryMutation.mutate({
                        title: inquiryTitle.trim(),
                        content: inquiryContent.trim(),
                      })
                    }
                  >
                    {createInquiryMutation.isPending ? "등록 중..." : "등록"}
                  </Button>
                </div>
              </div>
            </div>
          )}
          <div className="mt-6 overflow-hidden rounded-lg border border-border bg-card">
            {/* Table Header */}
            <div className="grid grid-cols-[140px_1fr_140px] border-b border-border bg-muted/40 px-5 py-3 text-xs font-semibold tracking-wide text-muted-foreground">
              <span>상태</span>
              <span>제목</span>
              <span>작성일</span>
            </div>

            {/* Loading */}
            {inquiriesQuery.isLoading && (
              <div className="px-5 py-10 text-center text-sm text-muted-foreground">
                문의를 불러오는 중...
              </div>
            )}

            {/* Error */}
            {inquiriesQuery.isError && (
              <div className="px-5 py-10 text-center text-sm text-destructive">
                문의를 불러오지 못했습니다.
              </div>
            )}

            {/* Empty */}
            {inquiriesQuery.data?.length === 0 && (
              <div className="px-5 py-10 text-center text-sm text-muted-foreground">
                아직 등록한 문의가 없습니다.
              </div>
            )}
            {/* Inquiries */}
            {inquiriesQuery.data?.map((inquiry: Inquiry) => (
              <Link
                key={inquiry.inquiry_id}
                href={`/community/inquiries/${inquiry.inquiry_id}`}
                className="grid w-full grid-cols-[140px_1fr_140px] items-center border-b border-border px-5 py-4 text-left transition-colors last:border-b-0 hover:bg-muted/40"
              >
                <div>
                  <span
                    className={cn(
                      "inline-flex rounded-full border px-2.5 py-1 text-xs font-medium",
                      inquiry.status === "answered"
                        ? "border-foreground bg-foreground text-background"
                        : "border-border text-muted-foreground",
                    )}
                  >
                    {inquiry.status === "answered" ? "답변완료" : "답변대기"}
                  </span>
                </div>

                <span className="text-sm font-medium">{inquiry.title}</span>

                <span className="text-xs text-muted-foreground">
                  {new Date(inquiry.created_at * 1000).toLocaleDateString(
                    "ko-KR",
                  )}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default function CommunityPage() {
  return (
    <RequireAuth>
      <CommunityContent />
    </RequireAuth>
  );
}

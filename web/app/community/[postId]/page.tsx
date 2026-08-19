"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, MessageSquare } from "lucide-react";

import { RequireAuth } from "@/components/auth/require-auth";
import { Button } from "@/components/ui/button";
import { createCommunityComment, getCommunityPost } from "@/lib/api/community";
import { formatCreatedAt } from "@/lib/utils";

function CommunityPostContent({ postId }: { postId: string }) {
  const [comment, setComment] = useState("");
  const queryClient = useQueryClient();

  const postQuery = useQuery({
    queryKey: ["community-post", postId],
    queryFn: () => getCommunityPost(postId),
  });

  const commentMutation = useMutation({
    mutationFn: () => createCommunityComment(postId, comment.trim()),
    onSuccess: async () => {
      setComment("");

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["community-post", postId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["community-posts"],
        }),
      ]);
    },
  });

  if (postQuery.isLoading) {
    return (
      <div className="mx-auto w-full max-w-[1000px] px-8 py-12">
        <p className="text-sm text-muted-foreground">게시글을 불러오는 중...</p>
      </div>
    );
  }

  if (postQuery.isError || !postQuery.data) {
    return (
      <div className="mx-auto w-full max-w-[1000px] px-8 py-12">
        <p className="text-sm text-destructive">
          게시글을 불러오지 못했습니다.
        </p>
      </div>
    );
  }

  const post = postQuery.data;

  return (
    <div className="mx-auto w-full max-w-[1000px] px-8 py-12">
      <Link
        href="/community"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        COMMUNITY BOARD
      </Link>

      <article className="mt-8 rounded-lg border border-border bg-card">
        <div className="border-b border-border p-6">
          <span className="text-xs font-medium text-muted-foreground">
            {post.category}
          </span>

          <h1 className="mt-2 text-2xl font-semibold">{post.title}</h1>

          <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
            <span>{post.company_name}</span>
            <span>·</span>
            <span>{formatCreatedAt(post.created_at)}</span>
          </div>
        </div>

        <div className="min-h-[220px] whitespace-pre-wrap p-6 text-sm leading-7">
          {post.content}
        </div>
      </article>

      <section className="mt-8">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4" />
          <h2 className="text-lg font-semibold">댓글 {post.comment_count}</h2>
        </div>

        <div className="mt-4 space-y-3">
          {post.comments.length === 0 ? (
            <div className="rounded-lg border border-border bg-card px-5 py-8 text-center text-sm text-muted-foreground">
              아직 댓글이 없습니다.
            </div>
          ) : (
            post.comments.map((item) => (
              <div
                key={item.comment_id}
                className="rounded-lg border border-border bg-card p-5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">
                    {item.company_name}
                  </span>

                  <span className="text-xs text-muted-foreground">
                    {formatCreatedAt(item.created_at)}
                  </span>
                </div>

                <p className="mt-3 whitespace-pre-wrap text-sm leading-6">
                  {item.content}
                </p>
              </div>
            ))
          )}
        </div>

        <div className="mt-6 rounded-lg border border-border bg-card p-5">
          <label htmlFor="community-comment" className="text-sm font-medium">
            댓글 작성
          </label>

          <textarea
            id="community-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={1000}
            rows={4}
            placeholder="댓글을 입력하세요"
            className="mt-2 w-full resize-none rounded-md border border-border bg-background px-3 py-3 text-sm outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-foreground"
          />

          {commentMutation.isError && (
            <p className="mt-2 text-sm text-destructive">
              댓글 등록에 실패했습니다.
            </p>
          )}

          <div className="mt-3 flex justify-end">
            <Button
              variant="accent"
              disabled={commentMutation.isPending || !comment.trim()}
              onClick={() => commentMutation.mutate()}
            >
              {commentMutation.isPending ? "등록 중..." : "댓글 등록"}
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}

export default function CommunityPostPage({
  params,
}: {
  params: Promise<{ postId: string }>;
}) {
  const { postId } = use(params);

  return (
    <RequireAuth>
      <CommunityPostContent postId={postId} />
    </RequireAuth>
  );
}

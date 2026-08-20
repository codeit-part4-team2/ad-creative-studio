import { apiFetch } from "./client";

export type CommunityPost = {
  post_id: string;
  customer_id: string;
  company_name: string;
  category: string;
  title: string;
  content: string;
  created_at: number;
  comment_count: number;
};

export type CommunityPostCreate = {
  category: string;
  title: string;
  content: string;
};

export type CommunityComment = {
  comment_id: string;
  customer_id: string;
  company_name: string;
  content: string;
  created_at: number;
};

export type CommunityPostDetail = CommunityPost & {
  comments: CommunityComment[];
};

export async function getCommunityPosts(): Promise<CommunityPost[]> {
  return apiFetch("/api/v1/community/posts");
}

export async function getCommunityPost(
  postId: string,
): Promise<CommunityPostDetail> {
  return apiFetch(`/api/v1/community/posts/${postId}`);
}

export async function createCommunityPost(
  input: CommunityPostCreate,
): Promise<CommunityPost> {
  return apiFetch("/api/v1/community/posts", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function createCommunityComment(
  postId: string,
  content: string,
): Promise<CommunityComment> {
  return apiFetch(`/api/v1/community/posts/${postId}/comments`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

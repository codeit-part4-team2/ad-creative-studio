import time
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.backend.api.deps import get_current_customer
from app.backend.schemas.community import (
    CommunityCommentCreate,
    CommunityCommentResponse,
    CommunityPostCreate,
    CommunityPostDetailResponse,
    CommunityPostResponse,
)
from app.backend.services import store
from app.backend.services.store import COMMUNITY_POSTS


router = APIRouter(prefix="/api/v1/community", tags=["community"])


@router.get("/posts", response_model=list[CommunityPostResponse])
async def get_posts(
    customer: dict = Depends(get_current_customer),
):
    # Community는 로그인한 사용자라면 다른 고객사의 게시글도 볼 수 있다.
    return sorted(
        COMMUNITY_POSTS,
        key=lambda post: post["created_at"],
        reverse=True,
    )


@router.get("/posts/{post_id}", response_model=CommunityPostDetailResponse,)
async def get_post(
    post_id: str,
    customer: dict = Depends(get_current_customer),
):
    for post in COMMUNITY_POSTS:
        if post["post_id"] == post_id:
            post.setdefault("comments",[])
            post["comment_count"] = len(post["comments"])
            return post

    raise HTTPException(status_code=404, detail="community post not found")


@router.post(
    "/posts",
    response_model=CommunityPostResponse,
    status_code=201,
)
async def create_post(
    body: CommunityPostCreate,
    customer: dict = Depends(get_current_customer),
):
    post = {
        "post_id": f"post_{uuid.uuid4().hex[:12]}",
        "customer_id": customer["customer_id"],
        "company_name": customer["company_name"],
        "category": body.category,
        "title": body.title,
        "content": body.content,
        "created_at": time.time(),
        "comment_count": 0,
        "comments": [],
    }

    COMMUNITY_POSTS.append(post)
    store.save()

    return post

@router.post(
    "/posts/{post_id}/comments",
    response_model=CommunityCommentResponse,
    status_code=201,
)
async def create_comment(
    post_id: str,
    body: CommunityCommentCreate,
    customer: dict = Depends(get_current_customer),
):
    for post in COMMUNITY_POSTS:
        if post["post_id"] != post_id:
            continue

        comments = post.setdefault("comments", [])

        comment = {
            "comment_id": f"comment_{uuid.uuid4().hex[:12]}",
            "customer_id": customer["customer_id"],
            "company_name": customer["company_name"],
            "content": body.content,
            "created_at": time.time(),
        }

        comments.append(comment)
        post["comment_count"] = len(comments)

        store.save()

        return comment

    raise HTTPException(status_code=404, detail="community post not found")
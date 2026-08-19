from pydantic import BaseModel, Field


class CommunityPostCreate(BaseModel):
    category: str = Field(min_length=1, max_length=30)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)


class CommunityCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class CommunityCommentResponse(BaseModel):
    comment_id: str
    customer_id: str
    company_name: str
    content: str
    created_at: float


class CommunityPostResponse(BaseModel):
    post_id: str
    customer_id: str
    company_name: str
    category: str
    title: str
    content: str
    created_at: float
    comment_count: int = 0


class CommunityPostDetailResponse(CommunityPostResponse):
    comments: list[CommunityCommentResponse] = []
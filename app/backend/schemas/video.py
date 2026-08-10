from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class RenderStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PublishStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    SCHEDULED = "scheduled"
    FAILED = "failed"
    AUTH_REQUIRED = "auth_required"
    NEEDS_REVIEW = "needs_review"
    SCHEDULE_EXPIRED = "schedule_expired"


class VideoJob(BaseModel):
    video_job_id: str
    result_id: str
    product_id: str
    tone: Literal["emotional", "modern", "practical", "premium"]
    time_slot: Literal["commute_am", "commute_pm"]
    render_status: RenderStatus = RenderStatus.QUEUED
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    publish_status: PublishStatus = PublishStatus.NOT_REQUESTED
    video_url: str | None = None
    video_sha256: str | None = None
    source_fingerprint: str
    music_key: str | None = None
    music_warning: str | None = None
    silent_publish_confirmed: bool = False
    activation_at: datetime | None = None
    approved_at: datetime | None = None
    youtube_video_id: str | None = None
    youtube_error: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class VideoCreateRequest(BaseModel):
    result_id: str


class VideoCreateResponse(BaseModel):
    video_job_id: str
    render_status: RenderStatus


class VideoApprovalRequest(BaseModel):
    activation_at: datetime
    publish_to_youtube: bool = False
    allow_silent: bool = False


class YouTubeStatusResponse(BaseModel):
    configured: bool
    connection_id: str
    token_available: bool

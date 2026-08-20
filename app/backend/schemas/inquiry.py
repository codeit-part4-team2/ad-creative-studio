from pydantic import BaseModel, Field


class InquiryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)


class InquiryAnswerCreate(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)


class InquiryResponse(BaseModel):
    inquiry_id: str
    customer_id: str
    company_name: str

    title: str
    content: str

    status: str

    answer: str | None = None
    answered_at: float | None = None

    created_at: float
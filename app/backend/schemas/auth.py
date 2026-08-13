from pydantic import BaseModel


class CustomerCreateRequest(BaseModel):
    customer_id: str
    company_name: str
    pin: str
    plan: str = "basic"


class CustomerResponse(BaseModel):
    customer_id: str
    company_name: str
    status: str
    plan: str


class LoginRequest(BaseModel):
    customer_id: str
    pin: str


class LoginResponse(BaseModel):
    token: str
    customer: CustomerResponse

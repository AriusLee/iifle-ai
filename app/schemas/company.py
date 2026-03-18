import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class CompanyCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=500)
    brand_name: str | None = None
    registration_number: str | None = None
    date_of_incorporation: date | None = None
    company_type: str | None = None
    primary_industry: str | None = None
    sub_industry: str | None = None
    country: str = "Malaysia"
    website: str | None = None
    brief_description: str | None = None


class CompanyUpdate(BaseModel):
    legal_name: str | None = None
    brand_name: str | None = None
    registration_number: str | None = None
    date_of_incorporation: date | None = None
    company_type: str | None = None
    primary_industry: str | None = None
    sub_industry: str | None = None
    country: str | None = None
    website: str | None = None
    brief_description: str | None = None
    enterprise_stage: str | None = None
    status: str | None = None


class CompanyResponse(BaseModel):
    id: uuid.UUID
    legal_name: str
    brand_name: str | None
    registration_number: str | None
    date_of_incorporation: date | None
    company_type: str | None
    primary_industry: str | None
    sub_industry: str | None
    country: str
    website: str | None
    brief_description: str | None
    enterprise_stage: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

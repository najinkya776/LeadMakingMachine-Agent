from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, EmailStr, HttpUrl


class LeadResponse(BaseModel):
    id: int
    business_name: str
    category: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    website_url: Optional[str] = None
    google_rating: Optional[float] = None
    review_count: Optional[int] = None
    lead_type: Optional[str] = None
    status: str = "pending"
    opportunity_score: Optional[float] = None
    classification: Optional[str] = None
    created_at: datetime


class LeadListResponse(BaseModel):
    leads: List[LeadResponse]
    total: int
    page: int = 1
    per_page: int = 50


class AuditEntry(BaseModel):
    timestamp: datetime
    action: str
    details: Optional[str] = None


class ReportEntry(BaseModel):
    generated_at: datetime
    content: Optional[str] = None
    status: str


class LeadDetail(LeadResponse):
    audit_trail: List[AuditEntry] = Field(default_factory=list)
    reports: List[ReportEntry] = Field(default_factory=list)
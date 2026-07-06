"""Report data model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class ReportStatus(str, Enum):
    """Report generation status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    SENT = "sent"


class PricingTier(str, Enum):
    """Pricing tier for web development services."""
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"


class Pricing(BaseModel):
    """Pricing tiers for web development."""
    basic: str = "15,000 - 25,000"
    standard: str = "30,000 - 50,000"
    premium: str = "60,000 - 1,50,000"


class Report(BaseModel):
    """Report data model for lead outreach."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str

    # Opportunity scoring
    opportunity_score: int
    classification: str  # high, medium, low
    lead_type: str

    # Pitch content
    pitch_type: str
    pitch_content: str
    executive_summary: Optional[str] = None

    # Outreach messages
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    whatsapp_message: Optional[str] = None

    # PDF
    pdf_path: Optional[str] = None
    pdf_generated: bool = False

    # Status tracking
    status: ReportStatus = ReportStatus.PENDING
    email_sent: bool = False
    email_sent_at: Optional[datetime] = None

    # Pricing
    pricing_tier: Optional[PricingTier] = None
    pricing_estimate: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "opportunity_score": self.opportunity_score,
            "classification": self.classification,
            "lead_type": self.lead_type,
            "pitch_type": self.pitch_type,
            "pitch_content": self.pitch_content,
            "executive_summary": self.executive_summary,
            "email_subject": self.email_subject,
            "email_body": self.email_body,
            "whatsapp_message": self.whatsapp_message,
            "pdf_path": self.pdf_path,
            "pdf_generated": self.pdf_generated,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "email_sent": self.email_sent,
            "email_sent_at": self.email_sent_at.isoformat() if self.email_sent_at else None,
            "pricing_tier": self.pricing_tier.value if self.pricing_tier and isinstance(self.pricing_tier, Enum) else self.pricing_tier,
            "pricing_estimate": self.pricing_estimate,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Report":
        """Create Report from dictionary."""
        if "status" in data and isinstance(data["status"], str):
            data["status"] = ReportStatus(data["status"])
        if "pricing_tier" in data and isinstance(data["pricing_tier"], str):
            data["pricing_tier"] = PricingTier(data["pricing_tier"])
        return cls(**data)


class OutreachMessage(BaseModel):
    """Structured outreach message."""
    channel: str  # email, whatsapp, sms
    subject: Optional[str] = None
    body: str
    template_used: str
    personalization_data: dict = {}
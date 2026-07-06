"""Lead data model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class LeadStatus(str, Enum):
    """Lead processing status."""
    RAW = "raw"
    QUALIFIED = "qualified"
    AUDITING = "auditing"
    SCORED = "scored"
    PITCHING = "pitching"
    COMPLETED = "completed"
    FAILED = "failed"


class LeadType(str, Enum):
    """Lead type classification."""
    NO_WEBSITE = "no_website"
    HAS_WEBSITE = "has_website"
    SOCIAL_ONLY = "social_only"


class SocialHandles(BaseModel):
    """Social media handles for a business."""
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    twitter: Optional[str] = None
    linkedin: Optional[str] = None
    youtube: Optional[str] = None


class Lead(BaseModel):
    """Lead data model representing a potential client business."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    business_name: str
    category: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website_url: Optional[str] = None
    google_rating: Optional[float] = None
    review_count: Optional[int] = None
    photos_count: Optional[int] = None
    business_hours: Optional[str] = None
    social_handles: Optional[SocialHandles] = None
    source: str = "google_maps"
    status: LeadStatus = LeadStatus.RAW
    lead_type: Optional[LeadType] = None
    reachability_score: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "business_name": self.business_name,
            "category": self.category,
            "address": self.address,
            "phone": self.phone,
            "email": self.email,
            "website_url": self.website_url,
            "google_rating": self.google_rating,
            "review_count": self.review_count,
            "photos_count": self.photos_count,
            "business_hours": self.business_hours,
            "social_handles": self.social_handles.model_dump_json() if self.social_handles else None,
            "source": self.source,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "lead_type": self.lead_type.value if self.lead_type and isinstance(self.lead_type, Enum) else self.lead_type,
            "reachability_score": self.reachability_score,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Lead":
        """Create Lead from dictionary."""
        if "social_handles" in data and isinstance(data["social_handles"], str):
            data["social_handles"] = SocialHandles.model_validate_json(data["social_handles"])
        if "status" in data and isinstance(data["status"], str):
            data["status"] = LeadStatus(data["status"])
        if "lead_type" in data and isinstance(data["lead_type"], str):
            data["lead_type"] = LeadType(data["lead_type"])
        return cls(**data)


class LeadBatch(BaseModel):
    """Batch of leads for processing."""
    leads: list[Lead]
    total_count: int
    qualified_count: int = 0
    source: str = "google_maps"
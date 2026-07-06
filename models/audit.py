"""Audit data model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class DesignQuality(str, Enum):
    """Design quality assessment."""
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    VERY_POOR = "very_poor"


class AuditScore(BaseModel):
    """Individual audit scores."""
    page_speed: int = 0
    mobile: int = 0
    seo: int = 0
    design: int = 0

    def overall(self) -> float:
        """Calculate overall audit score."""
        return (self.page_speed + self.mobile + self.seo + self.design) / 4


class Audit(BaseModel):
    """Website audit data model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str
    website_url: str

    # Core metrics
    page_speed_score: Optional[int] = None
    mobile_score: Optional[int] = None
    https_enabled: bool = False

    # SEO metrics
    seo_score: Optional[int] = None
    has_sitemap: bool = False
    has_robots_txt: bool = False
    meta_tags_complete: bool = False

    # Technical issues
    broken_links_count: int = 0
    missing_images_count: int = 0

    # Tech stack detection
    tech_stack: Optional[str] = None
    cms_type: Optional[str] = None
    is_wordpress: bool = False
    is_wix: bool = False
    is_shopify: bool = False

    # Content assessment
    design_quality: Optional[DesignQuality] = None
    has_contact_form: bool = False
    has_cta: bool = False
    has_whatsapp: bool = False
    last_updated: Optional[str] = None

    # Social integration
    has_facebook_widget: bool = False
    has_instagram_feed: bool = False

    # Detailed audit data
    audit_data: Optional[dict] = None
    screenshots: Optional[list[str]] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "website_url": self.website_url,
            "page_speed_score": self.page_speed_score,
            "mobile_score": self.mobile_score,
            "https_enabled": self.https_enabled,
            "seo_score": self.seo_score,
            "has_sitemap": self.has_sitemap,
            "has_robots_txt": self.has_robots_txt,
            "meta_tags_complete": self.meta_tags_complete,
            "broken_links_count": self.broken_links_count,
            "missing_images_count": self.missing_images_count,
            "tech_stack": self.tech_stack,
            "cms_type": self.cms_type,
            "is_wordpress": self.is_wordpress,
            "is_wix": self.is_wix,
            "is_shopify": self.is_shopify,
            "design_quality": self.design_quality.value if self.design_quality and isinstance(self.design_quality, Enum) else self.design_quality,
            "has_contact_form": self.has_contact_form,
            "has_cta": self.has_cta,
            "has_whatsapp": self.has_whatsapp,
            "last_updated": self.last_updated,
            "audit_data": str(self.audit_data) if self.audit_data else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Audit":
        """Create Audit from dictionary."""
        if "audit_data" in data and isinstance(data["audit_data"], str):
            import json
            try:
                data["audit_data"] = json.loads(data["audit_data"])
            except:
                data["audit_data"] = None
        return cls(**data)


class AuditSummary(BaseModel):
    """Summary of audit for reporting."""
    audit: Audit
    overall_score: int
    issues_count: int
    critical_issues: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []
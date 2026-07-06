"""Lead management API endpoints."""

from datetime import datetime
from typing import Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models import Lead, LeadStatus, LeadType, Audit, Report


router = APIRouter(prefix="/api/leads", tags=["leads"])


# =============================================================================
# Response Schemas
# =============================================================================

class SocialHandlesResponse(BaseModel):
    """Social media handles response."""
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    twitter: Optional[str] = None
    linkedin: Optional[str] = None
    youtube: Optional[str] = None


class LeadResponse(BaseModel):
    """Lead response schema."""
    id: str
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
    social_handles: Optional[SocialHandlesResponse] = None
    source: str = "google_maps"
    status: str
    lead_type: Optional[str] = None
    reachability_score: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class AuditResponse(BaseModel):
    """Audit response schema."""
    id: str
    lead_id: str
    website_url: str
    page_speed_score: Optional[int] = None
    mobile_score: Optional[int] = None
    https_enabled: bool = False
    seo_score: Optional[int] = None
    has_sitemap: bool = False
    has_robots_txt: bool = False
    meta_tags_complete: bool = False
    broken_links_count: int = 0
    missing_images_count: int = 0
    tech_stack: Optional[str] = None
    cms_type: Optional[str] = None
    is_wordpress: bool = False
    is_wix: bool = False
    is_shopify: bool = False
    design_quality: Optional[str] = None
    has_contact_form: bool = False
    has_cta: bool = False
    has_whatsapp: bool = False
    last_updated: Optional[str] = None
    created_at: datetime


class ReportResponse(BaseModel):
    """Report response schema."""
    id: str
    lead_id: str
    opportunity_score: int
    classification: str
    lead_type: str
    pitch_type: str
    pitch_content: str
    executive_summary: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    whatsapp_message: Optional[str] = None
    pdf_path: Optional[str] = None
    pdf_generated: bool = False
    status: str
    email_sent: bool = False
    email_sent_at: Optional[datetime] = None
    pricing_tier: Optional[str] = None
    pricing_estimate: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LeadDetailResponse(BaseModel):
    """Lead detail response with audit and report."""
    lead: LeadResponse
    audit: Optional[AuditResponse] = None
    report: Optional[ReportResponse] = None


class LeadListResponse(BaseModel):
    """Paginated lead list response."""
    leads: list[LeadResponse]
    total: int
    limit: int
    offset: int


class LeadStatsResponse(BaseModel):
    """Lead statistics response."""
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    avg_score: Optional[float] = None
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int


# =============================================================================
# Database Helpers
# =============================================================================

def get_leads_from_db(
    status: Optional[str] = None,
    lead_type: Optional[str] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Lead], int]:
    """Fetch leads from database with filters."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        # Build query
        base_query = "SELECT * FROM leads WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM leads WHERE 1=1"
        params = []
        param_idx = 1

        if status:
            base_query += f" AND status = ${param_idx}"
            count_query += f" AND status = ${param_idx}"
            params.append(status)
            param_idx += 1

        if lead_type:
            base_query += f" AND lead_type = ${param_idx}"
            count_query += f" AND lead_type = ${param_idx}"
            params.append(lead_type)
            param_idx += 1

        if search:
            base_query += f" AND (business_name ILIKE ${param_idx} OR address ILIKE ${param_idx})"
            count_query += f" AND (business_name ILIKE ${param_idx} OR address ILIKE ${param_idx})"
            params.append(f"%{search}%")
            param_idx += 1

        if min_score is not None:
            base_query += f" AND reachability_score >= ${param_idx}"
            count_query += f" AND reachability_score >= ${param_idx}"
            params.append(min_score)
            param_idx += 1

        if max_score is not None:
            base_query += f" AND reachability_score <= ${param_idx}"
            count_query += f" AND reachability_score <= ${param_idx}"
            params.append(max_score)
            param_idx += 1

        # Get total count
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Add pagination
        base_query += f" ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])

        cursor.execute(base_query, params)
        rows = cursor.fetchall()

        leads = []
        for row in rows:
            data = {
                "id": row[0],
                "business_name": row[1],
                "category": row[2],
                "address": row[3],
                "phone": row[4],
                "email": row[5],
                "website_url": row[6],
                "google_rating": row[7],
                "review_count": row[8],
                "photos_count": row[9],
                "business_hours": row[10],
                "social_handles": row[11],
                "source": row[12],
                "status": row[13],
                "lead_type": row[14],
                "reachability_score": row[15],
                "created_at": row[16],
                "updated_at": row[17],
            }
            leads.append(Lead.from_dict(data))

        cursor.close()
        conn.close()

        return leads, total

    except Exception as e:
        # Fallback to empty result on connection error
        return [], 0


def get_audit_for_lead(lead_id: str) -> Optional[Audit]:
    """Get audit for a lead."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM audits WHERE lead_id = %s ORDER BY created_at DESC LIMIT 1",
            (lead_id,)
        )
        row = cursor.fetchone()

        if row:
            data = {
                "id": row[0],
                "lead_id": row[1],
                "website_url": row[2],
                "page_speed_score": row[3],
                "mobile_score": row[4],
                "https_enabled": row[5],
                "seo_score": row[6],
                "has_sitemap": row[7],
                "has_robots_txt": row[8],
                "meta_tags_complete": row[9],
                "broken_links_count": row[10],
                "missing_images_count": row[11],
                "tech_stack": row[12],
                "cms_type": row[13],
                "is_wordpress": row[14],
                "is_wix": row[15],
                "is_shopify": row[16],
                "design_quality": row[17],
                "has_contact_form": row[18],
                "has_cta": row[19],
                "has_whatsapp": row[20],
                "last_updated": row[21],
                "created_at": row[22],
            }
            cursor.close()
            conn.close()
            return Audit.from_dict(data)

        cursor.close()
        conn.close()
        return None

    except Exception:
        return None


def get_report_for_lead(lead_id: str) -> Optional[Report]:
    """Get report for a lead."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM reports WHERE lead_id = %s ORDER BY created_at DESC LIMIT 1",
            (lead_id,)
        )
        row = cursor.fetchone()

        if row:
            data = {
                "id": row[0],
                "lead_id": row[1],
                "opportunity_score": row[2],
                "classification": row[3],
                "lead_type": row[4],
                "pitch_type": row[5],
                "pitch_content": row[6],
                "executive_summary": row[7],
                "email_subject": row[8],
                "email_body": row[9],
                "whatsapp_message": row[10],
                "pdf_path": row[11],
                "pdf_generated": row[12],
                "status": row[13],
                "email_sent": row[14],
                "email_sent_at": row[15],
                "pricing_tier": row[16],
                "pricing_estimate": row[17],
                "created_at": row[18],
                "updated_at": row[19],
            }
            cursor.close()
            conn.close()
            return Report.from_dict(data)

        cursor.close()
        conn.close()
        return None

    except Exception:
        return None


def get_lead_stats() -> LeadStatsResponse:
    """Get lead statistics."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        # Get total
        cursor.execute("SELECT COUNT(*) FROM leads")
        total = cursor.fetchone()[0]

        # Get by status
        cursor.execute("SELECT status, COUNT(*) FROM leads GROUP BY status")
        by_status = {row[0]: row[1] for row in cursor.fetchall()}

        # Get by type
        cursor.execute("SELECT lead_type, COUNT(*) FROM leads WHERE lead_type IS NOT NULL GROUP BY lead_type")
        by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Get average score
        cursor.execute("SELECT AVG(reachability_score) FROM leads WHERE reachability_score IS NOT NULL")
        avg_score = cursor.fetchone()[0]

        # Get priority counts
        cursor.execute("SELECT COUNT(*) FROM leads WHERE reachability_score >= 80")
        high_priority = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE reachability_score >= 50 AND reachability_score < 80")
        medium_priority = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE reachability_score < 50 AND reachability_score IS NOT NULL")
        low_priority = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return LeadStatsResponse(
            total=total,
            by_status=by_status,
            by_type=by_type,
            avg_score=avg_score,
            high_priority_count=high_priority,
            medium_priority_count=medium_priority,
            low_priority_count=low_priority,
        )

    except Exception as e:
        return LeadStatsResponse(
            total=0,
            by_status={},
            by_type={},
            avg_score=None,
            high_priority_count=0,
            medium_priority_count=0,
            low_priority_count=0,
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=LeadListResponse)
def list_leads(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    lead_type: Optional[str] = Query(default=None, description="Filter by lead type"),
    min_score: Optional[int] = Query(default=None, ge=0, le=100, description="Minimum score filter"),
    max_score: Optional[int] = Query(default=None, ge=0, le=100, description="Maximum score filter"),
    search: Optional[str] = Query(default=None, description="Search in business name/address"),
):
    """List all leads with pagination and filters."""
    leads, total = get_leads_from_db(
        status=status,
        lead_type=lead_type,
        min_score=min_score,
        max_score=max_score,
        search=search,
        limit=limit,
        offset=offset,
    )

    return LeadListResponse(
        leads=[
            LeadResponse(
                id=lead.id,
                business_name=lead.business_name,
                category=lead.category,
                address=lead.address,
                phone=lead.phone,
                email=lead.email,
                website_url=lead.website_url,
                google_rating=lead.google_rating,
                review_count=lead.review_count,
                photos_count=lead.photos_count,
                business_hours=lead.business_hours,
                social_handles=SocialHandlesResponse(**lead.social_handles.model_dump()) if lead.social_handles else None,
                source=lead.source,
                status=lead.status.value if hasattr(lead.status, 'value') else lead.status,
                lead_type=lead.lead_type.value if hasattr(lead.lead_type, 'value') else lead.lead_type,
                reachability_score=lead.reachability_score,
                created_at=lead.created_at,
                updated_at=lead.updated_at,
            )
            for lead in leads
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=LeadStatsResponse)
def get_lead_statistics():
    """Get lead statistics for dashboard KPI cards."""
    return get_lead_stats()


@router.get("/{lead_id}", response_model=LeadDetailResponse)
def get_lead(lead_id: str):
    """Get a single lead with its audit and report."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM leads WHERE id = %s", (lead_id,))
        row = cursor.fetchone()

        if not row:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")

        data = {
            "id": row[0],
            "business_name": row[1],
            "category": row[2],
            "address": row[3],
            "phone": row[4],
            "email": row[5],
            "website_url": row[6],
            "google_rating": row[7],
            "review_count": row[8],
            "photos_count": row[9],
            "business_hours": row[10],
            "social_handles": row[11],
            "source": row[12],
            "status": row[13],
            "lead_type": row[14],
            "reachability_score": row[15],
            "created_at": row[16],
            "updated_at": row[17],
        }

        lead = Lead.from_dict(data)

        cursor.close()
        conn.close()

        # Get associated audit and report
        audit = get_audit_for_lead(lead_id)
        report = get_report_for_lead(lead_id)

        return LeadDetailResponse(
            lead=LeadResponse(
                id=lead.id,
                business_name=lead.business_name,
                category=lead.category,
                address=lead.address,
                phone=lead.phone,
                email=lead.email,
                website_url=lead.website_url,
                google_rating=lead.google_rating,
                review_count=lead.review_count,
                photos_count=lead.photos_count,
                business_hours=lead.business_hours,
                social_handles=SocialHandlesResponse(**lead.social_handles.model_dump()) if lead.social_handles else None,
                source=lead.source,
                status=lead.status.value if hasattr(lead.status, 'value') else lead.status,
                lead_type=lead.lead_type.value if hasattr(lead.lead_type, 'value') else lead.lead_type,
                reachability_score=lead.reachability_score,
                created_at=lead.created_at,
                updated_at=lead.updated_at,
            ),
            audit=AuditResponse(
                id=audit.id,
                lead_id=audit.lead_id,
                website_url=audit.website_url,
                page_speed_score=audit.page_speed_score,
                mobile_score=audit.mobile_score,
                https_enabled=audit.https_enabled,
                seo_score=audit.seo_score,
                has_sitemap=audit.has_sitemap,
                has_robots_txt=audit.has_robots_txt,
                meta_tags_complete=audit.meta_tags_complete,
                broken_links_count=audit.broken_links_count,
                missing_images_count=audit.missing_images_count,
                tech_stack=audit.tech_stack,
                cms_type=audit.cms_type,
                is_wordpress=audit.is_wordpress,
                is_wix=audit.is_wix,
                is_shopify=audit.is_shopify,
                design_quality=audit.design_quality.value if hasattr(audit.design_quality, 'value') else audit.design_quality,
                has_contact_form=audit.has_contact_form,
                has_cta=audit.has_cta,
                has_whatsapp=audit.has_whatsapp,
                last_updated=audit.last_updated,
                created_at=audit.created_at,
            ) if audit else None,
            report=ReportResponse(
                id=report.id,
                lead_id=report.lead_id,
                opportunity_score=report.opportunity_score,
                classification=report.classification,
                lead_type=report.lead_type,
                pitch_type=report.pitch_type,
                pitch_content=report.pitch_content,
                executive_summary=report.executive_summary,
                email_subject=report.email_subject,
                email_body=report.email_body,
                whatsapp_message=report.whatsapp_message,
                pdf_path=report.pdf_path,
                pdf_generated=report.pdf_generated,
                status=report.status.value if hasattr(report.status, 'value') else report.status,
                email_sent=report.email_sent,
                email_sent_at=report.email_sent_at,
                pricing_tier=report.pricing_tier.value if hasattr(report.pricing_tier, 'value') else report.pricing_tier,
                pricing_estimate=report.pricing_estimate,
                created_at=report.created_at,
                updated_at=report.updated_at,
            ) if report else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
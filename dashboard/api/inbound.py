"""Inbound leads API endpoints for email and WhatsApp leads."""

from datetime import datetime
from typing import Optional, List
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


router = APIRouter(prefix="/api/leads/inbound", tags=["inbound_leads"])


class LeadSource(str, Enum):
    """Source of inbound lead."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB = "web"
    OTHER = "other"


class LeadIntent(str, Enum):
    """Intent classification for inbound leads."""
    WANTS_WEBSITE = "wants_website"
    ASKING_QUESTION = "asking_question"
    PROPOSAL_REQUEST = "proposal_request"
    SPAM = "spam"
    UNKNOWN = "unknown"


class InboundLeadCreate(BaseModel):
    """Schema for creating an inbound lead."""
    source: LeadSource
    email: Optional[str] = None
    phone: Optional[str] = None
    sender_name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    intent: LeadIntent = LeadIntent.UNKNOWN
    business_name: Optional[str] = None
    status: str = "new"


class InboundLeadResponse(BaseModel):
    """Response schema for inbound lead."""
    id: str
    source: str
    email: Optional[str] = None
    phone: Optional[str] = None
    sender_name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    intent: str
    business_name: Optional[str] = None
    status: str
    order_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class InboundLeadListResponse(BaseModel):
    """Paginated list of inbound leads."""
    leads: List[InboundLeadResponse]
    total: int
    limit: int
    offset: int


class HumanNeededResponse(BaseModel):
    """Response schema for human-needed emails."""
    id: int
    sender_email: str
    sender_name: Optional[str] = None
    subject: str
    body: str
    received_at: datetime
    status: str
    assigned_to: Optional[str] = None


def get_inbound_leads_from_db(
    source: Optional[str] = None,
    intent: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Fetch inbound leads from database."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        # Build query
        base_query = "SELECT * FROM inbound_leads WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM inbound_leads WHERE 1=1"
        params = []
        param_idx = 1

        if source:
            base_query += f" AND source = ${param_idx}"
            count_query += f" AND source = ${param_idx}"
            params.append(source)
            param_idx += 1

        if intent:
            base_query += f" AND intent = ${param_idx}"
            count_query += f" AND intent = ${param_idx}"
            params.append(intent)
            param_idx += 1

        if status:
            base_query += f" AND status = ${param_idx}"
            count_query += f" AND status = ${param_idx}"
            params.append(status)
            param_idx += 1

        # Get total count
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Add pagination and ordering
        base_query += f" ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])

        cursor.execute(base_query, params)
        rows = cursor.fetchall()

        leads = []
        for row in rows:
            leads.append({
                "id": row[0],
                "source": row[1],
                "email": row[2],
                "sender_name": row[3],
                "subject": row[4],
                "body": row[5],
                "intent": row[6],
                "business_name": row[7],
                "phone": row[8],
                "status": row[9],
                "order_id": row[10],
                "created_at": row[11],
                "updated_at": row[12],
            })

        cursor.close()
        conn.close()
        return leads, total

    except Exception as e:
        return [], 0


@router.post("", response_model=InboundLeadResponse)
def create_inbound_lead(lead: InboundLeadCreate):
    """Create a new inbound lead."""
    try:
        import psycopg2
        from config.database import DB_CONFIG
        import uuid

        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inbound_leads (
                id VARCHAR(36) PRIMARY KEY,
                source VARCHAR(50) DEFAULT 'email',
                email VARCHAR(255),
                sender_name VARCHAR(255),
                subject VARCHAR(500),
                body TEXT,
                intent VARCHAR(50),
                business_name VARCHAR(255),
                phone VARCHAR(50),
                status VARCHAR(50) DEFAULT 'new',
                order_id VARCHAR(36),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        lead_id = str(uuid.uuid4())
        now = datetime.utcnow()

        cursor.execute("""
            INSERT INTO inbound_leads
            (id, source, email, sender_name, subject, body, intent, business_name, phone, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            lead_id,
            lead.source.value,
            lead.email,
            lead.sender_name,
            lead.subject,
            lead.body,
            lead.intent.value,
            lead.business_name,
            lead.phone,
            lead.status,
            now,
            now,
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return InboundLeadResponse(
            id=lead_id,
            source=lead.source.value,
            email=lead.email,
            phone=lead.phone,
            sender_name=lead.sender_name,
            subject=lead.subject,
            body=lead.body,
            intent=lead.intent.value,
            business_name=lead.business_name,
            status=lead.status,
            order_id=None,
            created_at=now,
            updated_at=now,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("", response_model=InboundLeadListResponse)
def list_inbound_leads(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    source: Optional[str] = Query(default=None, description="Filter by source (email, whatsapp, web)"),
    intent: Optional[str] = Query(default=None, description="Filter by intent"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
):
    """List all inbound leads with pagination and filters."""
    leads, total = get_inbound_leads_from_db(
        source=source,
        intent=intent,
        status=status,
        limit=limit,
        offset=offset,
    )

    return InboundLeadListResponse(
        leads=[
            InboundLeadResponse(
                id=lead["id"],
                source=lead["source"],
                email=lead["email"],
                phone=lead["phone"],
                sender_name=lead["sender_name"],
                subject=lead["subject"],
                body=lead["body"],
                intent=lead["intent"],
                business_name=lead["business_name"],
                status=lead["status"],
                order_id=lead["order_id"],
                created_at=lead["created_at"],
                updated_at=lead["updated_at"],
            )
            for lead in leads
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{lead_id}", response_model=InboundLeadResponse)
def get_inbound_lead(lead_id: str):
    """Get a single inbound lead by ID."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, source, email, sender_name, subject, body, intent,
                   business_name, phone, status, order_id, created_at, updated_at
            FROM inbound_leads WHERE id = %s
        """, (lead_id,))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Lead not found")

        return InboundLeadResponse(
            id=row[0],
            source=row[1],
            email=row[2],
            sender_name=row[3],
            subject=row[4],
            body=row[5],
            intent=row[6],
            business_name=row[7],
            phone=row[8],
            status=row[9],
            order_id=row[10],
            created_at=row[11],
            updated_at=row[12],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.patch("/{lead_id}")
def update_inbound_lead(lead_id: str, updates: dict):
    """Update an inbound lead."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Build update query dynamically
        allowed_fields = ["status", "order_id", "business_name", "phone", "email"]
        set_clauses = []
        values = []

        for field in allowed_fields:
            if field in updates:
                set_clauses.append(f"{field} = %s")
                values.append(updates[field])

        if not set_clauses:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        set_clauses.append("updated_at = %s")
        values.append(datetime.utcnow())
        values.append(lead_id)

        cursor.execute(
            f"UPDATE inbound_leads SET {', '.join(set_clauses)} WHERE id = %s",
            values
        )

        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Lead not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"success": True, "message": "Lead updated"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/human-needed/list")
def list_human_needed(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List emails that need human response."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        base_query = "SELECT id, sender_email, sender_name, subject, body, received_at, status, assigned_to FROM human_needed WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM human_needed WHERE 1=1"
        params = []
        param_idx = 1

        if status:
            base_query += f" AND status = ${param_idx}"
            count_query += f" AND status = ${param_idx}"
            params.append(status)
            param_idx += 1

        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        base_query += f" ORDER BY received_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])

        cursor.execute(base_query, params)
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            "items": [
                {
                    "id": row[0],
                    "sender_email": row[1],
                    "sender_name": row[2],
                    "subject": row[3],
                    "body": row[4],
                    "received_at": row[5],
                    "status": row[6],
                    "assigned_to": row[7],
                }
                for row in rows
            ],
            "total": total,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

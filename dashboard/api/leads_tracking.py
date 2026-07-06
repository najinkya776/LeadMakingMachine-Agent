"""Lead tracking API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import LeadDatabase, Lead, LeadStatus, LeadSource, EmailRecord, Response, Conversation, Order
from dashboard.ws_manager import ws_manager

router = APIRouter(prefix="/api/leads", tags=["leads"])

# Pydantic models for request/response
class LeadCreate(BaseModel):
    business_name: str
    owner_name: str = ""
    industry: str = ""
    location: str = ""
    email: str = ""
    phone: str = ""
    website: str = ""
    google_maps_url: str = ""
    rating: float = 0.0
    reviews_count: int = 0
    source: str = "cold_outreach"


class LeadUpdate(BaseModel):
    owner_name: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    status: Optional[str] = None
    score: Optional[int] = None
    findings: Optional[str] = None
    notes: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str
    notes: str = ""


class ResponseCreate(BaseModel):
    channel: str = "email"
    response_text: str
    response_type: str = "neutral"
    sentiment: str = "neutral"
    interested_in: str = ""
    budget: str = ""
    timeline: str = ""
    notes: str = ""


class EmailRecordCreate(BaseModel):
    email_type: str = "initial"
    subject: str = ""
    body: str = ""
    pdf_report_path: str = ""


class OrderCreate(BaseModel):
    package: str
    amount: float
    currency: str = "INR"
    payment_status: str = "pending"
    payment_id: str = ""
    website_url: str = ""
    notes: str = ""


# Initialize database
db = LeadDatabase()


# ==================== LEAD ENDPOINTS ====================

@router.get("", response_model=List[dict])
async def get_leads(
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None),
    limit: int = Query(100, max=500),
    offset: int = Query(0),
):
    """Get all leads with optional filters."""
    leads = db.get_leads(
        status=status, source=source, industry=industry,
        location=location, min_score=min_score, limit=limit, offset=offset
    )
    return [lead.to_dict() for lead in leads]


@router.get("/stats")
async def get_stats():
    """Get dashboard statistics."""
    return db.get_stats()


@router.get("/search")
async def search_leads(q: str = Query(...), limit: int = Query(50)):
    """Search leads by name, email, or owner."""
    leads = db.search_leads(q, limit)
    return [lead.to_dict() for lead in leads]


@router.get("/untouched")
async def get_untouched_leads(limit: int = Query(50)):
    """Get leads that haven't been contacted yet."""
    leads = db.get_untouched_leads(limit)
    return [lead.to_dict() for lead in leads]


@router.get("/needs-followup")
async def get_followup_leads():
    """Get leads that need follow-up."""
    leads = db.get_leads_needing_followup()
    return [lead.to_dict() for lead in leads]


@router.get("/{lead_id}")
async def get_lead(lead_id: int):
    """Get a single lead by ID."""
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead.to_dict()


@router.post("")
async def create_lead(lead_data: LeadCreate):
    """Create a new lead."""
    lead = Lead(**lead_data.model_dump())
    lead_id = db.add_lead(lead)
    # Fetch the created lead for broadcast
    created_lead = db.get_lead(lead_id)
    # Broadcast to all connected clients
    await ws_manager.broadcast_lead_created(lead_id, created_lead.to_dict() if created_lead else {"id": lead_id})
    await ws_manager.broadcast_stats_updated(db.get_stats())
    return {"id": lead_id, "message": "Lead created"}


@router.post("/bulk")
async def create_leads_bulk(leads_data: List[LeadCreate]):
    """Create multiple leads at once."""
    leads = [Lead(**ld.model_dump()) for ld in leads_data]
    count = db.add_leads_bulk(leads)
    return {"count": count, "message": f"{count} leads created"}


@router.patch("/{lead_id}")
async def update_lead(lead_id: int, update: LeadUpdate):
    """Update lead fields."""
    data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    success = db.update_lead(lead_id, **data)
    if not success:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"message": "Lead updated"}


@router.patch("/{lead_id}/status")
async def update_lead_status(lead_id: int, update: StatusUpdate):
    """Update lead status."""
    success = db.update_lead_status(lead_id, update.status)
    if update.notes:
        db.update_lead(lead_id, notes=update.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"message": f"Status updated to {update.status}"}


@router.delete("/{lead_id}/trash")
async def trash_lead(lead_id: int, reason: str = Query("")):
    """Move lead to trash."""
    success = db.trash_lead(lead_id, reason)
    if not success:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"message": "Lead moved to trash"}


@router.delete("/{lead_id}")
async def delete_lead(lead_id: int):
    """Permanently delete a lead."""
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    if affected == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"message": "Lead deleted"}


# ==================== EMAIL ENDPOINTS ====================

@router.get("/{lead_id}/emails")
async def get_lead_emails(lead_id: int):
    """Get all email records for a lead."""
    emails = db.get_emails_for_lead(lead_id)
    return [{"id": e.id, "email_type": e.email_type, "subject": e.subject,
             "sent_at": e.sent_at, "delivered": e.delivered, "opened": e.opened,
             "replied": e.replied} for e in emails]


@router.post("/{lead_id}/emails")
async def record_email(lead_id: int, record: EmailRecordCreate):
    """Record a sent email."""
    email_record = EmailRecord(
        lead_id=lead_id,
        email_type=record.email_type,
        subject=record.subject,
        body=record.body,
        pdf_report_path=record.pdf_report_path,
    )
    email_id = db.record_email(email_record)
    return {"id": email_id, "message": "Email recorded"}


@router.patch("/{lead_id}/emails/{email_id}/replied")
async def mark_email_replied(lead_id: int, email_id: int):
    """Mark email as replied to."""
    success = db.mark_email_replied(email_id)
    if success:
        # Also update lead status
        db.update_lead_status(lead_id, LeadStatus.RESPONDED.value)
    return {"message": "Email marked as replied"}


# ==================== RESPONSE ENDPOINTS ====================

@router.get("/{lead_id}/responses")
async def get_lead_responses(lead_id: int):
    """Get all responses for a lead."""
    responses = db.get_responses_for_lead(lead_id)
    return [{"id": r.id, "channel": r.channel, "response_type": r.response_type,
             "sentiment": r.sentiment, "responded_at": r.responded_at,
             "response_text": r.response_text[:200]} for r in responses]


@router.post("/{lead_id}/responses")
async def add_response(lead_id: int, response: ResponseCreate):
    """Add a response from a lead."""
    resp = Response(
        lead_id=lead_id,
        channel=response.channel,
        response_text=response.response_text,
        response_type=response.response_type,
        sentiment=response.sentiment,
        interested_in=response.interested_in,
        budget=response.budget,
        timeline=response.timeline,
        notes=response.notes,
    )
    response_id = db.add_response(resp)
    return {"id": response_id, "message": "Response recorded"}


# ==================== CONVERSATION ENDPOINTS ====================

@router.get("/{lead_id}/conversations")
async def get_conversation_history(lead_id: int):
    """Get full conversation history for a lead."""
    conversations = db.get_conversation_history(lead_id)
    return [{"id": c.id, "direction": c.direction, "channel": c.channel,
             "message": c.message, "created_at": c.created_at} for c in conversations]


@router.post("/{lead_id}/conversations")
async def add_conversation(lead_id: int, direction: str = "outbound",
                          channel: str = "email", message: str = ""):
    """Add a conversation entry."""
    conv = Conversation(lead_id=lead_id, direction=direction,
                        channel=channel, message=message)
    conv_id = db.add_conversation(conv)
    return {"id": conv_id, "message": "Conversation added"}


# ==================== ORDER ENDPOINTS ====================

@router.get("/{lead_id}/orders")
async def get_lead_orders(lead_id: int):
    """Get orders for a lead."""
    orders = db.get_orders(lead_id=lead_id)
    return [{"id": o.id, "package": o.package, "amount": o.amount,
             "payment_status": o.payment_status, "order_date": o.order_date}
            for o in orders]


@router.post("/{lead_id}/orders")
async def create_order(lead_id: int, order: OrderCreate):
    """Create a new order for a lead."""
    new_order = Order(
        lead_id=lead_id,
        package=order.package,
        amount=order.amount,
        currency=order.currency,
        payment_status=order.payment_status,
        payment_id=order.payment_id,
        website_url=order.website_url,
        notes=order.notes,
    )
    order_id = db.create_order(new_order)
    return {"id": order_id, "message": "Order created"}


@router.patch("/{lead_id}/orders/{order_id}")
async def update_order(lead_id: int, order_id: int, status: str = Query(...)):
    """Update order payment status."""
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET payment_status = ? WHERE id = ? AND lead_id = ?",
                  (status, order_id, lead_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    if affected == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"message": f"Order status updated to {status}"}


# ==================== BULK ACTIONS ====================

@router.post("/bulk-status")
async def bulk_update_status(lead_ids: List[int], status: str = Query(...)):
    """Update status for multiple leads."""
    count = 0
    for lead_id in lead_ids:
        if db.update_lead_status(lead_id, status):
            count += 1
    return {"count": count, "message": f"{count} leads updated to {status}"}


@router.post("/bulk-trash")
async def bulk_trash_leads(lead_ids: List[int], reason: str = Query("")):
    """Move multiple leads to trash."""
    count = 0
    for lead_id in lead_ids:
        if db.trash_lead(lead_id, reason):
            count += 1
    return {"count": count, "message": f"{count} leads moved to trash"}


# ==================== CAMPAIGN ENDPOINTS ====================

from agents.campaign_agent import CampaignAgent, Campaign, get_campaign_agent

campaign_router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])
ca: CampaignAgent = get_campaign_agent()


class CampaignCreate(BaseModel):
    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    target_count: int = 0


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    end_date: Optional[str] = None
    target_count: Optional[int] = None
    status: Optional[str] = None


@campaign_router.post("")
async def create_campaign(campaign_data: CampaignCreate):
    """Create a new campaign."""
    campaign_id = ca.create_campaign(
        name=campaign_data.name,
        start_date=campaign_data.start_date,
        end_date=campaign_data.end_date,
        target_count=campaign_data.target_count
    )
    campaign = ca.get_campaign(campaign_id)
    return {"id": campaign_id, "campaign": campaign.to_dict() if campaign else None}


@campaign_router.get("")
async def list_campaigns(status: Optional[str] = Query(None), limit: int = Query(100)):
    """List all campaigns with optional status filter."""
    campaigns = ca.get_campaigns(status=status, limit=limit)
    return [c.to_dict() for c in campaigns]


@campaign_router.get("/summary")
async def get_campaign_summary():
    """Get summary of all campaigns."""
    return ca.get_campaign_summary()


@campaign_router.get("/{campaign_id}")
async def get_campaign(campaign_id: int):
    """Get a single campaign by ID."""
    campaign = ca.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign.to_dict()


@campaign_router.get("/{campaign_id}/stats")
async def get_campaign_stats(campaign_id: int):
    """Get detailed statistics for a campaign."""
    stats = ca.get_campaign_stats(campaign_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return stats


@campaign_router.get("/{campaign_id}/leads")
async def get_campaign_leads(campaign_id: int):
    """Get all leads associated with a campaign."""
    campaign = ca.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    leads = ca.get_leads_for_campaign(campaign_id)
    return [l.to_dict() for l in leads]


@campaign_router.patch("/{campaign_id}")
async def update_campaign(campaign_id: int, update: CampaignUpdate):
    """Update campaign fields."""
    data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    success = ca.update_campaign(campaign_id, **data)
    if not success:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"message": "Campaign updated"}


@campaign_router.post("/{campaign_id}/archive")
async def archive_campaign(campaign_id: int):
    """Archive a campaign."""
    success = ca.archive_campaign(campaign_id)
    if not success:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"message": "Campaign archived"}


@campaign_router.post("/auto-archive")
async def auto_archive_campaigns(days: int = Query(30)):
    """Auto-archive campaigns older than specified days."""
    count = ca.auto_archive_old_campaigns(days)
    return {"archived": count, "message": f"{count} campaigns archived"}


@campaign_router.post("/{campaign_id}/associate")
async def associate_leads(campaign_id: int, lead_ids: List[int]):
    """Associate multiple leads with a campaign."""
    campaign = ca.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    count = ca.associate_leads_bulk(lead_ids, campaign_id)
    return {"count": count, "message": f"{count} leads associated with campaign"}


@campaign_router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: int):
    """Delete a campaign (only if no leads associated)."""
    success = ca.delete_campaign(campaign_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete campaign with associated leads")
    return {"message": "Campaign deleted"}

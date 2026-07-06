"""Conversion funnel API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.conversion_agent import (
    FunnelStage,
    FunnelReport,
    FunnelVisualization,
    generate_funnel_report,
    get_funnel_visualization,
    get_stuck_leads,
    get_stage_leads,
    move_lead_to_stage,
    set_lead_deal_value,
    get_funnel_stages,
)


router = APIRouter(prefix="/api/funnel", tags=["funnel"])


# =============================================================================
# Response Schemas
# =============================================================================

class StageMetricsResponse(BaseModel):
    """Metrics for a single funnel stage."""
    stage: str
    count: int
    previous_count: int
    drop_offs: int
    conversion_rate: float
    drop_off_rate: float
    avg_time_hours: float


class BottleneckResponse(BaseModel):
    """Bottleneck analysis result."""
    stage: str
    drop_off_rate: float
    drop_offs: int
    severity: str
    recommendation: str


class FunnelReportResponse(BaseModel):
    """Complete funnel report."""
    generated_at: datetime
    total_leads: int
    converted_leads: int
    overall_conversion_rate: float
    total_revenue: float
    avg_revenue_per_lead: float
    avg_customer_lifetime_value: float
    stage_metrics: list[StageMetricsResponse]
    bottlenecks: list[BottleneckResponse]
    time_range_start: datetime
    time_range_end: datetime


class FunnelVisualizationResponse(BaseModel):
    """Funnel visualization data for dashboard charts."""
    stages: list[dict]
    drop_offs: list[dict]
    conversion_rates: list[dict]
    time_metrics: list[dict]
    summary: dict


class StageLeadsResponse(BaseModel):
    """Leads in a specific stage."""
    stage: str
    leads: list[dict]
    total: int


class StuckLeadsResponse(BaseModel):
    """Leads stuck in stages."""
    leads: list[dict]
    total: int
    days_threshold: int


class StageMoveRequest(BaseModel):
    """Request to move a lead to a new stage."""
    lead_id: str
    target_stage: str


class DealValueRequest(BaseModel):
    """Request to set deal value."""
    lead_id: str
    value: float


class FunnelStagesResponse(BaseModel):
    """Available funnel stages."""
    stages: list[str]
    stage_order: list[str]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=FunnelReportResponse)
def get_funnel_report(
    days: int = Query(default=30, ge=7, le=365, description="Number of days to analyze"),
):
    """Get comprehensive funnel analysis report."""
    report = generate_funnel_report(days=days)

    return FunnelReportResponse(
        generated_at=report.generated_at,
        total_leads=report.total_leads,
        converted_leads=report.converted_leads,
        overall_conversion_rate=report.overall_conversion_rate,
        total_revenue=report.total_revenue,
        avg_revenue_per_lead=report.avg_revenue_per_lead,
        avg_customer_lifetime_value=report.avg_customer_lifetime_value,
        stage_metrics=[
            StageMetricsResponse(
                stage=m.stage,
                count=m.count,
                previous_count=m.previous_count,
                drop_offs=m.drop_offs,
                conversion_rate=m.conversion_rate,
                drop_off_rate=m.drop_off_rate,
                avg_time_hours=m.avg_time_hours,
            )
            for m in report.stage_metrics
        ],
        bottlenecks=[
            BottleneckResponse(
                stage=b["stage"],
                drop_off_rate=b["drop_off_rate"],
                drop_offs=b["drop_offs"],
 severity=b["severity"],
                recommendation=b["recommendation"],
            )
            for b in report.bottlenecks
        ],
        time_range_start=report.time_range_start,
        time_range_end=report.time_range_end,
    )


@router.get("/visualization", response_model=FunnelVisualizationResponse)
def get_funnel_visualization_endpoint(
    days: int = Query(default=30, ge=7, le=365, description="Number of days to analyze"),
):
    """Get funnel data optimized for dashboard visualization."""
    viz = get_funnel_visualization(days=days)

    return FunnelVisualizationResponse(
        stages=viz.stages,
        drop_offs=viz.drop_offs,
        conversion_rates=viz.conversion_rates,
        time_metrics=viz.time_metrics,
        summary=viz.summary,
    )


@router.get("/stages", response_model=FunnelStagesResponse)
def get_funnel_stages_endpoint():
    """Get available funnel stages."""
    stages = get_funnel_stages()

    return FunnelStagesResponse(
        stages=stages,
        stage_order=[
            "new",
            "contacted",
            "responded",
            "interested",
            "negotiating",
            "converted",
        ],
    )


@router.get("/stuck", response_model=StuckLeadsResponse)
def get_stuck_leads_endpoint(
    days: int = Query(default=7, ge=1, le=30, description="Days threshold for stuck leads"),
):
    """Get leads stuck in stages for too long."""
    leads = get_stuck_leads(days=days)

    return StuckLeadsResponse(
        leads=leads,
        total=len(leads),
        days_threshold=days,
    )


@router.get("/stage/{stage}", response_model=StageLeadsResponse)
def get_stage_leads_endpoint(
    stage: str,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get all leads in a specific funnel stage."""
    leads = get_stage_leads(stage, limit)

    return StageLeadsResponse(
        stage=stage,
        leads=leads,
        total=len(leads),
    )


@router.post("/move")
def move_lead_endpoint(move: StageMoveRequest):
    """Move a lead to a new funnel stage."""
    result = move_lead_to_stage(move.lead_id, move.target_stage)
    return result


@router.post("/deal-value")
def set_deal_value_endpoint(deal: DealValueRequest):
    """Set the deal value for a lead."""
    success = set_lead_deal_value(deal.lead_id, deal.value)

    if success:
        return {"success": True, "lead_id": deal.lead_id, "value": deal.value}
    return {"success": False, "error": "Failed to update deal value"}

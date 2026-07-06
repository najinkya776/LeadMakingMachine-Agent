"""Dashboard statistics API endpoints."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


router = APIRouter(prefix="/api/stats", tags=["stats"])


# =============================================================================
# Response Schemas
# =============================================================================

class DashboardStatsResponse(BaseModel):
    """Dashboard statistics response for KPI cards."""
    # Lead metrics
    total_leads: int
    leads_today: int
    leads_this_week: int
    leads_this_month: int

    # Status breakdown
    leads_by_status: dict[str, int]
    leads_by_type: dict[str, int]

    # Quality metrics
    avg_score: Optional[float] = None
    high_priority_leads: int
    medium_priority_leads: int
    low_priority_leads: int

    # Conversion metrics
    qualified_leads: int
    reports_generated: int
    emails_sent: int
    email_open_rate: Optional[float] = None

    # Pipeline metrics
    total_runs: int
    runs_completed: int
    runs_failed: int
    avg_run_duration_seconds: Optional[float] = None

    # Recent activity
    recent_leads: list[dict] = []
    recent_activity: list[dict] = []


class PipelineStatusResponse(BaseModel):
    """Current pipeline status response."""
    is_running: bool
    current_run_id: Optional[str] = None
    queue_depth: dict[str, int]
    processing_rate: Optional[float] = None  # leads per minute
    estimated_completion: Optional[str] = None
    last_activity: Optional[datetime] = None


class CategoryBreakdown(BaseModel):
    """Lead breakdown by category."""
    category: str
    count: int
    avg_score: Optional[float] = None


class TrendDataPoint(BaseModel):
    """Single data point for trend charts."""
    date: str
    value: int


class DashboardTrendsResponse(BaseModel):
    """Trend data for charts."""
    leads_trend: list[TrendDataPoint]
    score_trend: list[TrendDataPoint]
    conversion_trend: list[TrendDataPoint]


# =============================================================================
# Database Helpers
# =============================================================================

def get_db_connection():
    """Get database connection."""
    try:
        import psycopg2
        from config.database import DB_CONFIG
        return psycopg2.connect(**DB_CONFIG)
    except Exception:
        return None


def get_dashboard_stats() -> DashboardStatsResponse:
    """Get comprehensive dashboard statistics."""
    conn = get_db_connection()

    if not conn:
        return _empty_dashboard_stats()

    try:
        conn.autocommit = True
        cursor = conn.cursor()

        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        # Total leads
        cursor.execute("SELECT COUNT(*) FROM leads")
        total_leads = cursor.fetchone()[0]

        # Leads by time period
        cursor.execute("SELECT COUNT(*) FROM leads WHERE created_at >= %s", (today_start,))
        leads_today = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE created_at >= %s", (week_start,))
        leads_this_week = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE created_at >= %s", (month_start,))
        leads_this_month = cursor.fetchone()[0]

        # Leads by status
        cursor.execute("SELECT status, COUNT(*) FROM leads GROUP BY status")
        leads_by_status = {row[0]: row[1] for row in cursor.fetchall()}

        # Leads by type
        cursor.execute("SELECT lead_type, COUNT(*) FROM leads WHERE lead_type IS NOT NULL GROUP BY lead_type")
        leads_by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Score metrics
        cursor.execute("SELECT AVG(reachability_score) FROM leads WHERE reachability_score IS NOT NULL")
        avg_score = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE reachability_score >= 80")
        high_priority_leads = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE reachability_score >= 50 AND reachability_score < 80")
        medium_priority_leads = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE reachability_score < 50 AND reachability_score IS NOT NULL")
        low_priority_leads = cursor.fetchone()[0]

        # Conversion metrics
        qualified_leads = leads_by_status.get("qualified", 0) + leads_by_status.get("scored", 0)

        cursor.execute("SELECT COUNT(*) FROM reports")
        reports_generated = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM reports WHERE email_sent = true")
        emails_sent = cursor.fetchone()[0]

        # Pipeline runs from Redis
        import redis
        from config.database import REDIS_CONFIG

        try:
            r = redis.Redis(**REDIS_CONFIG)
            run_keys = [k.decode() for k in r.keys("run:*") if not k.decode().endswith(":status")]
            total_runs = len(run_keys)

            runs_completed = 0
            runs_failed = 0
            durations = []

            for key in run_keys:
                status = r.hget(key, "status")
                if status:
                    status = status.decode()
                    if status == "completed":
                        runs_completed += 1
                        duration = r.hget(key, "duration_seconds")
                        if duration:
                            durations.append(float(duration.decode()))
                    elif status == "failed":
                        runs_failed += 1

            avg_run_duration = sum(durations) / len(durations) if durations else None
        except Exception:
            total_runs = 0
            runs_completed = 0
            runs_failed = 0
            avg_run_duration = None

        # Recent leads
        cursor.execute("""
            SELECT id, business_name, category, status, reachability_score, created_at
            FROM leads
            ORDER BY created_at DESC
            LIMIT 5
        """)
        recent_leads = [
            {
                "id": row[0],
                "business_name": row[1],
                "category": row[2],
                "status": row[3],
                "score": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
            }
            for row in cursor.fetchall()
        ]

        cursor.close()
        conn.close()

        return DashboardStatsResponse(
            total_leads=total_leads,
            leads_today=leads_today,
            leads_this_week=leads_this_week,
            leads_this_month=leads_this_month,
            leads_by_status=leads_by_status,
            leads_by_type=leads_by_type,
            avg_score=avg_score,
            high_priority_leads=high_priority_leads,
            medium_priority_leads=medium_priority_leads,
            low_priority_leads=low_priority_leads,
            qualified_leads=qualified_leads,
            reports_generated=reports_generated,
            emails_sent=emails_sent,
            email_open_rate=None,
            total_runs=total_runs,
            runs_completed=runs_completed,
            runs_failed=runs_failed,
            avg_run_duration_seconds=avg_run_duration,
            recent_leads=recent_leads,
            recent_activity=[],
        )

    except Exception as e:
        return _empty_dashboard_stats()


def _empty_dashboard_stats() -> DashboardStatsResponse:
    """Return empty stats on error."""
    return DashboardStatsResponse(
        total_leads=0,
        leads_today=0,
        leads_this_week=0,
        leads_this_month=0,
        leads_by_status={},
        leads_by_type={},
        avg_score=None,
        high_priority_leads=0,
        medium_priority_leads=0,
        low_priority_leads=0,
        qualified_leads=0,
        reports_generated=0,
        emails_sent=0,
        email_open_rate=None,
        total_runs=0,
        runs_completed=0,
        runs_failed=0,
        avg_run_duration_seconds=None,
        recent_leads=[],
        recent_activity=[],
    )


def get_pipeline_status() -> PipelineStatusResponse:
    """Get current pipeline status."""
    import redis
    from config.database import REDIS_CONFIG, QUEUES

    try:
        r = redis.Redis(**REDIS_CONFIG)

        # Check for running/pending runs
        run_keys = [k.decode() for k in r.keys("run:*") if not k.decode().endswith(":status")]
        current_run_id = None
        is_running = False
        last_activity = None

        for key in run_keys:
            status = r.hget(key, "status")
            if status:
                status = status.decode()
                if status == "running":
                    is_running = True
                    current_run_id = key.replace("run:", "")
                    started = r.hget(key, "started_at")
                    if started:
                        last_activity = datetime.fromisoformat(started.decode())
                    break
                elif status == "pending":
                    current_run_id = key.replace("run:", "")

        # Get queue depths
        queue_depth = {}
        for queue_name, queue_key in QUEUES.items():
            try:
                count = r.llen(queue_key)
                queue_depth[queue_name] = count
            except Exception:
                queue_depth[queue_name] = 0

        # Calculate processing rate from recent runs
        processing_rate = None
        estimated_completion = None

        if is_running and current_run_id:
            leads_scraped = r.hget(f"run:{current_run_id}", "leads_scraped")
            started = r.hget(f"run:{current_run_id}", "started_at")
            if leads_scraped and started:
                leads = int(leads_scraped.decode())
                started_time = datetime.fromisoformat(started.decode())
                elapsed_minutes = (datetime.utcnow() - started_time).total_seconds() / 60
                if elapsed_minutes > 0:
                    processing_rate = leads / elapsed_minutes

        return PipelineStatusResponse(
            is_running=is_running,
            current_run_id=current_run_id,
            queue_depth=queue_depth,
            processing_rate=processing_rate,
            estimated_completion=estimated_completion,
            last_activity=last_activity,
        )

    except Exception:
        return PipelineStatusResponse(
            is_running=False,
            current_run_id=None,
            queue_depth={},
            processing_rate=None,
            estimated_completion=None,
            last_activity=None,
        )


def get_category_breakdown() -> list[CategoryBreakdown]:
    """Get lead count breakdown by category."""
    conn = get_db_connection()

    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, COUNT(*), AVG(reachability_score)
            FROM leads
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY COUNT(*) DESC
        """)

        results = [
            CategoryBreakdown(
                category=row[0],
                count=row[1],
                avg_score=row[2],
            )
            for row in cursor.fetchall()
        ]

        cursor.close()
        conn.close()

        return results

    except Exception:
        return []


def get_lead_trends(days: int = 30) -> DashboardTrendsResponse:
    """Get lead trends over time."""
    conn = get_db_connection()

    if not conn:
        return DashboardTrendsResponse(
            leads_trend=[],
            score_trend=[],
            conversion_trend=[],
        )

    try:
        cursor = conn.cursor()

        # Get leads per day
        cursor.execute(f"""
            SELECT DATE(created_at) as date, COUNT(*)
            FROM leads
            WHERE created_at >= NOW() - INTERVAL '{days} days'
            GROUP BY DATE(created_at)
            ORDER BY date
        """)

        leads_trend = [
            TrendDataPoint(date=str(row[0]), value=row[1])
            for row in cursor.fetchall()
        ]

        # Get average score per day
        cursor.execute(f"""
            SELECT DATE(created_at) as date, AVG(reachability_score)
            FROM leads
            WHERE created_at >= NOW() - INTERVAL '{days} days'
            AND reachability_score IS NOT NULL
            GROUP BY DATE(created_at)
            ORDER BY date
        """)

        score_trend = [
            TrendDataPoint(date=str(row[0]), value=int(row[1] or 0))
            for row in cursor.fetchall()
        ]

        # Get conversion (qualified leads) per day
        cursor.execute(f"""
            SELECT DATE(created_at) as date, COUNT(*)
            FROM leads
            WHERE created_at >= NOW() - INTERVAL '{days} days'
            AND status IN ('qualified', 'scored', 'completed')
            GROUP BY DATE(created_at)
            ORDER BY date
        """)

        conversion_trend = [
            TrendDataPoint(date=str(row[0]), value=row[1])
            for row in cursor.fetchall()
        ]

        cursor.close()
        conn.close()

        return DashboardTrendsResponse(
            leads_trend=leads_trend,
            score_trend=score_trend,
            conversion_trend=conversion_trend,
        )

    except Exception:
        return DashboardTrendsResponse(
            leads_trend=[],
            score_trend=[],
            conversion_trend=[],
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=DashboardStatsResponse)
def get_dashboard_stats_endpoint(
    refresh: bool = Query(default=False, description="Force refresh cached data"),
):
    """Get dashboard statistics for KPI cards."""
    return get_dashboard_stats()


@router.get("/pipeline", response_model=PipelineStatusResponse)
def get_pipeline_status_endpoint():
    """Get current pipeline processing status."""
    return get_pipeline_status()


@router.get("/categories", response_model=list[CategoryBreakdown])
def get_category_breakdown_endpoint():
    """Get lead breakdown by business category."""
    return get_category_breakdown()


@router.get("/trends", response_model=DashboardTrendsResponse)
def get_trends_endpoint(
    days: int = Query(default=30, ge=7, le=90, description="Number of days for trend data"),
):
    """Get lead trends over time for charts."""
    return get_lead_trends(days=days)
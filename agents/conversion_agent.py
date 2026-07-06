"""Conversion funnel tracking agent.

Tracks leads through the sales funnel and generates funnel reports.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field
import psycopg2
from config.database import DB_CONFIG


class FunnelStage(str, Enum):
    """Sales funnel stages."""
    NEW = "new"
    CONTACTED = "contacted"
    RESPONDED = "responded"
    INTERESTED = "interested"
    NEGOTIATING = "negotiating"
    CONVERTED = "converted"


@dataclass
class StageMetrics:
    """Metrics for a single funnel stage."""
    stage: str
    count: int = 0
    previous_count: int = 0
    drop_offs: int = 0
    conversion_rate: float = 0.0
    drop_off_rate: float = 0.0
    avg_time_hours: float = 0.0
    leads: list[dict] = field(default_factory=list)


@dataclass
class FunnelReport:
    """Complete funnel analysis report."""
    generated_at: datetime
    total_leads: int
    converted_leads: int
    overall_conversion_rate: float
    total_revenue: float
    avg_revenue_per_lead: float
    avg_customer_lifetime_value: float
    stage_metrics: list[StageMetrics]
    bottlenecks: list[dict]
    time_range_start: datetime
    time_range_end: datetime


@dataclass
class FunnelVisualization:
    """Data structure optimized for funnel visualization in dashboard."""
    stages: list[dict]
    drop_offs: list[dict]
    conversion_rates: list[dict]
    time_metrics: list[dict]
    summary: dict


def get_funnel_stages() -> list[str]:
    """Get ordered funnel stages."""
    return [stage.value for stage in FunnelStage]


def get_stage_status_mapping() -> dict:
    """Map funnel stages to lead statuses."""
    return {
        FunnelStage.NEW: "qualified",
        FunnelStage.CONTACTED: "pitched",
        FunnelStage.RESPONDED: "responded",
        FunnelStage.INTERESTED: "interested",
        FunnelStage.NEGOTIATING: "negotiating",
        FunnelStage.CONVERTED: "converted",
    }


def ensure_funnel_columns():
    """Ensure funnel tracking columns exist in leads table."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Add funnel columns if they don't exist
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'leads' AND column_name = 'funnel_stage'
                ) THEN
                    ALTER TABLE leads ADD COLUMN funnel_stage VARCHAR(50) DEFAULT 'new';
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'leads' AND column_name = 'stage_entered_at'
                ) THEN
                    ALTER TABLE leads ADD COLUMN stage_entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'leads' AND column_name = 'funnel_started_at'
                ) THEN
                    ALTER TABLE leads ADD COLUMN funnel_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'leads' AND column_name = 'converted_at'
                ) THEN
                    ALTER TABLE leads ADD COLUMN converted_at TIMESTAMP;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'leads' AND column_name = 'deals_value'
                ) THEN
                    ALTER TABLE leads ADD COLUMN deals_value DECIMAL(10, 2) DEFAULT 0;
                END IF;
            END $$;
        """)

        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass


def ensure_orders_funnel_columns():
    """Ensure orders table has conversion tracking columns."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'orders' AND column_name = 'funnel_lead_id'
                ) THEN
                    ALTER TABLE orders ADD COLUMN funnel_lead_id VARCHAR(36);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'orders' AND column_name = 'ltv_tracking'
                ) THEN
                    ALTER TABLE orders ADD COLUMN ltv_tracking BOOLEAN DEFAULT false;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'orders' AND column_name = 'customer_id'
                ) THEN
                    ALTER TABLE orders ADD COLUMN customer_id VARCHAR(36);
                END IF;
            END $$;
        """)

        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass


def update_lead_funnel_stage(lead_id: str, new_stage: FunnelStage) -> bool:
    """Update a lead's funnel stage."""
    ensure_funnel_columns()

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        now = datetime.utcnow()

        cursor.execute("""
            UPDATE leads
            SET funnel_stage = %s,
                stage_entered_at = %s,
                converted_at = CASE WHEN %s = 'converted' THEN %s ELSE converted_at END
            WHERE id = %s
        """, (new_stage.value, now, new_stage.value, now, lead_id))

        conn.commit()
        cursor.close()
        conn.close()

        return True
    except Exception:
        return False


def get_funnel_metrics(days: int = 30) -> tuple[list[StageMetrics], list[dict]]:
    """Calculate funnel metrics for each stage."""
    ensure_funnel_columns()

    stages = get_funnel_stages()
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        stage_metrics = []
        bottlenecks = []

        for i, stage in enumerate(stages):
            # Get count for current stage
            cursor.execute("""
                SELECT COUNT(*)
                FROM leads
                WHERE funnel_stage = %s
                AND funnel_started_at >= %s
            """, (stage, start_date))
            count = cursor.fetchone()[0]

            # Get previous stage count for drop-off calculation
            previous_count = 0
            if i > 0:
                prev_stage = stages[i - 1]
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM leads
                    WHERE funnel_stage = %s
                    AND funnel_started_at >= %s
                """, (prev_stage, start_date))
                previous_count = cursor.fetchone()[0]

            # Calculate drop-offs
            drop_offs = max(0, previous_count - count) if i > 0 else 0

            # Calculate rates
            conversion_rate = (count / previous_count * 100) if previous_count > 0 and i > 0 else 100.0 if i == 0 else 0.0
            drop_off_rate = (drop_offs / previous_count * 100) if previous_count > 0 and i > 0 else 0.0

            # Get average time in stage
            cursor.execute("""
                SELECT AVG(EXTRACT(EPOCH FROM (COALESCE(stage_entered_at, NOW()) - funnel_started_at)) / 3600)
                FROM leads
                WHERE funnel_stage = %s
                AND funnel_started_at >= %s
            """, (stage, start_date))
            avg_time = cursor.fetchone()[0] or 0.0

            metrics = StageMetrics(
                stage=stage,
                count=count,
                previous_count=previous_count,
                drop_offs=drop_offs,
                conversion_rate=round(conversion_rate, 2),
                drop_off_rate=round(drop_off_rate, 2),
                avg_time_hours=round(float(avg_time), 2),
            )

            stage_metrics.append(metrics)

            # Track bottleneck (high drop-off rate)
            if drop_off_rate > 30 and i > 0:
                bottlenecks.append({
                    "stage": stage,
                    "drop_off_rate": drop_off_rate,
                    "drop_offs": drop_offs,
                    "severity": "high" if drop_off_rate > 50 else "medium",
                    "recommendation": f"Review outreach strategy for {stage} stage. {drop_offs} leads dropped off.",
                })

        cursor.close()
        conn.close()

        return stage_metrics, bottlenecks

    except Exception as e:
        return [], []


def get_conversion_revenue() -> tuple[int, float, float]:
    """Get conversion count, total revenue, and average revenue per lead."""
    ensure_funnel_columns()

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        # Count converted leads
        cursor.execute("SELECT COUNT(*) FROM leads WHERE funnel_stage = 'converted'")
        converted = cursor.fetchone()[0]

        # Get revenue from deals_value
        cursor.execute("SELECT COALESCE(SUM(deals_value), 0) FROM leads WHERE funnel_stage = 'converted'")
        lead_revenue = float(cursor.fetchone()[0])

        # Get revenue from orders
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM orders
            WHERE status IN ('paid', 'building', 'review', 'delivered', 'upsold')
        """)
        order_revenue = float(cursor.fetchone()[0])

        total_revenue = lead_revenue + order_revenue
        avg_per_lead = total_revenue / converted if converted > 0 else 0.0

        cursor.close()
        conn.close()

        return converted, total_revenue, avg_per_lead

    except Exception:
        return 0, 0.0, 0.0


def calculate_ltv() -> float:
    """Calculate Customer Lifetime Value based on historical data."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        # Get average order value
        cursor.execute("""
            SELECT AVG(amount)
            FROM orders
            WHERE status IN ('paid', 'building', 'review', 'delivered', 'upsold')
            AND amount IS NOT NULL
        """)
        avg_order_value = cursor.fetchone()[0] or 0.0

        # Get repeat purchase rate (orders per customer)
        cursor.execute("""
            SELECT COUNT(*) / COUNT(DISTINCT COALESCE(email, phone, id))
            FROM orders
            WHERE status IN ('paid', 'delivered', 'upsold')
        """)
        repeat_rate = cursor.fetchone()[0] or 1.0

        # Assume average customer relationship of 2 years with quarterly purchases
        assumed_purchases = min(repeat_rate, 8)  # Cap at 8 purchases

        ltv = avg_order_value * assumed_purchases * 0.8  # 80% margin assumption

        cursor.close()
        conn.close()

        return round(ltv, 2)

    except Exception:
        return 5000.0  # Default LTV estimate


def generate_funnel_report(days: int = 30) -> FunnelReport:
    """Generate comprehensive funnel report."""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    stage_metrics, bottlenecks = get_funnel_metrics(days=days)
    converted_leads, total_revenue, avg_revenue = get_conversion_revenue()
    ltv = calculate_ltv()

    # Get total leads that entered funnel in period
    total_leads = sum(m.count for m in stage_metrics) if stage_metrics else 0
    overall_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0.0

    return FunnelReport(
        generated_at=now,
        total_leads=total_leads,
        converted_leads=converted_leads,
        overall_conversion_rate=round(overall_rate, 2),
        total_revenue=round(total_revenue, 2),
        avg_revenue_per_lead=round(avg_revenue, 2),
        avg_customer_lifetime_value=ltv,
        stage_metrics=stage_metrics,
        bottlenecks=bottlenecks,
        time_range_start=start_date,
        time_range_end=now,
    )


def get_funnel_visualization(days: int = 30) -> FunnelVisualization:
    """Generate funnel visualization data for dashboard."""
    report = generate_funnel_report(days=days)

    # Build stages data
    stages = []
    for m in report.stage_metrics:
        stages.append({
            "stage": m.stage,
            "count": m.count,
            "width_percent": min(100, (m.count / max(report.total_leads, 1)) * 100) if report.total_leads > 0 else 0,
        })

    # Build drop-offs data
    drop_offs = []
    for m in report.stage_metrics[1:]:  # Skip first stage
        if m.previous_count > 0:
            drop_offs.append({
                "from": report.stage_metrics[report.stage_metrics.index(m) - 1].stage,
                "to": m.stage,
                "count": m.drop_offs,
                "rate": m.drop_off_rate,
            })

    # Build conversion rates
    conversion_rates = []
    for m in report.stage_metrics:
        conversion_rates.append({
            "stage": m.stage,
            "rate": m.conversion_rate,
        })

    # Build time metrics
    time_metrics = []
    for m in report.stage_metrics:
        time_metrics.append({
            "stage": m.stage,
            "avg_hours": m.avg_time_hours,
            "avg_days": round(m.avg_time_hours / 24, 1),
        })

    summary = {
        "total_leads": report.total_leads,
        "converted": report.converted_leads,
        "conversion_rate": report.overall_conversion_rate,
        "revenue": report.total_revenue,
        "avg_per_lead": report.avg_revenue_per_lead,
        "ltv": report.avg_customer_lifetime_value,
        "bottleneck_count": len(report.bottlenecks),
    }

    return FunnelVisualization(
        stages=stages,
        drop_offs=drop_offs,
        conversion_rates=conversion_rates,
        time_metrics=time_metrics,
        summary=summary,
    )


def get_stuck_leads(days: int = 7) -> list[dict]:
    """Identify leads stuck in stages for too long."""
    ensure_funnel_columns()

    stages = get_funnel_stages()
    stuck_leads = []

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        # Find leads not converted and in same stage for too long
        cursor.execute("""
            SELECT id, business_name, funnel_stage, stage_entered_at
            FROM leads
            WHERE funnel_stage != 'converted'
            AND funnel_stage IS NOT NULL
            AND stage_entered_at < NOW() - INTERVAL '%s days'
            ORDER BY stage_entered_at ASC
            LIMIT 50
        """, (days,))

        for row in cursor.fetchall():
            stage_idx = stages.index(row[2]) if row[2] in stages else 0
            stuck_leads.append({
                "id": row[0],
                "business_name": row[1],
                "stage": row[2],
                "stage_index": stage_idx,
                "stuck_days": (datetime.utcnow() - row[3]).days if row[3] else 0,
            })

        cursor.close()
        conn.close()

        return stuck_leads

    except Exception:
        return []


def get_stage_leads(stage: str, limit: int = 50) -> list[dict]:
    """Get all leads in a specific funnel stage."""
    ensure_funnel_columns()

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, business_name, category, email, phone,
                   funnel_stage, stage_entered_at, deals_value,
                   created_at, reachability_score
            FROM leads
            WHERE funnel_stage = %s
            ORDER BY stage_entered_at DESC
            LIMIT %s
        """, (stage, limit))

        leads = []
        for row in cursor.fetchall():
            leads.append({
                "id": row[0],
                "business_name": row[1],
                "category": row[2],
                "email": row[3],
                "phone": row[4],
                "funnel_stage": row[5],
                "stage_entered_at": row[6].isoformat() if row[6] else None,
                "deals_value": float(row[7]) if row[7] else 0,
                "created_at": row[8].isoformat() if row[8] else None,
                "score": row[9],
            })

        cursor.close()
        conn.close()

        return leads

    except Exception:
        return []


def move_lead_to_stage(lead_id: str, target_stage: str) -> dict:
    """Move a lead to a new funnel stage."""
    try:
        stage = FunnelStage(target_stage)
        success = update_lead_funnel_stage(lead_id, stage)

        if success:
            return {"success": True, "lead_id": lead_id, "new_stage": target_stage}
        return {"success": False, "error": "Failed to update stage"}

    except ValueError:
        return {"success": False, "error": f"Invalid stage: {target_stage}"}


def set_lead_deal_value(lead_id: str, value: float) -> bool:
    """Set the deal value for a lead."""
    ensure_funnel_columns()

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE leads SET deals_value = %s WHERE id = %s",
            (value, lead_id)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return True
    except Exception:
        return False

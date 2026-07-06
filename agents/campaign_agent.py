"""Campaign tracking agent for lead database system."""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import LeadDatabase, Lead, LeadStatus


@dataclass
class Campaign:
    """Campaign data model."""
    id: Optional[int] = None
    name: str = ""
    start_date: str = ""
    end_date: Optional[str] = None
    target_count: int = 0
    sent_count: int = 0
    responded_count: int = 0
    converted_count: int = 0
    status: str = "active"  # active, paused, completed, archived
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class CampaignAgent:
    """Agent for managing campaigns and tracking campaign performance."""

    def __init__(self, db_path: str = None):
        """Initialize campaign agent."""
        self.db = LeadDatabase(db_path)
        self._ensure_lead_campaign_link()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return self.db._get_connection()

    def _ensure_lead_campaign_link(self):
        """Ensure leads table has campaign_id column."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if column exists
        cursor.execute("PRAGMA table_info(leads)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'campaign_id' not in columns:
            cursor.execute("ALTER TABLE leads ADD COLUMN campaign_id INTEGER")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_campaign ON leads(campaign_id)")
            conn.commit()

        conn.close()

    # ==================== CAMPAIGN CRUD ====================

    def create_campaign(
        self,
        name: str,
        start_date: str = None,
        end_date: str = None,
        target_count: int = 0
    ) -> int:
        """Create a new campaign.

        Args:
            name: Campaign name
            start_date: Start date (defaults to now)
            end_date: Optional end date
            target_count: Target number of leads

        Returns:
            Campaign ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        start = start_date or datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO campaigns (name, start_date, end_date, target_count, status)
            VALUES (?, ?, ?, ?, 'active')
        """, (name, start, end_date, target_count))

        campaign_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return campaign_id

    def get_campaign(self, campaign_id: int) -> Optional[Campaign]:
        """Get campaign by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return Campaign(**dict(row))
        return None

    def get_campaigns(self, status: str = None, limit: int = 100) -> List[Campaign]:
        """Get all campaigns, optionally filtered by status."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute("""
                SELECT * FROM campaigns WHERE status = ?
                ORDER BY created_at DESC LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("SELECT * FROM campaigns ORDER BY created_at DESC LIMIT ?", (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [Campaign(**dict(row)) for row in rows]

    def update_campaign(self, campaign_id: int, **kwargs) -> bool:
        """Update campaign fields."""
        if not kwargs:
            return False

        conn = self._get_connection()
        cursor = conn.cursor()

        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [campaign_id]

        cursor.execute(f"UPDATE campaigns SET {set_clause} WHERE id = ?", values)
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected > 0

    def delete_campaign(self, campaign_id: int) -> bool:
        """Delete a campaign (only if no leads associated)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if leads are associated
        cursor.execute("SELECT COUNT(*) FROM leads WHERE campaign_id = ?", (campaign_id,))
        if cursor.fetchone()[0] > 0:
            conn.close()
            return False  # Cannot delete campaign with leads

        cursor.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected > 0

    def archive_campaign(self, campaign_id: int) -> bool:
        """Archive a campaign."""
        return self.update_campaign(campaign_id, status="archived")

    # ==================== LEAD ASSOCIATION ====================

    def associate_lead_with_campaign(self, lead_id: int, campaign_id: int) -> bool:
        """Associate a lead with a campaign."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE leads SET campaign_id = ? WHERE id = ?
        """, (campaign_id, lead_id))

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        # Update campaign sent_count
        if affected > 0:
            self._update_campaign_counts(campaign_id)

        return affected > 0

    def associate_leads_bulk(self, lead_ids: List[int], campaign_id: int) -> int:
        """Associate multiple leads with a campaign.

        Returns:
            Number of leads successfully associated
        """
        count = 0
        conn = self._get_connection()
        cursor = conn.cursor()

        for lead_id in lead_ids:
            cursor.execute("""
                UPDATE leads SET campaign_id = ? WHERE id = ?
            """, (campaign_id, lead_id))
            if cursor.rowcount > 0:
                count += 1

        conn.commit()
        conn.close()

        # Update campaign counts
        if count > 0:
            self._update_campaign_counts(campaign_id)

        return count

    def get_leads_for_campaign(self, campaign_id: int) -> List[Lead]:
        """Get all leads associated with a campaign."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM leads WHERE campaign_id = ?", (campaign_id,))
        rows = cursor.fetchall()
        conn.close()

        return [Lead(**dict(row)) for row in rows]

    def remove_lead_from_campaign(self, lead_id: int) -> bool:
        """Remove a lead's campaign association."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get campaign_id before clearing
        cursor.execute("SELECT campaign_id FROM leads WHERE id = ?", (lead_id,))
        row = cursor.fetchone()
        campaign_id = row[0] if row else None

        cursor.execute("UPDATE leads SET campaign_id = NULL WHERE id = ?", (lead_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        # Update campaign counts
        if affected > 0 and campaign_id:
            self._update_campaign_counts(campaign_id)

        return affected > 0

    # ==================== METRICS & STATS ====================

    def _update_campaign_counts(self, campaign_id: int):
        """Update campaign counts based on associated leads."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total leads in campaign
        cursor.execute("""
            SELECT COUNT(*) FROM leads WHERE campaign_id = ?
        """, (campaign_id,))
        total = cursor.fetchone()[0]

        # Contacted leads (status is contacted or higher)
        cursor.execute("""
            SELECT COUNT(*) FROM leads
            WHERE campaign_id = ?
            AND status IN ('contacted', 'responded', 'interested', 'negotiating', 'converted')
        """, (campaign_id,))
        contacted = cursor.fetchone()[0]

        # Responded leads
        cursor.execute("""
            SELECT COUNT(*) FROM leads
            WHERE campaign_id = ?
            AND status IN ('responded', 'interested', 'negotiating', 'converted')
        """, (campaign_id,))
        responded = cursor.fetchone()[0]

        # Converted leads
        cursor.execute("""
            SELECT COUNT(*) FROM leads
            WHERE campaign_id = ? AND status = 'converted'
        """, (campaign_id,))
        converted = cursor.fetchone()[0]

        cursor.execute("""
            UPDATE campaigns SET
                sent_count = ?,
                responded_count = ?,
                converted_count = ?
            WHERE id = ?
        """, (total, responded, converted, campaign_id))

        conn.commit()
        conn.close()

    def get_campaign_stats(self, campaign_id: int) -> Dict[str, Any]:
        """Get detailed statistics for a campaign.

        Returns:
            Dictionary with campaign performance metrics
        """
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return {}

        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {
            "campaign_id": campaign_id,
            "name": campaign.name,
            "status": campaign.status,
            "start_date": campaign.start_date,
            "end_date": campaign.end_date,
            "target_count": campaign.target_count,
            "leads_scraped": campaign.sent_count,
            "leads_contacted": 0,
            "leads_responded": campaign.responded_count,
            "leads_converted": campaign.converted_count,
            "response_rate": 0.0,
            "contact_rate": 0.0,
            "conversion_rate": 0.0,
            "progress_percent": 0.0,
        }

        # Get counts from leads table directly
        cursor.execute("""
            SELECT COUNT(*) FROM leads WHERE campaign_id = ?
        """, (campaign_id,))
        leads_total = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM leads
            WHERE campaign_id = ?
            AND status IN ('contacted', 'responded', 'interested', 'negotiating', 'converted')
        """, (campaign_id,))
        leads_contacted = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM leads
            WHERE campaign_id = ?
            AND status IN ('responded', 'interested', 'negotiating', 'converted')
        """, (campaign_id,))
        leads_responded = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM leads
            WHERE campaign_id = ? AND status = 'converted'
        """, (campaign_id,))
        leads_converted = cursor.fetchone()[0]

        stats["leads_scraped"] = leads_total
        stats["leads_contacted"] = leads_contacted
        stats["leads_responded"] = leads_responded
        stats["leads_converted"] = leads_converted

        # Calculate rates
        if leads_total > 0:
            stats["contact_rate"] = round((leads_contacted / leads_total) * 100, 2)
            stats["response_rate"] = round((leads_responded / leads_total) * 100, 2)
            stats["conversion_rate"] = round((leads_converted / leads_total) * 100, 2)
            stats["progress_percent"] = round((leads_total / campaign.target_count) * 100, 2) if campaign.target_count > 0 else 0

        # Leads by status breakdown
        cursor.execute("""
            SELECT status, COUNT(*) FROM leads
            WHERE campaign_id = ?
            GROUP BY status
        """, (campaign_id,))
        stats["leads_by_status"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Average score in campaign
        cursor.execute("""
            SELECT AVG(score) FROM leads
            WHERE campaign_id = ? AND score > 0
        """, (campaign_id,))
        avg_score = cursor.fetchone()[0]
        stats["avg_lead_score"] = round(avg_score, 1) if avg_score else 0

        conn.close()

        return stats

    def get_all_campaign_stats(self) -> List[Dict[str, Any]]:
        """Get stats for all campaigns."""
        campaigns = self.get_campaigns()
        return [self.get_campaign_stats(c.id) for c in campaigns if c.id]

    # ==================== AUTO-ARCHIVE ====================

    def auto_archive_old_campaigns(self, days: int = 30) -> int:
        """Archive campaigns older than specified days.

        Args:
            days: Number of days after which to archive (default 30)

        Returns:
            Number of campaigns archived
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff_date = datetime.now() - timedelta(days=days)
        cursor.execute("""
            UPDATE campaigns
            SET status = 'archived'
            WHERE status = 'active'
            AND datetime(start_date) < datetime(?)
        """, (cutoff_date.isoformat(),))

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected

    def auto_complete_campaign(self, campaign_id: int) -> bool:
        """Mark campaign as completed when target is reached."""
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return False

        if campaign.sent_count >= campaign.target_count and campaign.target_count > 0:
            return self.update_campaign(campaign_id, status="completed")

        return False

    # ==================== UTILITY METHODS ====================

    def get_active_campaigns(self) -> List[Campaign]:
        """Get all active campaigns."""
        return self.get_campaigns(status="active")

    def get_campaign_summary(self) -> Dict[str, Any]:
        """Get summary of all campaigns."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status, COUNT(*) as count,
                   SUM(sent_count) as total_leads,
                   SUM(responded_count) as total_responded,
                   SUM(converted_count) as total_converted
            FROM campaigns GROUP BY status
        """)

        summary = {"by_status": {}}
        total_leads = 0
        total_responded = 0
        total_converted = 0

        for row in cursor.fetchall():
            status, count = row[0], row[1]
            summary["by_status"][status] = {
                "count": count,
                "leads": row[2] or 0,
                "responded": row[3] or 0,
                "converted": row[4] or 0
            }

        cursor.execute("SELECT COUNT(*) FROM campaigns")
        summary["total_campaigns"] = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM leads WHERE campaign_id IS NOT NULL
        """)
        summary["total_leads_in_campaigns"] = cursor.fetchone()[0]

        conn.close()
        return summary


# Global instance
campaign_agent = CampaignAgent()


def get_campaign_agent() -> CampaignAgent:
    """Get the global campaign agent instance."""
    return campaign_agent
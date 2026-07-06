"""
Dashboard Service - Statistics and reporting
"""

import sqlite3
from datetime import datetime
from typing import Dict
from pathlib import Path


class Dashboard:
    def __init__(self, settings):
        self.settings = settings
        self.db_path = settings.db_path_absolute

    def get_stats(self) -> Dict:
        """Get dashboard statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Lead counts
        cursor.execute("SELECT COUNT(*) FROM leads")
        stats['total_leads'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'qualified'")
        stats['qualified_leads'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'emailed'")
        stats['emailed'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'responded'")
        stats['responses'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM emails WHERE status = 'replied'")
        stats['replies'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM emails WHERE status = 'bounced'")
        stats['bounces'] = cursor.fetchone()[0]

        # Campaign stats
        cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'active'")
        stats['active_campaigns'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'completed'")
        stats['completed_campaigns'] = cursor.fetchone()[0]

        conn.close()
        return stats

    def generate_report(self, leads: list = None) -> str:
        """Generate campaign report"""
        stats = self.get_stats()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = Path(self.settings.db_path_absolute).parent / "reports"
        report_dir.mkdir(exist_ok=True)

        report_path = report_dir / f"report_{timestamp}.txt"

        with open(report_path, 'w') as f:
            f.write("=" * 50 + "\n")
            f.write("LEAD GENERATION CAMPAIGN REPORT\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")

            f.write("STATISTICS\n")
            f.write("-" * 30 + "\n")
            for key, value in stats.items():
                f.write(f"  {key.replace('_', ' ').title()}: {value}\n")

            if leads:
                f.write(f"\n\nLEADS PROCESSED: {len(leads)}\n")

        return str(report_path)

    def get_recent_leads(self, limit: int = 20) -> list:
        """Get recent leads"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM leads
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        leads = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return leads

    def get_lead_by_id(self, lead_id: int) -> Dict:
        """Get single lead by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

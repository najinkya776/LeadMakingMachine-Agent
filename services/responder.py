"""
Response Checker - Check for email responses
"""

import sqlite3
from datetime import datetime
from typing import List, Dict


class ResponseChecker:
    def __init__(self, settings):
        self.settings = settings
        self.db_path = settings.db_path_absolute

    def check_all(self) -> List[Dict]:
        """Check all pending emails for responses"""
        # This would typically check an IMAP inbox for replies
        # For now, returns responses already logged in database
        return self._get_logged_responses()

    def _get_logged_responses(self) -> List[Dict]:
        """Get responses from database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT r.*, l.company
            FROM responses r
            JOIN leads l ON r.lead_id = l.id
            ORDER BY r.received_at DESC
            LIMIT 100
        """)

        responses = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return responses

    def log_response(self, email_id: int, lead_id: int, subject: str,
                     body: str, from_address: str) -> int:
        """Log a new response"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO responses (email_id, lead_id, subject, body, from_address, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (email_id, lead_id, subject, body, from_address, datetime.now()))

        response_id = cursor.lastrowid

        # Update email status
        cursor.execute("""
            UPDATE emails SET status = 'replied', replied_at = ? WHERE id = ?
        """, (datetime.now(), email_id))

        # Update lead status
        cursor.execute("""
            UPDATE leads SET status = 'responded', updated_at = ? WHERE id = ?
        """, (datetime.now(), lead_id))

        conn.commit()
        conn.close()
        return response_id

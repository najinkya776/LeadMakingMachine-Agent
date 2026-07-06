"""
Follow-up Service - Send automated follow-up emails
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict


class FollowUpService:
    def __init__(self, settings):
        self.settings = settings
        self.db_path = settings.db_path_absolute

    def schedule_followup(self, lead_id: int, email_id: int,
                          sequence_number: int = 1) -> int:
        """Schedule a follow-up email"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        scheduled_at = datetime.now() + timedelta(days=self.settings.FOLLOWUP_DELAY_DAYS)

        cursor.execute("""
            INSERT INTO followups (lead_id, email_id, sequence_number, scheduled_at, status)
            VALUES (?, ?, ?, ?, 'scheduled')
        """, (lead_id, email_id, sequence_number, scheduled_at))

        followup_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return followup_id

    def get_due_followups(self) -> List[Dict]:
        """Get follow-ups that are due to be sent"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT f.*, l.email, l.company, e.subject as original_subject
            FROM followups f
            JOIN leads l ON f.lead_id = l.id
            JOIN emails e ON f.email_id = e.id
            WHERE f.status = 'scheduled'
            AND f.scheduled_at <= ?
            AND f.sequence_number < ?
            ORDER BY f.scheduled_at ASC
        """, (datetime.now(), self.settings.FOLLOWUP_MAX_ATTEMPTS))

        followups = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return followups

    def send_followup(self, followup: Dict) -> bool:
        """Send a follow-up email"""
        from services.emailer import EmailService

        try:
            emailer = EmailService(self.settings)

            sequence_num = followup['sequence_number']
            company = followup['company']

            # Customize based on sequence number
            subjects = {
                1: f"Following up on my email - {company}",
                2: f"Quick question about {company}",
                3: f"Last try - partnership opportunity",
            }

            bodies = {
                1: f"""
                <html><body>
                <p>Hi,</p>
                <p>I wanted to follow up on my previous email regarding a potential partnership.
                I understand you're busy, so I'll keep this brief.</p>
                <p>Would you have 15 minutes this week for a quick call?</p>
                <p>Best regards,<br>{self.settings.EMAIL_FROM_NAME}</p>
                </body></html>
                """,
                2: f"""
                <html><body>
                <p>Hi,</p>
                <p>I reached out last week about collaboration opportunities with {company}.
                Just wanted to make sure my previous email reached you.</p>
                <p>Happy to work around your schedule.</p>
                <p>Best regards,<br>{self.settings.EMAIL_FROM_NAME}</p>
                </body></html>
                """,
                3: f"""
                <html><body>
                <p>Hi,</p>
                <p>This is my final follow-up. If timing isn't right for {company} right now,
                I completely understand. Feel free to reach out in the future if that changes.</p>
                <p>Best of luck with your business!</p>
                <p>Best regards,<br>{self.settings.EMAIL_FROM_NAME}</p>
                </body></html>
                """
            }

            subject = subjects.get(sequence_num, subjects[1])
            body = bodies.get(sequence_num, bodies[1])

            success = emailer.send_email(followup['email'], subject, body)

            if success:
                self._mark_followup_sent(followup['id'])

                # Schedule next follow-up if not at max
                if sequence_num < self.settings.FOLLOWUP_MAX_ATTEMPTS - 1:
                    self.schedule_followup(
                        followup['lead_id'],
                        followup['email_id'],
                        sequence_num + 1
                    )

            return success

        except Exception as e:
            print(f"[ERROR] Follow-up failed: {e}")
            return False

    def _mark_followup_sent(self, followup_id: int):
        """Mark follow-up as sent"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE followups SET status = 'sent', sent_at = ? WHERE id = ?
        """, (datetime.now(), followup_id))

        conn.commit()
        conn.close()

    def send_due_followups(self) -> int:
        """Send all due follow-ups"""
        due = self.get_due_followups()
        sent_count = 0

        for followup in due:
            if self.send_followup(followup):
                sent_count += 1

        return sent_count

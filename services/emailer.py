"""
Email Service - Send emails via SMTP
"""

import smtplib
import sqlite3
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict


class EmailService:
    def __init__(self, settings):
        self.settings = settings
        self.db_path = settings.db_path_absolute

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send single email via SMTP"""
        try:
            msg = MIMEMultipart()
            msg['From'] = f"{self.settings.EMAIL_FROM_NAME} <{self.settings.EMAIL_FROM}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html'))

            with smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT) as server:
                server.starttls()
                server.login(self.settings.SMTP_USER, self.settings.SMTP_PASSWORD)
                server.send_message(msg)

            return True

        except Exception as e:
            print(f"[ERROR] Failed to send to {to_email}: {e}")
            return False

    def get_leads_for_emailing(self, limit: int = 50) -> List[Dict]:
        """Get leads that need to be emailed"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT l.* FROM leads l
            LEFT JOIN emails e ON l.id = e.lead_id AND e.status = 'sent'
            WHERE l.status IN ('new', 'qualified')
            AND l.email IS NOT NULL AND l.email != ''
            GROUP BY l.id
            HAVING COUNT(e.id) = 0
            ORDER BY l.score DESC
            LIMIT ?
        """, (limit,))

        leads = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return leads

    def send_batch(self, limit: int = None) -> int:
        """Send batch of emails to leads"""
        if limit is None:
            limit = self.settings.DAILY_EMAIL_LIMIT

        leads = self.get_leads_for_emailing(limit)
        sent_count = 0

        for lead in leads:
            subject = f"Partnership Opportunity with {lead.get('company', 'Your Company')}"
            body = self._build_email_body(lead)

            if self.send_email(lead['email'], subject, body):
                self._record_sent_email(lead, subject, body)
                sent_count += 1

        print(f"[+] Sent {sent_count}/{len(leads)} emails")
        return sent_count

    def _build_email_body(self, lead: Dict) -> str:
        """Build personalized email body"""
        company = lead.get('company', 'there')

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <p>Hi,</p>

            <p>I noticed {company} and thought there might be an opportunity
            for us to work together. We help businesses streamline their
            operations and increase revenue through automated solutions.</p>

            <p>Would you be open to a brief call this week to explore
            potential synergies?</p>

            <p>Best regards,<br>
            {self.settings.EMAIL_FROM_NAME}</p>
        </body>
        </html>
        """

    def _record_sent_email(self, lead: Dict, subject: str, body: str):
        """Record sent email in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO emails (lead_id, subject, body, status, sent_at)
            VALUES (?, ?, ?, 'sent', ?)
        """, (lead['id'], subject, body, datetime.now()))

        cursor.execute("UPDATE leads SET status = 'emailed', updated_at = ? WHERE id = ?",
                       (datetime.now(), lead['id']))

        conn.commit()
        conn.close()

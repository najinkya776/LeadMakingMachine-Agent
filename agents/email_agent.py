"""Email agent for sending outreach emails with database tracking."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from lib.email_sender import EmailSender
from db.database import LeadDatabase, Lead, EmailRecord, LeadStatus
from config.settings import (
    EMAIL_SUBJECT_TEMPLATES,
    EMAIL_BODY_TEMPLATE,
    FOLLOWUP_TEMPLATE,
    CONTACT_INFO,
    EMAIL_SETTINGS,
)


@dataclass
class EmailResult:
    """Result of an email send attempt."""
    success: bool
    lead_id: int
    email: str
    message: str
    email_record_id: Optional[int] = None


class EmailAgent:
    """Agent for sending outreach emails to leads."""

    def __init__(self, db: LeadDatabase = None):
        """Initialize email agent."""
        self.db = db or LeadDatabase()
        self.sender = EmailSender()
        self.batch_size = EMAIL_SETTINGS.get("batch_size", 5)
        self.delay_seconds = EMAIL_SETTINGS.get("delay_between_emails_seconds", 30)

    def get_leads_to_contact(self, limit: int = 50) -> List[Lead]:
        """Fetch leads that need to be contacted."""
        return self.db.get_leads(
            status=LeadStatus.REPORT_GENERATED.value,
            limit=limit
        )

    def get_needs_contact_leads(self, limit: int = 50) -> List[Lead]:
        """Fetch leads with needs_contact status."""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM leads
            WHERE status = 'needs_contact'
            AND email IS NOT NULL
            AND email != ''
            AND contact_attempts = 0
            ORDER BY score DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()
        return [Lead(**dict(row)) for row in rows]

    def build_email_content(self, lead: Lead, email_type: str = "initial") -> Dict[str, str]:
        """Build email subject and body from templates."""
        # Get findings list from lead data
        findings_list = self._format_findings(lead)

        # Select random subject template
        import random
        subject_template = random.choice(EMAIL_SUBJECT_TEMPLATES)

        # Prepare template variables
        template_vars = {
            "business_name": lead.business_name or "your business",
            "owner_name": lead.owner_name or "",
            "industry": lead.industry or "local business",
            "location": lead.location or "your area",
            "findings_list": findings_list,
            "contact_name": CONTACT_INFO["business_name"],
            "email": CONTACT_INFO["email"],
            "whatsapp": CONTACT_INFO["whatsapp"],
            "one_line_reminder": "Your report is still attached below.",
        }

        # Build subject
        subject = subject_template.format(**template_vars)

        # Build body
        if email_type == "followup":
            body = FOLLOWUP_TEMPLATE.format(**template_vars)
        else:
            body = EMAIL_BODY_TEMPLATE.format(**template_vars)

        return {
            "subject": subject,
            "body": body,
        }

    def _format_findings(self, lead: Lead) -> str:
        """Format findings from lead data for email body."""
        findings = []

        # Try to parse findings JSON
        if lead.findings:
            try:
                findings_data = json.loads(lead.findings)
                if isinstance(findings_data, dict):
                    for key, value in findings_data.items():
                        if value and key not in ["lead_id", "timestamp", "business_name"]:
                            findings.append(f"- {key.replace('_', ' ').title()}: {value}")
            except:
                pass

        # If no structured findings, add basic info
        if not findings:
            if lead.rating > 0:
                findings.append(f"- Rating: {lead.rating} stars")
            if lead.reviews_count > 0:
                findings.append(f"- Reviews: {lead.reviews_count} Google reviews")
            if lead.website:
                findings.append("- Online presence detected")
            else:
                findings.append("- No website found - opportunity to reach more customers")

        # Limit to top 5 findings
        findings = findings[:5]

        if not findings:
            findings = ["- Quick analysis shows room for improvement"]

        return "\n".join(findings)

    def send_to_lead(self, lead: Lead, email_type: str = "initial") -> EmailResult:
        """Send email to a single lead and record in database."""
        # Skip if no email
        if not lead.email:
            return EmailResult(
                success=False,
                lead_id=lead.id,
                email="",
                message="No email address available"
            )

        # Build email content
        email_content = self.build_email_content(lead, email_type)

        # Get PDF report path if exists
        attachments = []
        if lead.findings:
            try:
                findings_data = json.loads(lead.findings)
                pdf_path = findings_data.get("pdf_report_path")
                if pdf_path:
                    attachments = [pdf_path]
            except:
                pass

        # Send email
        try:
            result = self.sender.send_email(
                to_email=lead.email,
                subject=email_content["subject"],
                body=email_content["body"],
                attachments=attachments if attachments else None,
            )

            success = result.get("success", False)

            # Record in database
            email_record = EmailRecord(
                lead_id=lead.id,
                email_type=email_type,
                subject=email_content["subject"],
                body=email_content["body"],
                pdf_report_path=attachments[0] if attachments else "",
                sent_at=datetime.now().isoformat(),
                delivered=success,
                bounce_reason="" if success else result.get("message", ""),
            )

            email_record_id = self.db.record_email(email_record)

            # Update lead status
            next_followup = (datetime.now() + timedelta(days=3)).isoformat()
            self.db.update_lead(
                lead.id,
                status=LeadStatus.CONTACTED.value,
                last_contacted=datetime.now().isoformat(),
                next_followup=next_followup,
                contact_attempts=lead.contact_attempts + 1
            )

            return EmailResult(
                success=success,
                lead_id=lead.id,
                email=lead.email,
                message=result.get("message", "Email sent"),
                email_record_id=email_record_id
            )

        except Exception as e:
            return EmailResult(
                success=False,
                lead_id=lead.id,
                email=lead.email,
                message=f"Error sending email: {str(e)}"
            )

    def send_bulk(self, leads: List[Lead] = None, max_emails: int = 5) -> List[EmailResult]:
        """Send emails to multiple leads with delays to avoid spam."""
        results = []

        # Get leads to contact if not provided
        if leads is None:
            leads_to_contact = self.get_leads_to_contact(limit=max_emails)
            needs_contact = self.get_needs_contact_leads(limit=max_emails)
            leads = leads_to_contact + needs_contact

        # Limit to batch size
        leads = leads[:max_emails]

        for i, lead in enumerate(leads):
            print(f"[{i+1}/{len(leads)}] Sending to {lead.email} ({lead.business_name})...")

            result = self.send_to_lead(lead)
            results.append(result)

            if result.success:
                print(f"  -> Success: {result.message}")
            else:
                print(f"  -> Failed: {result.message}")

            # Delay between emails (skip on last one)
            if i < len(leads) - 1:
                print(f"  Waiting {self.delay_seconds}s before next email...")
                time.sleep(self.delay_seconds)

        return results

    def run_campaign(self, max_emails: int = 5) -> Dict:
        """Run a full email campaign."""
        print("=" * 50)
        print("Starting Email Campaign")
        print("=" * 50)

        # Get leads
        report_generated = self.get_leads_to_contact(limit=max_emails)
        needs_contact = self.get_needs_contact_leads(limit=max_emails)
        all_leads = report_generated + needs_contact

        print(f"Found {len(report_generated)} leads with 'report_generated' status")
        print(f"Found {len(needs_contact)} leads with 'needs_contact' status")
        print(f"Sending to {min(len(all_leads), max_emails)} leads")
        print()

        # Send emails
        results = self.send_bulk(all_leads, max_emails=max_emails)

        # Summary
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        summary = {
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "results": results,
        }

        print()
        print("=" * 50)
        print("Campaign Complete")
        print(f"  Sent: {successful}/{len(results)}")
        print(f"  Failed: {failed}/{len(results)}")
        print("=" * 50)

        return summary


# Standalone execution
if __name__ == "__main__":
    agent = EmailAgent()

    # Run with custom max emails
    import sys
    max_emails = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    summary = agent.run_campaign(max_emails=max_emails)

    # Print results summary
    print("\nResults:")
    for result in summary["results"]:
        status = "OK" if result.success else "FAIL"
        print(f"  [{status}] {result.email} - {result.message}")
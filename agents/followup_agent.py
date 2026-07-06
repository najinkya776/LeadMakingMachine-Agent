"""Follow-up agent for leads that haven't responded."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass

from db.database import LeadDatabase, Lead, LeadStatus, EmailRecord
from config.settings import FOLLOWUP_TEMPLATE, FOLLOWUP, CONTACT_INFO
from lib.email_sender import EmailSender


logger = logging.getLogger(__name__)


@dataclass
class FollowUpResult:
    """Result of a follow-up operation."""
    leads_processed: int = 0
    emails_sent: int = 0
    marked_responded: int = 0
    marked_not_interested: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class FollowUpAgent:
    """Agent to manage follow-ups for unresponsive leads."""

    def __init__(self, db: Optional[LeadDatabase] = None):
        """Initialize the follow-up agent."""
        self.db = db or LeadDatabase()
        self.email_sender = EmailSender()
        self.max_followups = FOLLOWUP.get("max_followups", 2)
        self.days_between_followups = FOLLOWUP.get("days_between_followups", [3, 7])
        self.enabled = FOLLOWUP.get("enabled", True)

    def check_followups_needed(self) -> List[Lead]:
        """Get leads that need follow-up based on their status and next_followup date."""
        if not self.enabled:
            logger.info("Follow-up system is disabled")
            return []

        now = datetime.now().isoformat()

        # Get leads that:
        # 1. Have been contacted (status = contacted)
        # 2. Haven't responded yet
        # 3. Haven't exceeded max follow-ups
        # 4. Next follow-up date has passed (or is due today)
        candidates = self.db.get_leads(status=LeadStatus.CONTACTED.value, limit=100)

        followup_leads = []
        for lead in candidates:
            # Skip if exceeded max follow-ups
            if lead.contact_attempts >= self.max_followups:
                logger.debug(f"Lead {lead.id} exceeded max follow-ups ({lead.contact_attempts})")
                continue

            # Check if next_followup date has passed
            if lead.next_followup:
                try:
                    next_followup_dt = datetime.fromisoformat(lead.next_followup)
                    if next_followup_dt > datetime.now():
                        logger.debug(f"Lead {lead.id} follow-up not due yet (next: {lead.next_followup})")
                        continue
                except ValueError:
                    logger.warning(f"Invalid next_followup date for lead {lead.id}: {lead.next_followup}")
                    # If invalid date, include it for follow-up
                    followup_leads.append(lead)
                    continue

            followup_leads.append(lead)

        logger.info(f"Found {len(followup_leads)} leads needing follow-up")
        return followup_leads

    def send_followup_email(self, lead: Lead) -> dict:
        """Send a follow-up email to a lead."""
        # Determine which follow-up number this is
        followup_num = lead.contact_attempts + 1

        # Get days for this follow-up attempt
        if followup_num <= len(self.days_between_followups):
            days_wait = self.days_between_followups[followup_num - 1]
        else:
            days_wait = self.days_between_followups[-1]

        # Build email subject and body
        subject = f"Following up - {lead.business_name}"

        # Prepare template variables
        template_vars = {
            "owner_name": lead.owner_name or "there",
            "business_name": lead.business_name,
            "contact_name": CONTACT_INFO["business_name"],
            "email": CONTACT_INFO["email"],
            "whatsapp": CONTACT_INFO["whatsapp"],
            "one_line_reminder": self._get_one_line_reminder(followup_num),
        }

        # Render email body from template
        body = self._render_template(FOLLOWUP_TEMPLATE, template_vars)

        # Send the email
        if lead.email:
            result = self.email_sender.send_email(
                to_email=lead.email,
                subject=subject,
                body=body,
            )
        else:
            result = {
                "success": False,
                "message": "No email address available"
            }

        # If successful, update lead record
        if result.get("success"):
            # Record the email
            email_record = EmailRecord(
                lead_id=lead.id,
                email_type=f"followup_{followup_num}",
                subject=subject,
                body=body,
                sent_at=datetime.now().isoformat(),
            )
            self.db.record_email(email_record)

            # Update lead
            next_followup_days = self._get_next_followup_days(followup_num)
            self.db.update_lead(
                lead.id,
                contact_attempts=lead.contact_attempts + 1,
                last_contacted=datetime.now().isoformat(),
                next_followup=(datetime.now() + timedelta(days=next_followup_days)).isoformat(),
            )

            logger.info(f"Sent follow-up #{followup_num} to lead {lead.id} ({lead.business_name})")

        return result

    def _get_one_line_reminder(self, followup_num: int) -> str:
        """Get a brief reminder line based on follow-up number."""
        reminders = {
            1: "Just wanted to make sure you received the report.",
            2: "Wanted to follow up on my earlier message.",
            3: "Last quick check - still happy to share ideas if you're interested.",
        }
        return reminders.get(followup_num, "Just checking in!")

    def _get_next_followup_days(self, current_attempt: int) -> int:
        """Get days until next follow-up based on current attempt."""
        if current_attempt < len(self.days_between_followups):
            return self.days_between_followups[current_attempt]
        return self.days_between_followups[-1] if self.days_between_followups else 7

    def _render_template(self, template: str, vars: dict) -> str:
        """Render a template with variables."""
        result = template
        for key, value in vars.items():
            placeholder = f"{{{key}}}"
            result = result.replace(placeholder, str(value))
        return result

    def check_for_responses(self, lead: Lead) -> bool:
        """Check if a lead has responded (new inbound email)."""
        from db.database import Response

        responses = self.db.get_responses_for_lead(lead.id)
        for response in responses:
            if response.response_type in ["interested", "positive"]:
                return True
        return False

    def mark_responded(self, lead: Lead) -> bool:
        """Mark a lead as responded."""
        result = self.db.update_lead_status(lead.id, LeadStatus.RESPONDED.value)
        if result:
            logger.info(f"Marked lead {lead.id} ({lead.business_name}) as responded")
        return result

    def mark_not_interested(self, lead: Lead) -> bool:
        """Mark a lead as not interested and move to trash."""
        reason = f"After {lead.contact_attempts} follow-up attempts, no response received"
        result = self.db.trash_lead(lead.id, reason=reason)
        if result:
            logger.info(f"Marked lead {lead.id} ({lead.business_name}) as not interested and trashed")
        return result

    def process_lead(self, lead: Lead) -> dict:
        """Process a single lead for follow-up."""
        result = {
            "lead_id": lead.id,
            "business_name": lead.business_name,
            "success": False,
            "action": None,
            "message": "",
        }

        # Check if lead has responded
        if self.check_for_responses(lead):
            self.mark_responded(lead)
            result["action"] = "marked_responded"
            result["success"] = True
            result["message"] = "Lead has responded"
            return result

        # Check if exceeded max follow-ups
        if lead.contact_attempts >= self.max_followups:
            self.mark_not_interested(lead)
            result["action"] = "marked_not_interested"
            result["success"] = True
            result["message"] = f"Exceeded max follow-ups ({self.max_followups}), moved to trash"
            return result

        # Send follow-up email
        email_result = self.send_followup_email(lead)
        if email_result.get("success"):
            result["success"] = True
            result["action"] = "email_sent"
            result["message"] = email_result.get("message")
        else:
            result["message"] = email_result.get("message", "Failed to send email")

        return result

    def run_daily_followup(self) -> FollowUpResult:
        """Run daily follow-up check for all leads needing follow-up."""
        result = FollowUpResult()

        logger.info("Starting daily follow-up check...")

        # Get leads needing follow-up
        leads = self.check_followups_needed()
        result.leads_processed = len(leads)

        for lead in leads:
            try:
                process_result = self.process_lead(lead)

                if process_result["action"] == "email_sent":
                    result.emails_sent += 1
                elif process_result["action"] == "marked_responded":
                    result.marked_responded += 1
                elif process_result["action"] == "marked_not_interested":
                    result.marked_not_interested += 1

            except Exception as e:
                error_msg = f"Error processing lead {lead.id}: {str(e)}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        logger.info(
            f"Daily follow-up complete: {result.leads_processed} processed, "
            f"{result.emails_sent} emails sent, {result.marked_not_interested} trashed"
        )

        return result


def run_daily_followup() -> FollowUpResult:
    """
    Convenience function to run daily follow-up checks.

    This can be scheduled via cron or task scheduler:
    - Windows: Task Scheduler with: python path\\to\\followup_agent.py
    - Unix/Mac: cron with: 0 9 * * * python /path/to/followup_agent.py

    Or imported and called from your main pipeline:
        from agents.followup_agent import run_daily_followup
        result = run_daily_followup()
    """
    agent = FollowUpAgent()
    return agent.run_daily_followup()


if __name__ == "__main__":
    # Run when executed directly
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    result = run_daily_followup()
    print(f"\nFollow-up Summary:")
    print(f"  Leads processed: {result.leads_processed}")
    print(f"  Emails sent: {result.emails_sent}")
    print(f"  Marked as responded: {result.marked_responded}")
    print(f"  Marked not interested: {result.marked_not_interested}")
    if result.errors:
        print(f"  Errors: {len(result.errors)}")
        for error in result.errors:
            print(f"    - {error}")

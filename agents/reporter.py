"""Agent 10: Reporter Agent - Generate PDF reports and outreach messages."""

from typing import Optional, Dict
from pathlib import Path

from anthropic import Anthropic
from models import Lead, Audit, Report, ReportStatus, PricingTier
from config.prompts import get_prompt
from lib.pdf_generator import PDFGenerator, generate_pdf_report
from lib.email_sender import EmailSender, generate_outreach_message, send_outreach


class ReporterAgent:
    """Agent for generating final reports and handling outreach."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the reporter agent."""
        self.anthropic = Anthropic(api_key=api_key or None)
        self.pdf_generator = PDFGenerator()

    def run(
        self,
        lead: Lead,
        audit: Optional[Audit],
        score: int,
        classification: str,
        pitch: str,
        lead_type: str,
    ) -> Report:
        """
        Generate complete report for a lead.

        Args:
            lead: Lead object
            audit: Audit object (optional)
            score: Opportunity score
            classification: Score classification (high/medium/low)
            pitch: Pitch content
            lead_type: Type of lead

        Returns:
            Report object with all content and PDF path
        """
        print(f"[Reporter] Generating report for {lead.business_name}")

        # Create report object
        report = Report(
            lead_id=lead.id,
            opportunity_score=score,
            classification=classification,
            lead_type=lead_type,
            pitch_type="no_website" if not lead.website_url else "has_website",
            pitch_content=pitch,
            status=ReportStatus.GENERATING,
        )

        try:
            # Generate executive summary
            report.executive_summary = self._generate_summary(lead, score, classification)

            # Generate outreach messages
            outreach = self._generate_outreach(lead, pitch, classification)
            report.email_subject = outreach["email_subject"]
            report.email_body = outreach["email_body"]
            report.whatsapp_message = outreach["whatsapp_message"]

            # Determine pricing tier
            report.pricing_tier, report.pricing_estimate = self._determine_pricing(
                lead, audit, score
            )

            # Generate PDF
            pdf_path = generate_pdf_report(lead, audit, report)
            report.pdf_path = pdf_path
            report.pdf_generated = True

            # Mark complete
            report.status = ReportStatus.COMPLETED

            print(f"[Reporter] Report complete: {pdf_path}")
            return report

        except Exception as e:
            print(f"[Reporter] Report generation failed: {e}")
            report.status = ReportStatus.FAILED
            return report

    def _generate_summary(
        self,
        lead: Lead,
        score: int,
        classification: str,
    ) -> str:
        """Generate executive summary."""
        summary = f"{lead.business_name} is a {lead.category or 'local'} business "

        if lead.address:
            summary += f"in {lead.address} "

        if classification == "high":
            summary += f"with HIGH opportunity (score: {score}/100). "
            summary += "They have strong Google presence "
            if lead.review_count:
                summary += f"({lead.review_count} reviews) "
            summary += "but limited digital infrastructure. "
            summary += "A website would significantly increase their visibility and customer acquisition."

        elif classification == "medium":
            summary += f"with MODERATE opportunity (score: {score}/100). "
            summary += "They have some online presence but there are clear improvement areas. "
            summary += "Website improvements could help them compete more effectively."

        else:
            summary += f"with LOWER priority (score: {score}/100). "
            summary += "Consider for later outreach when higher-priority leads are exhausted."

        return summary

    def _generate_outreach(
        self,
        lead: Lead,
        pitch: str,
        classification: str,
    ) -> Dict:
        """Generate email and WhatsApp messages."""
        urgency = "high" if classification == "high" else "normal"

        # Email subject
        if classification == "high":
            email_subject = f"Can we help {lead.business_name} reach more customers?"
        elif classification == "medium":
            email_subject = f"Quick question about {lead.business_name}'s online presence"
        else:
            email_subject = f"Website ideas for {lead.business_name}"

        # Email body
        if lead.website_url:
            opening = f"We recently analyzed {lead.website_url} and found some great opportunities to improve your online presence."
        else:
            opening = f"We noticed {lead.business_name} has great reviews but doesn't have a website yet."

        email_body = f"""Hi {lead.business_name} team,

{opening}

Based on our analysis, we believe there's significant potential to help more customers discover and engage with your business.

We've prepared a detailed report with specific recommendations tailored for a business like yours.

Would you be open to a brief conversation about how we can help?

Best regards,
Website Pitcher Team
"""

        # WhatsApp message
        if classification == "high":
            whatsapp = f"Hi {lead.business_name}! 👋\n\nWe help businesses like yours get more customers through professional websites. Your Google reviews are great! Want to discuss how a website could help grow your business?\n\nReply YES for a free consultation."
        else:
            whatsapp = f"Hi {lead.business_name}!\n\nWe help local businesses improve their online presence. Would you be interested in hearing how we could help?\n\nReply YES or call us to learn more."

        return {
            "email_subject": email_subject,
            "email_body": email_body,
            "whatsapp_message": whatsapp,
        }

    def _determine_pricing(
        self,
        lead: Lead,
        audit: Optional[Audit],
        score: int,
    ) -> tuple:
        """Determine pricing tier and estimate."""
        # Base pricing by lead type
        if not lead.website_url:
            # No website - needs full site
            if score >= 80:
                return PricingTier.STANDARD, "₹30,000 - ₹50,000"
            else:
                return PricingTier.BASIC, "₹15,000 - ₹25,000"
        else:
            # Has website - needs improvements
            if score >= 80:
                return PricingTier.PREMIUM, "₹60,000 - ₹1,50,000"
            elif score >= 50:
                return PricingTier.STANDARD, "₹30,000 - ₹50,000"
            else:
                return PricingTier.BASIC, "₹15,000 - ₹25,000"

    def send_report(
        self,
        report: Report,
        lead: Lead,
        channel: str = "email",
    ) -> dict:
        """
        Send report via email or WhatsApp.

        Args:
            report: Report object
            lead: Lead object
            channel: 'email' or 'whatsapp'

        Returns:
            Result dictionary with success status
        """
        if not lead.email and channel == "email":
            return {"success": False, "message": "No email address available"}

        if not report.pdf_generated or not report.pdf_path:
            return {"success": False, "message": "PDF not generated"}

        print(f"[Reporter] Sending report via {channel} to {lead.business_name}")

        try:
            result = send_outreach(report, lead, channel, attach_pdf=True)

            if result.get("success"):
                report.email_sent = True
                report.status = ReportStatus.SENT

            return result

        except Exception as e:
            print(f"[Reporter] Send failed: {e}")
            return {"success": False, "message": str(e)}

    def generate_batch_reports(
        self,
        leads_data: list,
    ) -> list:
        """
        Generate reports for multiple leads.

        Args:
            leads_data: List of dicts with lead, audit, score, pitch, lead_type

        Returns:
            List of Report objects
        """
        reports = []

        for data in leads_data:
            report = self.run(
                lead=data["lead"],
                audit=data.get("audit"),
                score=data["score"],
                classification=data["classification"],
                pitch=data["pitch"],
                lead_type=data["lead_type"],
            )
            reports.append(report)

        return reports

    def create_summary_report(self, reports: list) -> Dict:
        """
        Create a summary report for multiple leads.

        Args:
            reports: List of Report objects

        Returns:
            Summary statistics and high-priority leads
        """
        high_priority = [r for r in reports if r.classification == "high"]
        medium_priority = [r for r in reports if r.classification == "medium"]
        low_priority = [r for r in reports if r.classification == "low"]

        avg_score = sum(r.opportunity_score for r in reports) / len(reports) if reports else 0

        summary = {
            "total_reports": len(reports),
            "high_priority_count": len(high_priority),
            "medium_priority_count": len(medium_priority),
            "low_priority_count": len(low_priority),
            "average_score": round(avg_score, 1),
            "emails_sent": sum(1 for r in reports if r.email_sent),
            "pdfs_generated": sum(1 for r in reports if r.pdf_generated),
            "high_priority_leads": [r.lead_id for r in high_priority],
        }

        return summary


def generate_lead_report(
    lead: Lead,
    audit: Optional[Audit],
    score: int,
    classification: str,
    pitch: str,
    lead_type: str,
) -> Report:
    """Convenience function to generate a lead report."""
    agent = ReporterAgent()
    return agent.run(lead, audit, score, classification, pitch, lead_type)
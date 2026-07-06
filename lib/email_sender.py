"""Email and WhatsApp sender for outreach."""

import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from config.settings import EMAIL_SETTINGS


class EmailSender:
    """Email sender for outreach campaigns."""

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
    ):
        """Initialize email sender."""
        self.smtp_host = smtp_host or EMAIL_SETTINGS["smtp_host"]
        self.smtp_port = smtp_port or EMAIL_SETTINGS["smtp_port"]
        self.smtp_user = smtp_user or EMAIL_SETTINGS["smtp_user"]
        self.smtp_password = smtp_password or EMAIL_SETTINGS["smtp_password"]
        self.from_name = EMAIL_SETTINGS["from_name"]
        self.from_email = EMAIL_SETTINGS["from_email"]

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
    ) -> dict:
        """Send an email."""
        result = {
            "success": False,
            "message": "",
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email

            if cc:
                msg["Cc"] = ", ".join(cc)

            # Attach body (both plain and HTML)
            part1 = MIMEText(body, "plain")
            part2 = MIMEText(self._htmlize_body(body), "html")

            msg.attach(part1)
            msg.attach(part2)

            # Add attachments
            if attachments:
                for filepath in attachments:
                    with open(filepath, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    filename = Path(filepath).name
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={filename}",
                    )
                    msg.attach(part)

            # Send email (port 465 needs SSL, port 587 needs STARTTLS)
            if self.smtp_port == 465:
                import ssl
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(
                        self.from_email,
                        [to_email] + (cc or []),
                        msg.as_string(),
                    )
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(
                        self.from_email,
                        [to_email] + (cc or []),
                        msg.as_string(),
                    )

            result["success"] = True
            result["message"] = f"Email sent to {to_email}"

        except Exception as e:
            result["message"] = f"Failed to send email: {str(e)}"

        return result

    def send_bulk(
        self,
        recipients: List[dict],
        subject_template: str,
        body_template: str,
    ) -> List[dict]:
        """Send bulk emails with template substitution."""
        results = []

        for recipient in recipients:
            # Substitute placeholders
            subject = self._substitute_template(subject_template, recipient)
            body = self._substitute_template(body_template, recipient)

            # Send email
            result = self.send_email(
                to_email=recipient.get("email", ""),
                subject=subject,
                body=body,
            )

            results.append({
                "email": recipient.get("email"),
                "result": result,
            })

        return results

    def _substitute_template(self, template: str, data: dict) -> str:
        """Substitute template placeholders with data."""
        result = template
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))
        return result

    def _htmlize_body(self, body: str) -> str:
        """Convert plain text body to basic HTML."""
        # Convert newlines to <br>
        html = body.replace("\n\n", "</p><p>")
        html = html.replace("\n", "<br>")
        html = f"<p>{html}</p>"

        # Add basic styling
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                {html}
            </body>
        </html>
        """

        return html


class WhatsAppMessage:
    """WhatsApp message generator."""

    # WhatsApp API formatting
    BOLD = "*"
    ITALIC = "_"
    STRIKETHROUGH = "~"

    @staticmethod
    def format(text: str, style: str = "bold") -> str:
        """Format text with WhatsApp styling."""
        if style == "bold":
            return f"*{text}*"
        elif style == "italic":
            return f"_{text}_"
        elif style == "strikethrough":
            return f"~{text}~"
        return text

    @staticmethod
    def create_message(
        business_name: str,
        pitch: str,
        cta: str = "Reply to this message to schedule a free consultation",
    ) -> str:
        """Create a WhatsApp message from pitch content."""
        message = f"Hi *{business_name}*,\n\n"

        # Add short pitch (first 200 chars)
        pitch_preview = pitch[:200] + "..." if len(pitch) > 200 else pitch
        message += f"{pitch_preview}\n\n"

        # Add CTA
        message += f"_{cta}_\n\n"

        # Signature
        message += "Best regards,\n"
        message += "Website Pitcher Team"

        # WhatsApp link (if phone available)
        message += "\n\n📱 Ready to discuss your website improvement?"

        return message

    @staticmethod
    def create_short_message(
        business_name: str,
        value_prop: str,
    ) -> str:
        """Create a short WhatsApp message."""
        return (
            f"Hi {WhatsAppMessage.format(business_name, 'bold')},\n\n"
            f"{value_prop}\n\n"
            f"Would you be open to a quick chat about how we can help?\n"
            f"Reply YES to schedule a free 15-min call."
        )


def generate_outreach_message(
    report,
    lead,
    channel: str = "email",
) -> dict:
    """Generate outreach message for a report."""
    if channel == "email":
        subject = f"Can we help improve {lead.business_name}'s online presence?"

        body = f"""
Hi {lead.business_name} team,

I hope this message finds you well. I recently came across your business on Google
and was impressed by what I found.

After analyzing your digital presence, I believe there's significant potential to
help more customers discover and engage with your business online.

Here's what I found:
• Your business has great reviews ({lead.review_count or 'N/A'} ratings)
• Your category: {lead.category or 'N/A'}

Would you be open to a brief conversation about how a professional website could
help grow your business? I'd be happy to share some ideas at no cost.

Let me know if you're interested, and I'll send over some suggestions.

Best regards,
Website Pitcher Team
        """

        return {
            "channel": "email",
            "subject": subject,
            "body": body.strip(),
        }

    elif channel == "whatsapp":
        message = WhatsAppMessage.create_short_message(
            business_name=lead.business_name,
            value_prop="We help local businesses get more customers through professional websites.",
        )

        return {
            "channel": "whatsapp",
            "message": message,
        }

    return {}


def send_outreach(
    report,
    lead,
    channel: str = "email",
    attach_pdf: bool = True,
) -> dict:
    """Send outreach message for a lead."""
    # Generate message
    message_data = generate_outreach_message(report, lead, channel)

    if channel == "email":
        sender = EmailSender()

        attachments = None
        if attach_pdf and report.pdf_path:
            attachments = [report.pdf_path]

        result = sender.send_email(
            to_email=lead.email or "",
            subject=message_data["subject"],
            body=message_data["body"],
            attachments=attachments,
        )

        return result

    elif channel == "whatsapp":
        # WhatsApp integration would go here
        # For now, return the message
        return {
            "success": True,
            "message": message_data["message"],
            "channel": "whatsapp",
        }

    return {"success": False, "message": "Unknown channel"}
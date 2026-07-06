"""Inbound email processor for handling incoming email leads."""

import imaplib
import email
from email.header import decode_header
import logging
from datetime import datetime
from typing import Optional, Tuple
import time
import threading
from enum import Enum

from config.settings import EMAIL_SETTINGS, INBOUND_EMAIL
from lib.email_sender import EmailSender
from models import Lead, LeadStatus, LeadType
import anthropic

logger = logging.getLogger(__name__)


class EmailIntent(str, Enum):
    """Email intent classification."""
    WANTS_WEBSITE = "wants_website"
    ASKING_QUESTION = "asking_question"
    SPAM = "spam"
    PROPOSAL_REQUEST = "proposal_request"
    UNKNOWN = "unknown"


class InboxProcessor:
    """Processes inbound emails from IMAP inbox."""

    def __init__(self):
        """Initialize the inbox processor."""
        self.imap_host = INBOUND_EMAIL.get("imap_host", "imap.gmail.com")
        self.imap_port = INBOUND_EMAIL.get("imap_port", 993)
        self.email_addr = INBOUND_EMAIL.get("email", "")
        self.app_password = INBOUND_EMAIL.get("app_password", "")
        self.poll_interval = INBOUND_EMAIL.get("poll_interval_seconds", 300)
        self.auto_reply_templates = INBOUND_EMAIL.get("auto_reply_templates", {})
        self.sender = EmailSender()
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._processed_ids: set = set()

        # Initialize Claude client
        self.claude_client = anthropic.Anthropic()

    def connect(self) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server."""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.email_addr, self.app_password)
            logger.info(f"Connected to IMAP server: {self.imap_host}")
            return mail
        except Exception as e:
            logger.error(f"Failed to connect to IMAP: {e}")
            raise

    def decode_email_header(self, header: str) -> str:
        """Decode email header (subject, sender name, etc.)."""
        decoded_parts = decode_header(header)
        result = ""
        for content, charset in decoded_parts:
            if isinstance(content, bytes):
                charset = charset or "utf-8"
                try:
                    result += content.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    result += content.decode("utf-8", errors="replace")
            else:
                result += content
        return result

    def parse_email(self, raw_email: bytes) -> dict:
        """Parse raw email into structured data."""
        msg = email.message_from_bytes(raw_email)

        # Extract headers
        subject = self.decode_email_header(msg.get("Subject", ""))
        sender = msg.get("From", "")
        recipient = msg.get("To", "")
        date = msg.get("Date", "")
        message_id = msg.get("Message-ID", "")

        # Parse sender email
        sender_email = ""
        sender_name = ""
        if "<" in sender:
            sender_name = sender.split("<")[0].strip().strip('"')
            sender_email = sender.split("<")[1].strip().rstrip(">")
        else:
            sender_email = sender

        # Extract body
        body = ""
        html_body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get_content_disposition())

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        body = part.get_payload(decode=True).decode(charset, errors="replace")
                    except Exception:
                        pass
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        html_body = part.get_payload(decode=True).decode(charset, errors="replace")
                    except Exception:
                        pass
        else:
            try:
                charset = msg.get_content_charset() or "utf-8"
                body = msg.get_payload(decode=True).decode(charset, errors="replace")
            except Exception:
                pass

        return {
            "subject": subject,
            "sender_email": sender_email,
            "sender_name": sender_name,
            "recipient": recipient,
            "date": date,
            "message_id": message_id,
            "body": body.strip(),
            "html_body": html_body,
        }

    def classify_intent(self, email_data: dict) -> EmailIntent:
        """Use Claude to classify the intent of an inbound email."""
        prompt = f"""Analyze this inbound email and classify the sender's intent.

Email Subject: {email_data['subject']}
Email Body:
{email_data['body'][:2000]}

Classify the intent into ONE of these categories:
- "wants_website" - They are interested in getting a website built
- "asking_question" - They have a question that needs human response
- "spam" - This is spam or irrelevant
- "proposal_request" - They want a custom proposal or quote

Respond with ONLY the category name in lowercase (e.g., "wants_website").

Consider these signals:
- Keywords like "website", "build", "create", "design", "develop" → wants_website
- Keywords like "quote", "proposal", "estimate", "pricing" → proposal_request
- Questions about services, timelines, process → asking_question
- Generic sales emails, marketing, suspicious content → spam
"""

        try:
            response = self.claude_client.messages.create(
                model="claude-opus-4-5",
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}]
            )
            intent_str = response.content[0].text.strip().lower()

            # Map response to enum
            intent_map = {
                "wants_website": EmailIntent.WANTS_WEBSITE,
                "asking_question": EmailIntent.ASKING_QUESTION,
                "spam": EmailIntent.SPAM,
                "proposal_request": EmailIntent.PROPOSAL_REQUEST,
            }
            return intent_map.get(intent_str, EmailIntent.UNKNOWN)

        except Exception as e:
            logger.error(f"Claude classification failed: {e}")
            return EmailIntent.UNKNOWN

    def save_human_needed(self, email_data: dict) -> None:
        """Save email requiring human response to database."""
        try:
            import psycopg2
            from config.database import DB_CONFIG

            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS human_needed (
                    id SERIAL PRIMARY KEY,
                    sender_email VARCHAR(255),
                    sender_name VARCHAR(255),
                    subject VARCHAR(500),
                    body TEXT,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'pending',
                    assigned_to VARCHAR(255),
                    resolved_at TIMESTAMP,
                    notes TEXT
                )
            """)

            cursor.execute("""
                INSERT INTO human_needed (sender_email, sender_name, subject, body)
                VALUES (%s, %s, %s, %s)
            """, (
                email_data["sender_email"],
                email_data["sender_name"],
                email_data["subject"],
                email_data["body"]
            ))

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Saved human-needed email from {email_data['sender_email']}")

        except Exception as e:
            logger.error(f"Failed to save human-needed email: {e}")

    def save_inbound_lead(self, email_data: dict, intent: EmailIntent, business_name: Optional[str] = None) -> Optional[str]:
        """Save inbound lead to database."""
        try:
            import psycopg2
            from config.database import DB_CONFIG

            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()

            # Create inbound_leads table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inbound_leads (
                    id VARCHAR(36) PRIMARY KEY,
                    source VARCHAR(50) DEFAULT 'email',
                    email VARCHAR(255),
                    sender_name VARCHAR(255),
                    subject VARCHAR(500),
                    body TEXT,
                    intent VARCHAR(50),
                    business_name VARCHAR(255),
                    phone VARCHAR(50),
                    status VARCHAR(50) DEFAULT 'new',
                    order_id VARCHAR(36),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            import uuid
            lead_id = str(uuid.uuid4())

            cursor.execute("""
                INSERT INTO inbound_leads (id, source, email, sender_name, subject, body, intent, business_name, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                lead_id,
                "email",
                email_data["sender_email"],
                email_data["sender_name"],
                email_data["subject"],
                email_data["body"],
                intent.value,
                business_name or email_data["sender_name"] or "Unknown",
                "qualified"
            ))

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Saved inbound lead {lead_id} from {email_data['sender_email']}")
            return lead_id

        except Exception as e:
            logger.error(f"Failed to save inbound lead: {e}")
            return None

    def generate_auto_reply(self, email_data: dict, intent: EmailIntent) -> Tuple[str, str]:
        """Generate automated reply based on intent."""
        sender_name = email_data["sender_name"] or "there"
        first_name = sender_name.split()[0] if sender_name else "there"

        if intent == EmailIntent.WANTS_WEBSITE:
            subject = f"Re: {email_data['subject']}" if email_data["subject"] else "Thanks for reaching out!"
            body = f"""Hi {first_name},

Thank you for your interest in getting a website! We'd love to help you establish a professional online presence.

Here are our website packages:

*Starter Website - $99*
- 5 custom pages
- Mobile responsive design
- Contact form included
- Delivery in 5 days

*Professional Website - $249*
- 10 custom pages
- Advanced SEO setup
- Google Analytics integration
- Delivery in 7 days

*Premium Website - $499*
- Unlimited pages
- E-commerce ready
- Payment gateway integration
- Delivery in 14 days

To get started, simply click the PayPal link for your chosen package:
- Starter: https://paypal.me/yourusername/99
- Professional: https://paypal.me/yourusername/249
- Premium: https://paypal.me/yourusername/499

After payment, we'll reach out within 24 hours to gather your requirements and begin the build.

Want to discuss your needs first? Book a free consultation call:
https://calendly.com/yourusername/consultation

Best regards,
Website Pitcher Team
"""
            return subject, body

        elif intent == EmailIntent.PROPOSAL_REQUEST:
            subject = f"Re: {email_data['subject']}"
            body = f"""Hi {first_name},

Thank you for your interest in a custom website proposal!

To create a tailored proposal for you, I'll need a few details:

1. What type of website do you need? (e-commerce, portfolio, business, etc.)
2. How many pages/sections?
3. Any specific features or integrations?
4. Do you have examples of websites you like?

Once I have these details, I can prepare a comprehensive proposal with exact pricing and timeline.

In the meantime, feel free to explore our standard packages:
- Starter: $99
- Professional: $249
- Premium: $499

Book a call to discuss your project:
https://calendly.com/yourusername/consultation

Looking forward to hearing from you!

Best regards,
Website Pitcher Team
"""
            return subject, body

        else:
            subject = f"Re: {email_data['subject']}"
            body = f"""Hi {first_name},

Thank you for reaching out!

I've received your message and someone from our team will get back to you within 24 hours.

If you have an urgent question, feel free to reply to this email or reach us directly.

Best regards,
Website Pitcher Team
"""
            return subject, body

    def send_auto_reply(self, to_email: str, subject: str, body: str) -> dict:
        """Send auto-reply email."""
        return self.sender.send_email(
            to_email=to_email,
            subject=subject,
            body=body
        )

    def trigger_proposal_pipeline(self, lead_id: str, email_data: dict) -> None:
        """Trigger the full Website Pitcher pipeline to generate a custom proposal."""
        try:
            from lib.build_trigger import trigger_proposal_generation
            trigger_proposal_generation(lead_id, email_data)
            logger.info(f"Triggered proposal generation for lead {lead_id}")
        except Exception as e:
            logger.error(f"Failed to trigger proposal pipeline: {e}")

    def process_emails(self) -> None:
        """Process all new emails in the inbox."""
        try:
            mail = self.connect()
            mail.select("INBOX")

            # Search for unread emails
            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                logger.warning("No messages found or search failed")
                return

            email_ids = messages[0].split()
            logger.info(f"Found {len(email_ids)} new emails to process")

            for email_id in email_ids:
                try:
                    # Fetch email
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    email_data = self.parse_email(raw_email)

                    # Skip if already processed (by message ID)
                    if email_data["message_id"] in self._processed_ids:
                        continue

                    self._processed_ids.add(email_data["message_id"])
                    logger.info(f"Processing email from {email_data['sender_email']}")

                    # Classify intent
                    intent = self.classify_intent(email_data)
                    logger.info(f"Email intent: {intent}")

                    if intent == EmailIntent.SPAM:
                        # Archive silently
                        mail.store(email_id, "+FLAGS", "\\Archived")
                        logger.info(f"Archived spam from {email_data['sender_email']}")

                    elif intent == EmailIntent.WANTS_WEBSITE:
                        # Save lead and send auto-reply
                        lead_id = self.save_inbound_lead(email_data, intent)
                        subject, body = self.generate_auto_reply(email_data, intent)
                        self.send_auto_reply(email_data["sender_email"], subject, body)
                        logger.info(f"Processed wants_website email, saved lead {lead_id}")

                    elif intent == EmailIntent.PROPOSAL_REQUEST:
                        # Save lead, send auto-reply, and trigger proposal pipeline
                        lead_id = self.save_inbound_lead(email_data, intent)
                        subject, body = self.generate_auto_reply(email_data, intent)
                        self.send_auto_reply(email_data["sender_email"], subject, body)
                        self.trigger_proposal_pipeline(lead_id, email_data)
                        logger.info(f"Processed proposal_request, saved lead {lead_id}")

                    elif intent == EmailIntent.ASKING_QUESTION:
                        # Forward to human
                        self.save_human_needed(email_data)
                        subject, body = self.generate_auto_reply(email_data, intent)
                        self.send_auto_reply(email_data["sender_email"], subject, body)
                        logger.info(f"Saved asking_question for human review")

                    else:
                        # Unknown intent - treat as asking_question
                        self.save_human_needed(email_data)
                        logger.warning(f"Unknown intent for email from {email_data['sender_email']}")

                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {e}")
                    continue

            mail.logout()

        except Exception as e:
            logger.error(f"Failed to process emails: {e}")

    def start_polling(self) -> None:
        """Start polling for new emails in a background thread."""
        if self.running:
            logger.warning("Inbox processor already running")
            return

        self.running = True

        def poll_loop():
            while self.running:
                try:
                    self.process_emails()
                except Exception as e:
                    logger.error(f"Polling error: {e}")

                # Sleep for poll interval
                for _ in range(self.poll_interval):
                    if not self.running:
                        break
                    time.sleep(1)

        self._thread = threading.Thread(target=poll_loop, daemon=True)
        self._thread.start()
        logger.info(f"Started inbox polling (interval: {self.poll_interval}s)")

    def stop_polling(self) -> None:
        """Stop polling for new emails."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Stopped inbox polling")


def start_inbox_processor() -> InboxProcessor:
    """Start the inbox processor as a background service."""
    processor = InboxProcessor()

    # Only start if IMAP credentials are configured
    if INBOUND_EMAIL.get("email") and INBOUND_EMAIL.get("app_password"):
        processor.start_polling()
    else:
        logger.warning("Inbound email not configured. Set INBOUND_EMAIL and INBOUND_EMAIL_PASSWORD in .env")

    return processor


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    processor = InboxProcessor()
    processor.process_emails()  # Run once for testing

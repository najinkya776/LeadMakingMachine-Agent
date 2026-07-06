"""Response Parser Agent - Handles replies to cold emails."""

import imaplib
import email
import re
import logging
from datetime import datetime
from typing import Optional
from email.header import decode_header
from enum import Enum

import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ResponseType(str, Enum):
    """Classification of email response type."""
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    NEUTRAL = "neutral"


class ResponseParserAgent:
    """Parses incoming email replies to cold emails and updates lead status."""

    # Patterns that indicate positive response
    INTERESTED_PATTERNS = [
        r"\binterested\b",
        r"\byes\b",
        r"\bplease\b",
        r"\btell me more\b",
        r"\bwant\b",
        r"\bneed\b",
        r"\blike to\b",
        r"\bconsidering\b",
        r"\bexploring\b",
        r"\bhelp me\b",
        r"\bhow much\b",
        r"\bcost\b",
        r"\bprice\b",
        r"\bpricing\b",
        r"\bschedule\b",
        r"\bcall\b",
        r"\bmeet\b",
        r"\bdiscuss\b",
        r"\bcool\b",
        r"\bawesome\b",
        r"\bgreat\b",
        r"\bthanks for\b",
        r"\battacheds?\b",
        r"\bsaw your\b",
        r"\bgot the\b",
        r"\bchecked\b",
        r"\blooked at\b",
        r"\bgood point\b",
    ]

    # Patterns that indicate negative response
    NOT_INTERESTED_PATTERNS = [
        r"\bnot interested\b",
        r"\bnot interested\b",
        r"\bstop\b",
        r"\bremove\b",
        r"\bunsubscribe\b",
        r"\bdo not contact\b",
        r"\bdo not email\b",
        r"\bno thanks\b",
        r"\bnot now\b",
        r"\bnot looking\b",
        r"\bnot looking for\b",
        r"\balready have\b",
        r"\balready got\b",
        r"\busing someone\b",
    ]

    # Patterns that indicate email is a reply to our cold email
    REPLY_INDICATORS = [
        r"re:\s*\w+",  # "Re:" prefix
        r"fw:\s*\w+",  # "Fw:" prefix
        r"subject:",  # Forwarded emails
        r">",  # Quoted reply text
        r"on\s+\d+/\d+/\d+.*wrote:",  # Gmail style reply header
        r"from:\s+\w+",  # Email forwards
        r"original message",  # Forwarded original
    ]

    def __init__(self):
        """Initialize the response parser."""
        self.imap_host = "imap.hostinger.com"
        self.imap_port = 993
        self.email_addr = "__EMAIL_REDACTED__"
        self.password = "Welovethis1@+"
        self.processed_folder = "Processed"

        # Initialize Claude for more nuanced classification
        self.claude_client = anthropic.Anthropic()

    def _get_env_or_default(self, key: str, default: str) -> str:
        """Get value from environment or return default."""
        import os
        return os.getenv(key, default)

    def connect(self) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server."""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.email_addr, self.password)
            logger.info(f"Connected to IMAP server: {self.imap_host}")
            return mail
        except Exception as e:
            logger.error(f"Failed to connect to IMAP: {e}")
            raise

    def decode_header(self, header: str) -> str:
        """Decode email header (subject, sender name, etc.)."""
        if not header:
            return ""
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
        subject = self.decode_header(msg.get("Subject", ""))
        sender = msg.get("From", "")
        recipient = msg.get("To", "")
        date = msg.get("Date", "")
        message_id = msg.get("Message-ID", "")
        in_reply_to = msg.get("In-Reply-To", "")
        references = msg.get("References", "")

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
            "sender_email": sender_email.lower().strip(),
            "sender_name": sender_name,
            "recipient": recipient,
            "date": date,
            "message_id": message_id,
            "in_reply_to": in_reply_to,
            "references": references,
            "body": body.strip(),
            "html_body": html_body,
        }

    def is_reply_to_our_email(self, email_data: dict) -> bool:
        """Check if email is a reply to our cold email."""
        subject = email_data.get("subject", "").lower()

        # Check for Re: prefix (common reply indicator)
        if subject.startswith("re:"):
            return True

        # Check for forwarded emails
        if subject.startswith("fw:"):
            return True

        # Check body for quoted reply patterns
        body = email_data.get("body", "")

        # Look for "> " which indicates quoted text (reply)
        if re.search(r"^>", body, re.MULTILINE):
            return True

        # Look for common email client reply headers
        if re.search(r"on \d+/\d+/\d+|from:|original message", body, re.IGNORECASE):
            return True

        # Check if sender email is in our sent folder wassent to
        # (This would require tracking sent emails, we can add tracking later)
        return False

    def classify_response(self, email_data: dict) -> ResponseType:
        """Classify the response type based on email content."""
        body = email_data.get("body", "").lower()
        subject = email_data.get("subject", "").lower()
        combined_text = f"{subject} {body}"

        # First, check for negative patterns
        for pattern in self.NOT_INTERESTED_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                logger.info(f"Matched NOT_INTERESTED pattern: {pattern}")
                return ResponseType.NOT_INTERESTED

        # Then, check for positive patterns
        for pattern in self.INTERESTED_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                logger.info(f"Matched INTERESTED pattern: {pattern}")
                return ResponseType.INTERESTED

        # Use Claude for nuanced classification
        try:
            return self._claude_classify(combined_text)
        except Exception as e:
            logger.error(f"Claude classification failed: {e}")
            return ResponseType.NEUTRAL

    def _claude_classify(self, text: str) -> ResponseType:
        """Use Claude to classify email response."""
        prompt = f"""Analyze this email reply and classify the sender's intent.

Email preview:
{text[:1500]}

Classify the response as ONE of these:
- "interested" - The sender is showing interest in our services (asking about pricing, wanting more info, saying yes, expressing enthusiasm)
- "not_interested" - The sender clearly does not want to be contacted or is rejecting our offer
- "neutral" - The sender hasn't indicated clear interest or disinterest (just acknowledging, asking questions, etc.)

Respond with ONLY ONE of these exact words: interested, not_interested, or neutral"""

        try:
            response = self.claude_client.messages.create(
                model="claude-opus-4-7",
                max_tokens=20,
                messages=[{"role": "user", "content": prompt}]
            )
            result = response.content[0].text.strip().lower()

            if result in ["interested", "not_interested", "neutral"]:
                return ResponseType(result)
            return ResponseType.NEUTRAL

        except Exception as e:
            logger.error(f"Claude classification error: {e}")
            return ResponseType.NEUTRAL

    def find_lead_by_email(self, sender_email: str) -> Optional[dict]:
        """Find lead by email address in database."""
        try:
            import psycopg2
            from config.database import DB_CONFIG

            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, business_name, email, status
                FROM leads
                WHERE LOWER(email) = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (sender_email,))

            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if row:
                return {
                    "id": row[0],
                    "business_name": row[1],
                    "email": row[2],
                    "status": row[3]
                }
            return None

        except Exception as e:
            logger.error(f"Failed to find lead by email: {e}")
            return None

    def record_response(self, email_data: dict, response_type: ResponseType) -> Optional[str]:
        """Record the response in the database."""
        try:
            import psycopg2
            from config.database import DB_CONFIG

            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()

            # Create email_responses table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_responses (
                    id SERIAL PRIMARY KEY,
                    lead_id VARCHAR(36),
                    sender_email VARCHAR(255),
                    sender_name VARCHAR(255),
                    subject VARCHAR(500),
                    body TEXT,
                    response_type VARCHAR(50),
                    is_reply BOOLEAN DEFAULT TRUE,
                    message_id VARCHAR(500),
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Find lead
            lead = self.find_lead_by_email(email_data["sender_email"])
            lead_id = lead["id"] if lead else None

            # Insert response
            cursor.execute("""
                INSERT INTO email_responses
                (lead_id, sender_email, sender_name, subject, body, response_type, is_reply, message_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                lead_id,
                email_data["sender_email"],
                email_data["sender_name"],
                email_data["subject"],
                email_data["body"],
                response_type.value,
                True,
                email_data["message_id"]
            ))

            response_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Recorded email response {response_id} for {email_data['sender_email']}")
            return str(response_id)

        except Exception as e:
            logger.error(f"Failed to record response: {e}")
            return None

    def update_lead_status(self, sender_email: str, response_type: ResponseType) -> bool:
        """Update lead status based on response type."""
        try:
            import psycopg2
            from config.database import DB_CONFIG

            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()

            if response_type == ResponseType.INTERESTED:
                new_status = "pitching"
            elif response_type == ResponseType.NOT_INTERESTED:
                new_status = "completed"  # Mark as completed (no further action)
            else:
                new_status = None

            if new_status:
                cursor.execute("""
                    UPDATE leads
                    SET status = %s, updated_at = %s
                    WHERE LOWER(email) = %s
                    AND status != 'completed'
                    AND status != 'failed'
                """, (new_status, datetime.utcnow(), sender_email))

                rows_affected = cursor.rowcount
                conn.commit()
                cursor.close()
                conn.close()

                if rows_affected > 0:
                    logger.info(f"Updated lead {sender_email} status to {new_status}")
                    return True
                else:
                    logger.info(f"No lead found to update for {sender_email} (may already be completed)")
                    return False
            else:
                cursor.close()
                conn.close()
                return False

        except Exception as e:
            logger.error(f"Failed to update lead status: {e}")
            return False

    def create_processed_folder(self, mail: imaplib.IMAP4_SSL) -> None:
        """Create Processed folder if it doesn't exist."""
        try:
            # Try to create the folder
            status, _ = mail.create(self.processed_folder)
            if status == "OK":
                logger.info(f"Created folder: {self.processed_folder}")
            elif status == "NO":
                # Folder might already exist
                pass
        except Exception as e:
            logger.debug(f"Folder creation check: {e}")

    def move_to_processed(self, mail: imaplib.IMAP4_SSL, email_id: bytes) -> bool:
        """Move email to Processed folder."""
        try:
            # Create folder if needed
            self.create_processed_folder(mail)

            # First copy to Processed
            status, _ = mail.copy(email_id, self.processed_folder)
            if status != "OK":
                logger.warning(f"Failed to copy email to {self.processed_folder}")
                return False

            # Then mark original as deleted
            status, _ = mail.store(email_id, "+FLAGS", "\\Deleted")
            if status != "OK":
                logger.warning("Failed to mark email as deleted")
                return False

            # Expunge to actually delete
            mail.expunge()
            return True

        except Exception as e:
            logger.error(f"Failed to move email to processed: {e}")
            return False

    def process_emails(self) -> dict:
        """Process all new emails in the inbox."""
        results = {
            "processed": 0,
            "interested": 0,
            "not_interested": 0,
            "neutral": 0,
            "errors": 0
        }

        try:
            mail = self.connect()
            mail.select("INBOX")

            # Search for unread emails
            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                logger.warning("No messages found or search failed")
                return results

            email_ids = messages[0].split()
            logger.info(f"Found {len(email_ids)} new emails to process")

            for email_id in email_ids:
                try:
                    # Fetch email
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    if status != "OK":
                        results["errors"] += 1
                        continue

                    raw_email = msg_data[0][1]
                    email_data = self.parse_email(raw_email)

                    logger.info(f"Processing email from {email_data['sender_email']}")

                    # Check if it's a reply to our cold email
                    is_reply = self.is_reply_to_our_email(email_data)

                    if not is_reply:
                        # Not a cold email reply, skip or handle differently
                        logger.info(f"Email from {email_data['sender_email']} is not a reply, skipping")
                        # Mark as seen but don't move
                        mail.store(email_id, "+FLAGS", "\\Seen")
                        continue

                    # Classify the response
                    response_type = self.classify_response(email_data)
                    logger.info(f"Email response type: {response_type.value}")

                    # Record the response in database
                    self.record_response(email_data, response_type)

                    # Update lead status if applicable
                    self.update_lead_status(email_data["sender_email"], response_type)

                    # Move to Processed folder
                    if self.move_to_processed(mail, email_id):
                        logger.info(f"Moved email to {self.processed_folder}")
                    else:
                        # Just mark as seen if move failed
                        mail.store(email_id, "+FLAGS", "\\Seen")

                    results["processed"] += 1
                    if response_type == ResponseType.INTERESTED:
                        results["interested"] += 1
                    elif response_type == ResponseType.NOT_INTERESTED:
                        results["not_interested"] += 1
                    else:
                        results["neutral"] += 1

                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {e}")
                    results["errors"] += 1
                    continue

            mail.logout()

        except Exception as e:
            logger.error(f"Failed to process emails: {e}")
            results["errors"] += 1

        return results


def run_response_parser() -> dict:
    """Run the response parser once and return results."""
    agent = ResponseParserAgent()
    return agent.process_emails()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("Starting Response Parser Agent...")
    results = run_response_parser()
    print(f"Results: {results}")

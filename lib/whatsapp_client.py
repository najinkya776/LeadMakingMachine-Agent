"""WhatsApp Business API client for inbound message handling."""

import logging
from typing import Optional, Dict, Any
from enum import Enum

import httpx
import anthropic

from config.payment import PACKAGES, get_payment_link

logger = logging.getLogger(__name__)


class WhatsAppIntent(str, Enum):
    """WhatsApp message intent classification."""
    OFFER_INFO = "offer_info"
    TIMELINE = "timeline"
    PRICING = "pricing"
    INTERESTED = "interested"
    TALK_HUMAN = "talk_human"
    GREETING = "greeting"
    UNKNOWN = "unknown"


class WhatsAppClient:
    """WhatsApp Business API client for receiving and sending messages."""

    def __init__(self):
        """Initialize WhatsApp client."""
        # Twilio WhatsApp configuration
        self.twilio_account_sid = None
        self.twilio_auth_token = None
        self.twilio_whatsapp_number = None

        # Meta WhatsApp Business API configuration
        self.meta_access_token = None
        self.meta_phone_number_id = None
        self.meta_verify_token = None

        # Claude client for intent classification
        self.claude_client = anthropic.Anthropic()

        self._load_config()

    def _load_config(self) -> None:
        """Load WhatsApp configuration from environment."""
        from dotenv import load_dotenv
        load_dotenv()
        import os

        # Twilio config
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER")

        # Meta WhatsApp Business API config
        self.meta_access_token = os.getenv("WHATSAPP_META_ACCESS_TOKEN")
        self.meta_phone_number_id = os.getenv("WHATSAPP_META_PHONE_NUMBER_ID")
        self.meta_verify_token = os.getenv("WHATSAPP_META_VERIFY_TOKEN")

    def verify_webhook(self, mode: str, token: str, challenge: str) -> bool:
        """Verify webhook for Twilio/Meta WhatsApp webhook setup."""
        if mode == "subscribe" and token == self.meta_verify_token:
            logger.info("WhatsApp webhook verified successfully")
            return True
        return False

    def classify_message(self, message_text: str) -> WhatsAppIntent:
        """Use Claude to classify the intent of a WhatsApp message."""
        prompt = f"""Analyze this WhatsApp message and classify the sender's intent.

Message:
{message_text[:500]}

Classify the intent into ONE of these categories:
- "offer_info" - Asking about services/what we offer
- "timeline" - Asking about delivery time/how long
- "pricing" - Asking about price/cost
- "interested" - Expressing interest in getting a website
- "talk_human" - Wants to talk to a human
- "greeting" - Just greeting or saying hello
- "unknown" - Doesn't fit other categories

Respond with ONLY the category name in lowercase.

Key signals:
- "what do you offer", "services", "what can you do" → offer_info
- "how long", "timeline", "delivery", "when" → timeline
- "price", "cost", "how much", "pricing" → pricing
- "interested", "want", "need website", "build" → interested
- "human", "real person", "talk to someone" → talk_human
- "hi", "hello", "hey" → greeting (unless also asking questions)
"""

        try:
            response = self.claude_client.messages.create(
                model="claude-opus-4-5",
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}]
            )
            intent_str = response.content[0].text.strip().lower()

            intent_map = {
                "offer_info": WhatsAppIntent.OFFER_INFO,
                "timeline": WhatsAppIntent.TIMELINE,
                "pricing": WhatsAppIntent.PRICING,
                "interested": WhatsAppIntent.INTERESTED,
                "talk_human": WhatsAppIntent.TALK_HUMAN,
                "greeting": WhatsAppIntent.GREETING,
            }
            return intent_map.get(intent_str, WhatsAppIntent.UNKNOWN)

        except Exception as e:
            logger.error(f"Claude classification failed: {e}")
            return WhatsAppIntent.UNKNOWN

    def generate_response(self, intent: WhatsAppIntent, business_name: Optional[str] = None) -> str:
        """Generate automated response based on intent."""
        name = business_name or ""

        responses = {
            WhatsAppIntent.OFFER_INFO: f"""Hi {name}! 👋 Thanks for reaching out!

We build professional websites for businesses like yours. Here's what we offer:

🔥 *Starter Website - $99*
• 5 pages, mobile responsive
• Contact form included
• 5-day delivery

🚀 *Professional - $249*
• 10 pages, advanced SEO
• Google Analytics
• 7-day delivery

💎 *Premium - $499*
• Unlimited pages
• E-commerce ready
• 14-day delivery

Which package interests you? Or want to chat about your specific needs?""",

            WhatsAppIntent.TIMELINE: f"""Great question! {name}! ⏱️

Delivery times:
• Starter Website: 5 business days
• Professional Website: 7 business days
• Premium Website: 14 business days

We start work immediately after receiving your requirements and payment.

Need it faster? Let us know - we can often accommodate rush orders!""",

            WhatsAppIntent.PRICING: f"""Hi {name}! 💰 Here's our pricing:

• Starter: $99 (5 pages)
• Professional: $249 (10 pages)
• Premium: $499 (unlimited + e-commerce)

All packages include:
✓ Mobile responsive design
✓ Contact forms
✓ Basic SEO setup
✓ Free revisions

Ready to start? Click a link below:
🔗 Starter: https://paypal.me/yourusername/99
🔗 Professional: https://paypal.me/yourusername/249
🔗 Premium: https://paypal.me/yourusername/499""",

            WhatsAppIntent.INTERESTED: f"""Awesome, {name}! 🎉 We'd love to help you get your website!

Here's how it works:
1️⃣ Choose your package
2️⃣ Pay via the link
3️⃣ We reach out for requirements
4️⃣ We build your website
5️⃣ You review & approve

Ready to get started? Choose your package:
🔗 Starter ($99): https://paypal.me/yourusername/99
🔗 Professional ($249): https://paypal.me/yourusername/249
🔗 Premium ($499): https://paypal.me/yourusername/499

Or book a free call to discuss: https://calendly.com/yourusername/consultation""",

            WhatsAppIntent.TALK_HUMAN: f"""Hi {name}! No problem at all! 👋

I've flagged your conversation for one of our team members to reach out. We typically respond within 2-4 hours during business hours.

In the meantime, feel free to:
• Browse our packages above
• Book a call directly: https://calendly.com/yourusername/consultation

We'll be in touch soon!""",

            WhatsAppIntent.GREETING: f"""Hi {name}! 👋 Welcome to Website Pitcher!

We help local businesses get professional websites up and running.

What can we help you with today?
• Want to know our packages? → Reply "packages"
• Need a quote? → Reply "pricing"
• Ready to start? → Reply "interested"
• Or just tell us what you have in mind!""",

            WhatsAppIntent.UNKNOWN: f"""Hi {name}! Thanks for your message! 🙏

I'm an automated assistant here to help you get a website. Here's a quick overview:

📦 *Packages:*
• Starter: $99
• Professional: $249
• Premium: $499

🕐 *Timeline:* 5-14 days depending on package

Want more details? Just reply with your question or:
• Type "packages" for full service details
• Type "pricing" for price info
• Type "interested" if you're ready to start

Or book a call: https://calendly.com/yourusername/consultation""",
        }

        return responses.get(intent, responses[WhatsAppIntent.UNKNOWN])

    def save_whatsapp_lead(self, phone: str, message: str, intent: WhatsAppIntent) -> Optional[str]:
        """Save WhatsApp lead to database."""
        try:
            import psycopg2
            from config.database import DB_CONFIG
            import uuid

            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()

            # Create inbound_leads table if not exists (same table as email)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inbound_leads (
                    id VARCHAR(36) PRIMARY KEY,
                    source VARCHAR(50) DEFAULT 'whatsapp',
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

            lead_id = str(uuid.uuid4())

            cursor.execute("""
                INSERT INTO inbound_leads (id, source, phone, body, intent, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                lead_id,
                "whatsapp",
                phone,
                message,
                intent.value,
                "qualified" if intent == WhatsAppIntent.INTERESTED else "new"
            ))

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Saved WhatsApp lead {lead_id} from {phone}")
            return lead_id

        except Exception as e:
            logger.error(f"Failed to save WhatsApp lead: {e}")
            return None

    def send_via_twilio(self, to_number: str, message: str) -> Dict[str, Any]:
        """Send message via Twilio WhatsApp API."""
        if not self.twilio_account_sid or not self.twilio_auth_token:
            logger.warning("Twilio not configured")
            return {"success": False, "error": "Twilio not configured"}

        try:
            from twilio.rest import Client

            client = Client(self.twilio_account_sid, self.twilio_auth_token)

            response = client.messages.create(
                body=message,
                from_=f"whatsapp:{self.twilio_whatsapp_number}",
                to=f"whatsapp:{to_number}"
            )

            logger.info(f"Twilio message sent: {response.sid}")
            return {"success": True, "message_sid": response.sid}

        except ImportError:
            logger.error("Twilio library not installed")
            return {"success": False, "error": "Twilio not installed"}
        except Exception as e:
            logger.error(f"Twilio send failed: {e}")
            return {"success": False, "error": str(e)}

    def send_via_meta(self, to_number: str, message: str) -> Dict[str, Any]:
        """Send message via Meta WhatsApp Business API."""
        if not self.meta_access_token or not self.meta_phone_number_id:
            logger.warning("Meta WhatsApp API not configured")
            return {"success": False, "error": "Meta WhatsApp not configured"}

        try:
            url = f"https://graph.facebook.com/v18.0/{self.meta_phone_number_id}/messages"

            headers = {
                "Authorization": f"Bearer {self.meta_access_token}",
                "Content-Type": "application/json"
            }

            data = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": message
                }
            }

            with httpx.Client() as client:
                response = client.post(url, json=data, headers=headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Meta WhatsApp message sent: {result.get('messages', [{}])[0].get('id')}")
                return {"success": True, "message_id": result.get("messages", [{}])[0].get("id")}
            else:
                logger.error(f"Meta API error: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}

        except Exception as e:
            logger.error(f"Meta WhatsApp send failed: {e}")
            return {"success": False, "error": str(e)}

    def send_reply(self, to_number: str, message: str) -> Dict[str, Any]:
        """Send reply message using configured provider."""
        # Prefer Twilio if configured
        if self.twilio_account_sid and self.twilio_auth_token:
            if self.twilio_whatsapp_number:
                return self.send_via_twilio(to_number, message)

        # Fallback to Meta API
        if self.meta_access_token:
            return self.send_via_meta(to_number, message)

        logger.error("No WhatsApp provider configured")
        return {"success": False, "error": "No WhatsApp provider configured"}

    def process_inbound_message(self, from_number: str, message: str, sender_name: Optional[str] = None) -> Dict[str, Any]:
        """Process an inbound WhatsApp message and send auto-reply."""
        # Classify intent
        intent = self.classify_message(message)

        # Generate response
        response = self.generate_response(intent, sender_name)

        # Send reply
        send_result = self.send_reply(from_number, response)

        # Save lead if interested
        lead_id = None
        if intent in [WhatsAppIntent.INTERESTED, WhatsAppIntent.OFFER_INFO]:
            lead_id = self.save_whatsapp_lead(from_number, message, intent)

        return {
            "success": send_result.get("success", False),
            "intent": intent.value,
            "response_sent": bool(response),
            "lead_id": lead_id,
            "message_id": send_result.get("message_sid") or send_result.get("message_id"),
        }

    def handle_twilio_webhook(self, request_data: dict) -> Dict[str, Any]:
        """Handle incoming Twilio WhatsApp webhook."""
        from_number = request_data.get("From", "").replace("whatsapp:", "")
        message = request_data.get("Body", "").strip()

        if not message:
            return {"success": False, "error": "No message body"}

        return self.process_inbound_message(from_number, message)

    def handle_meta_webhook(self, request_data: dict) -> Dict[str, Any]:
        """Handle incoming Meta WhatsApp Business webhook."""
        try:
            # Meta sends messages in a different format
            entry = request_data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])

            if not messages:
                return {"success": False, "error": "No messages in webhook"}

            message = messages[0]
            from_number = message.get("from")
            text = message.get("text", {}).get("body", "")

            if not text:
                return {"success": False, "error": "No message body"}

            return self.process_inbound_message(from_number, text)

        except Exception as e:
            logger.error(f"Meta webhook handling failed: {e}")
            return {"success": False, "error": str(e)}


def handle_payment_confirmation(phone: str, payment_details: dict) -> Optional[str]:
    """Handle payment confirmation webhook - triggers build pipeline."""
    try:
        from lib.build_trigger import trigger_site_build

        order_id = trigger_site_build({
            "phone": phone,
            "package": payment_details.get("package", "professional"),
            "email": payment_details.get("email"),
            "source": "whatsapp_payment",
            "payment_id": payment_details.get("payment_id"),
        })

        return order_id

    except Exception as e:
        logger.error(f"Failed to trigger build from payment: {e}")
        return None


if __name__ == "__main__":
    # Test the client
    logging.basicConfig(level=logging.INFO)
    client = WhatsAppClient()

    # Test message classification
    test_messages = [
        "Hi, what do you offer?",
        "How long does it take?",
        "What's the price?",
        "I'm interested in a website",
    ]

    for msg in test_messages:
        intent = client.classify_message(msg)
        response = client.generate_response(intent, "Test User")
        print(f"\nMessage: {msg}")
        print(f"Intent: {intent}")
        print(f"Response: {response}")

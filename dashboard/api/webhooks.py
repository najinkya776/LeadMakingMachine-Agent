"""Webhook handlers for PayPal, WhatsApp, and other integrations."""

import logging
from typing import Dict, Any
import hmac
import hashlib
import base64

from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.payment import PAYPAL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class PayPalWebhookEvent(BaseModel):
    """PayPal webhook event data."""
    event_type: str
    resource: Dict[str, Any]


def verify_paypal_signature(
    headers: Dict[str, str],
    body: bytes,
) -> bool:
    """
    Verify PayPal webhook signature.

    PayPal sends these headers:
    - PAYPAL-TRANSMISSION-ID
    - PAYPAL-TRANSMISSION-TIME
    - PAYPAL-CERT-URL
    - PAYPAL-AUTH-ALGO
    - PAYPAL-TRANSMISSION-SIG
    - PAYPAL-TRANSMISSION-MAC (for older webhooks)
    """
    # For sandbox/testing, we can skip verification if webhook_id is not set
    if not PAYPAL.get("webhook_id"):
        logger.warning("PayPal webhook_id not configured, skipping signature verification")
        return True

    try:
        transmission_id = headers.get("paypal-transmission-id", "")
        transmission_time = headers.get("paypal-transmission-time", "")
        cert_url = headers.get("paypal-cert-url", "")
        auth_algo = headers.get("paypal-auth-algo", "SHA256withRSA")
        transmission_sig = headers.get("paypal-transmission-sig", "")

        # Build the expected signature string
        # PayPal's signature verification requires their certificate
        # For a full implementation, you would:
        # 1. Fetch the certificate from cert_url
        # 2. Verify the signature using the certificate
        # 3. Validate the certificate chain

        # Simplified verification for demo:
        # In production, use paypalrestsdk or verify with PayPal's API
        webhook_id = PAYPAL["webhook_id"]
        transmission_mac = headers.get("paypal-transmission-mac", "")

        # For now, we'll do basic validation
        # Real implementation should verify against PayPal's API
        expected_keys = {"paypal-transmission-id", "paypal-transmission-time",
                         "paypal-cert-url", "paypal-auth-algo", "paypal-transmission-sig"}

        received_keys = {k.lower().replace("-", "_") for k in headers.keys()
                        if k.lower().startswith("paypal-")}

        return bool(transmission_id and transmission_time and transmission_sig)

    except Exception as e:
        logger.error(f"PayPal signature verification failed: {e}")
        return False


def handle_paypal_payment_completed(resource: Dict[str, Any]) -> Dict[str, Any]:
    """Handle PAYMENT.CAPTURE.COMPLETED event."""
    try:
        # Extract payment details from PayPal webhook resource
        payment_id = resource.get("id", "")
        status = resource.get("status", "")

        # Get payer info
        payer_info = resource.get("payer", {})
        email = payer_info.get("email_address", "")
        payer_id = payer_info.get("payer_id", "")

        # Get amount info
        amount_info = resource.get("amount", {})
        amount = float(amount_info.get("value", 0))
        currency = amount_info.get("currency_code", "USD")

        # Get custom_id (often used to pass order/metadata)
        custom_id = resource.get("custom_id", "")

        # Get supplementary data (contains the order ID in create_time)
        supplementary_data = resource.get("supplementary_data", {})
        related_ids = supplementary_data.get("related_ids", {})
        order_id = related_ids.get("order_id", "")

        # Extract business name from custom fields if available
        purchase_units = resource.get("purchase_units", [])
        business_name = ""
        if purchase_units:
            business_name = purchase_units[0].get("shipping", {}).get("name", {}).get("full_name", "")

        # Create order in database
        from lib.build_trigger import create_order_from_payment

        order_data = {
            "source": "paypal",
            "customer_email": email,
            "customer_phone": None,
            "business_name": business_name or custom_id,
            "amount": amount,
            "currency": currency,
            "payment_id": payment_id,
            "status": status,
        }

        # Add package based on amount
        if amount >= 499:
            order_data["package"] = "premium"
        elif amount >= 249:
            order_data["package"] = "professional"
        elif amount >= 99:
            order_data["package"] = "starter"
        else:
            order_data["package"] = "professional"

        # Also try to extract from custom_id
        if custom_id and custom_id.startswith("package:"):
            order_data["package"] = custom_id.split(":")[1]

        order_id = create_order_from_payment(order_data)

        logger.info(f"Created order {order_id} from PayPal payment {payment_id}")

        return {
            "success": True,
            "order_id": order_id,
            "payment_id": payment_id,
            "status": status,
        }

    except Exception as e:
        logger.error(f"Failed to handle PayPal payment: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def handle_paypal_payment_denied(resource: Dict[str, Any]) -> Dict[str, Any]:
    """Handle PAYMENT.CAPTURE.DENIED event."""
    try:
        payment_id = resource.get("id", "")
        logger.warning(f"PayPal payment denied: {payment_id}")

        # Update order status if needed
        # For now, just log it

        return {
            "success": True,
            "payment_id": payment_id,
            "status": "denied",
        }

    except Exception as e:
        logger.error(f"Failed to handle PayPal payment denied: {e}")
        return {"success": False, "error": str(e)}


@router.post("/paypal")
async def paypal_webhook(request: Request):
    """
    PayPal IPN/webhook receiver.

    Handles:
    - PAYMENT.CAPTURE.COMPLETED: Triggers site build
    - PAYMENT.CAPTURE.DENIED: Logs denial
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Get headers (lowercase for consistency)
        headers = {k.lower(): v for k, v in request.headers.items()}

        # Verify signature
        # For now, we'll accept the webhook if verification passes
        # or if we're in sandbox mode without webhook_id
        if not verify_paypal_signature(headers, body):
            logger.warning("PayPal signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse JSON body
        import json
        data = json.loads(body)

        event_type = data.get("event_type", "")
        resource = data.get("resource", {})

        logger.info(f"PayPal webhook received: {event_type}")

        # Handle different event types
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            result = handle_paypal_payment_completed(resource)
            return result

        elif event_type == "PAYMENT.CAPTURE.DENIED":
            result = handle_paypal_payment_denied(resource)
            return result

        elif event_type == "CHECKOUT.ORDER.APPROVED":
            # Handle PayPal Checkout orders
            logger.info(f"PayPal checkout order approved: {resource.get('id')}")
            return {"success": True, "status": "order_approved"}

        else:
            logger.info(f"Unhandled PayPal event type: {event_type}")
            return {"success": True, "status": "ignored"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PayPal webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/whatsapp/twilio")
async def whatsapp_twilio_webhook(request: Request):
    """
    Twilio WhatsApp webhook receiver.

    Twilio sends form data with:
    - From: sender's WhatsApp number
    - Body: message text
    """
    try:
        form_data = await request.form()

        from_number = form_data.get("From", "").replace("whatsapp:", "")
        message = form_data.get("Body", "").strip()
        num_media = int(form_data.get("NumMedia", 0))

        if not message:
            return {"success": True, "message": "No message body"}

        logger.info(f"WhatsApp message from {from_number}: {message[:100]}")

        # Process the message
        from lib.whatsapp_client import WhatsAppClient
        client = WhatsAppClient()

        result = client.handle_twilio_webhook({
            "From": form_data.get("From"),
            "Body": message,
            "NumMedia": num_media,
        })

        return result

    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/whatsapp/meta")
async def whatsapp_meta_webhook(request: Request):
    """
    Meta WhatsApp Business webhook receiver.

    Handles webhook verification and incoming messages.
    """
    try:
        body = await request.json()

        # Handle webhook verification
        if body.get("object") == "whatsapp_business":
            entry = body.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]

            # Webhook verification request
            if changes.get("value", {}).get("messages") is None:
                # This is a verification request
                mode = request.query_params.get("hub.mode")
                token = request.query_params.get("hub.verify_token")
                challenge = request.query_params.get("hub.challenge")

                from lib.whatsapp_client import WhatsAppClient
                client = WhatsAppClient()

                if mode == "subscribe" and client.verify_webhook(mode, token, challenge):
                    from fastapi.responses import PlainTextResponse
                    return PlainTextResponse(content=challenge)

            # Process incoming message
            from lib.whatsapp_client import WhatsAppClient
            client = WhatsAppClient()

            result = client.handle_meta_webhook(body)
            return result

        return {"success": True, "status": "ignored"}

    except Exception as e:
        logger.error(f"Meta WhatsApp webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/whatsapp/meta")
async def whatsapp_meta_verify(
    hub_mode: str = None,
    hub_verify_token: str = None,
    hub_challenge: str = None,
):
    """
    Meta WhatsApp webhook verification endpoint.

    Meta sends a GET request to verify the webhook.
    """
    from lib.whatsapp_client import WhatsAppClient
    client = WhatsAppClient()

    if hub_mode == "subscribe" and client.verify_webhook(hub_mode, hub_verify_token, hub_challenge):
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=hub_challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/payment/stripe")
async def stripe_webhook(request: Request):
    """
    Stripe webhook receiver (optional alternative to PayPal).

    Handle:
    - payment_intent.succeeded: Triggers site build
    """
    try:
        import json
        import stripe

        body = await request.body()
        sig = request.headers.get("stripe-signature", "")

        # In production, verify the webhook signature
        # stripe.api_key = STRIPE_SECRET_KEY
        # event = stripe.Webhook.construct_event(body, sig, webhook_secret)

        data = json.loads(body)
        event_type = data.get("type", "")

        logger.info(f"Stripe webhook received: {event_type}")

        if event_type == "payment_intent.succeeded":
            payment_intent = data.get("data", {}).get("object", {})

            from lib.build_trigger import create_order_from_payment

            order_data = {
                "source": "stripe",
                "customer_email": payment_intent.get("receipt_email"),
                "customer_phone": None,
                "amount": payment_intent.get("amount", 0) / 100,  # Stripe uses cents
                "currency": payment_intent.get("currency", "usd").upper(),
                "payment_id": payment_intent.get("id"),
                "status": "COMPLETED",
            }

            order_id = create_order_from_payment(order_data)

            return {"success": True, "order_id": order_id}

        return {"success": True, "status": "ignored"}

    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return {"success": False, "error": str(e)}

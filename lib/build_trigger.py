"""Build trigger module - bridges orders to the SiteBuilder API."""

import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)

# SiteBuilder API endpoint
SITEBUILDER_URL = "http://localhost:3001/api/build"


def trigger_site_build(order: Dict[str, Any]) -> Optional[str]:
    """
    Trigger a site build via the SiteBuilder API.

    Args:
        order: Order details containing:
            - email: Customer email
            - phone: Customer phone
            - package: Selected package (starter, professional, premium)
            - business_name: Customer business name
            - source: Source of the order (email, whatsapp, etc.)
            - payment_id: Payment reference

    Returns:
        build_id: The ID of the initiated build, or None on failure
    """
    try:
        payload = {
            "email": order.get("email"),
            "phone": order.get("phone"),
            "package": order.get("package", "professional"),
            "business_name": order.get("business_name", order.get("name", "New Customer")),
            "source": order.get("source", "direct"),
            "payment_id": order.get("payment_id"),
            "order_id": order.get("order_id"),
            "requirements": order.get("requirements", {}),
        }

        with httpx.Client(timeout=30) as client:
            response = client.post(SITEBUILDER_URL, json=payload)

        if response.status_code == 200:
            result = response.json()
            build_id = result.get("build_id") or result.get("id")
            logger.info(f"Triggered SiteBuilder build: {build_id}")
            return build_id
        else:
            logger.error(f"SiteBuilder API error: {response.status_code} - {response.text}")
            return None

    except httpx.ConnectError:
        logger.error(f"Cannot connect to SiteBuilder at {SITEBUILDER_URL}. Is it running?")
        return None
    except Exception as e:
        logger.error(f"Failed to trigger site build: {e}")
        return None


def check_build_status(build_id: str) -> Optional[Dict[str, Any]]:
    """
    Check the status of a build via SiteBuilder API.

    Args:
        build_id: The ID of the build to check

    Returns:
        Build status data or None on failure
    """
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(f"{SITEBUILDER_URL}/{build_id}")

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Build status check failed: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Failed to check build status: {e}")
        return None


def trigger_proposal_generation(lead_id: str, email_data: Dict[str, Any]) -> Optional[str]:
    """
    Trigger proposal generation for an inbound lead.

    Args:
        lead_id: The inbound lead ID
        email_data: Email data with subject and body

    Returns:
        Proposal generation task ID or None on failure
    """
    try:
        # Import here to avoid circular imports
        import os
        import sys
        from pathlib import Path

        # Add project root to path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))

        # For now, log it - full implementation would trigger the crew
        logger.info(f"Proposal generation triggered for lead {lead_id}")
        logger.info(f"Email subject: {email_data.get('subject', 'N/A')}")
        logger.info(f"Email body preview: {email_data.get('body', '')[:200]}...")

        # TODO: Wire up to the actual proposal generation pipeline
        # This would typically:
        # 1. Parse the email for business requirements
        # 2. Run the scraper to gather business info
        # 3. Run auditor if website exists
        # 4. Generate custom proposal PDF
        # 5. Email the proposal to the customer

        # For now, return a placeholder task ID
        return f"proposal_{lead_id}"

    except Exception as e:
        logger.error(f"Failed to trigger proposal generation: {e}")
        return None


def create_order_from_payment(payment_data: Dict[str, Any]) -> Optional[str]:
    """
    Create an order record from payment webhook data.

    Args:
        payment_data: Payment webhook data containing:
            - order_id or custom_id: Order identifier
            - customer_email: Customer email
            - customer_phone: Customer phone
            - amount: Payment amount
            - status: Payment status

    Returns:
        Order ID if successful
    """
    try:
        import psycopg2
        from config.database import DB_CONFIG
        import uuid
        from datetime import datetime

        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Create orders table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id VARCHAR(36) PRIMARY KEY,
                source VARCHAR(50),
                email VARCHAR(255),
                phone VARCHAR(50),
                business_name VARCHAR(255),
                package VARCHAR(50),
                amount DECIMAL(10, 2),
                currency VARCHAR(10) DEFAULT 'USD',
                status VARCHAR(50) DEFAULT 'pending',
                payment_id VARCHAR(255),
                payment_status VARCHAR(50),
                build_id VARCHAR(36),
                lead_id VARCHAR(36),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivered_at TIMESTAMP,
                notes TEXT
            )
        """)

        order_id = str(uuid.uuid4())
        package = determine_package_from_amount(payment_data.get("amount", 0))

        cursor.execute("""
            INSERT INTO orders (id, source, email, phone, package, amount, payment_id, payment_status, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            order_id,
            payment_data.get("source", "paypal"),
            payment_data.get("customer_email"),
            payment_data.get("customer_phone"),
            package,
            payment_data.get("amount"),
            payment_data.get("payment_id"),
            payment_data.get("status"),
            "paid" if payment_data.get("status") == "COMPLETED" else "pending",
        ))

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Created order {order_id} from payment")

        # Trigger build
        build_id = trigger_site_build({
            "email": payment_data.get("customer_email"),
            "phone": payment_data.get("customer_phone"),
            "package": package,
            "order_id": order_id,
            "payment_id": payment_data.get("payment_id"),
            "source": payment_data.get("source", "paypal"),
        })

        if build_id:
            # Update order with build_id
            try:
                conn = psycopg2.connect(**DB_CONFIG)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE orders SET build_id = %s, updated_at = %s WHERE id = %s
                """, (build_id, datetime.utcnow(), order_id))
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to update order with build_id: {e}")

        return order_id

    except Exception as e:
        logger.error(f"Failed to create order from payment: {e}")
        return None


def determine_package_from_amount(amount: float) -> str:
    """Determine package from payment amount."""
    if amount >= 499:
        return "premium"
    elif amount >= 249:
        return "professional"
    elif amount >= 99:
        return "starter"
    else:
        return "professional"  # Default


def get_order_status(order_id: str) -> Optional[Dict[str, Any]]:
    """Get order status including build progress."""
    try:
        import psycopg2
        from config.database import DB_CONFIG
        from datetime import datetime

        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, source, email, phone, business_name, package, amount,
                   status, payment_id, build_id, created_at, delivered_at
            FROM orders WHERE id = %s
        """, (order_id,))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return None

        order = {
            "id": row[0],
            "source": row[1],
            "email": row[2],
            "phone": row[3],
            "business_name": row[4],
            "package": row[5],
            "amount": float(row[6]) if row[6] else None,
            "status": row[7],
            "payment_id": row[8],
            "build_id": row[9],
            "created_at": row[10].isoformat() if row[10] else None,
            "delivered_at": row[11].isoformat() if row[11] else None,
        }

        # If there's a build_id, get build status
        if order.get("build_id"):
            build_status = check_build_status(order["build_id"])
            if build_status:
                order["build_status"] = build_status.get("status", "unknown")
                order["build_progress"] = build_status.get("progress", 0)

        return order

    except Exception as e:
        logger.error(f"Failed to get order status: {e}")
        return None


if __name__ == "__main__":
    # Test trigger
    logging.basicConfig(level=logging.INFO)

    result = trigger_site_build({
        "email": "test@example.com",
        "phone": "+1234567890",
        "package": "professional",
        "business_name": "Test Business",
        "source": "test",
    })

    print(f"Build triggered: {result}")

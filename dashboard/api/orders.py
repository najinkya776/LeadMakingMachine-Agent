"""Orders API endpoints for tracking build orders."""

from datetime import datetime
from typing import Optional, List
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    PAID = "paid"
    BUILDING = "building"
    REVIEW = "review"
    DELIVERED = "delivered"
    UPSOLD = "upsold"
    CANCELLED = "cancelled"


class OrderCreate(BaseModel):
    """Schema for creating an order."""
    source: str = "web"
    email: Optional[str] = None
    phone: Optional[str] = None
    business_name: Optional[str] = None
    package: str = "professional"
    amount: Optional[float] = None
    currency: str = "USD"
    payment_id: Optional[str] = None
    lead_id: Optional[str] = None
    notes: Optional[str] = None


class OrderUpdate(BaseModel):
    """Schema for updating an order."""
    status: Optional[str] = None
    build_id: Optional[str] = None
    business_name: Optional[str] = None
    notes: Optional[str] = None
    delivered_at: Optional[datetime] = None


class OrderResponse(BaseModel):
    """Response schema for order."""
    id: str
    source: str
    email: Optional[str] = None
    phone: Optional[str] = None
    business_name: Optional[str] = None
    package: str
    amount: Optional[float] = None
    currency: str
    status: str
    payment_id: Optional[str] = None
    payment_status: Optional[str] = None
    build_id: Optional[str] = None
    lead_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    delivered_at: Optional[datetime] = None
    notes: Optional[str] = None


class OrderListResponse(BaseModel):
    """Paginated list of orders."""
    orders: List[OrderResponse]
    total: int
    limit: int
    offset: int


class OrderStatsResponse(BaseModel):
    """Order statistics."""
    total: int
    by_status: dict[str, int]
    total_revenue: float
    currency: str


def get_orders_from_db(
    status: Optional[str] = None,
    package: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Fetch orders from database."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        # Build query
        base_query = "SELECT * FROM orders WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM orders WHERE 1=1"
        params = []
        param_idx = 1

        if status:
            base_query += f" AND status = ${param_idx}"
            count_query += f" AND status = ${param_idx}"
            params.append(status)
            param_idx += 1

        if package:
            base_query += f" AND package = ${param_idx}"
            count_query += f" AND package = ${param_idx}"
            params.append(package)
            param_idx += 1

        # Get total count
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Add pagination and ordering
        base_query += f" ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])

        cursor.execute(base_query, params)
        rows = cursor.fetchall()

        orders = []
        for row in rows:
            orders.append({
                "id": row[0],
                "source": row[1],
                "email": row[2],
                "phone": row[3],
                "business_name": row[4],
                "package": row[5],
                "amount": float(row[6]) if row[6] else None,
                "currency": row[7],
                "status": row[8],
                "payment_id": row[9],
                "payment_status": row[10],
                "build_id": row[11],
                "lead_id": row[12],
                "created_at": row[13],
                "updated_at": row[14],
                "delivered_at": row[15],
                "notes": row[16],
            })

        cursor.close()
        conn.close()
        return orders, total

    except Exception as e:
        return [], 0


def ensure_orders_table():
    """Ensure orders table exists."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

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

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        pass  # Table creation is best-effort


@router.post("", response_model=OrderResponse)
def create_order(order: OrderCreate):
    """Create a new build order."""
    ensure_orders_table()

    try:
        import psycopg2
        from config.database import DB_CONFIG
        import uuid

        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        order_id = str(uuid.uuid4())
        now = datetime.utcnow()

        cursor.execute("""
            INSERT INTO orders
            (id, source, email, phone, business_name, package, amount, currency, status, payment_id, lead_id, notes, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            order_id,
            order.source,
            order.email,
            order.phone,
            order.business_name,
            order.package,
            order.amount,
            order.currency,
            "paid" if order.payment_id else "pending",
            order.payment_id,
            order.lead_id,
            order.notes,
            now,
            now,
        ))

        conn.commit()
        cursor.close()
        conn.close()

        # Trigger build if payment received
        if order.payment_id:
            try:
                from lib.build_trigger import trigger_site_build
                trigger_site_build({
                    "email": order.email,
                    "phone": order.phone,
                    "package": order.package,
                    "order_id": order_id,
                    "payment_id": order.payment_id,
                    "source": order.source,
                })
            except Exception:
                pass  # Build trigger is best-effort

        return OrderResponse(
            id=order_id,
            source=order.source,
            email=order.email,
            phone=order.phone,
            business_name=order.business_name,
            package=order.package,
            amount=order.amount,
            currency=order.currency,
            status="paid" if order.payment_id else "pending",
            payment_id=order.payment_id,
            payment_status="completed" if order.payment_id else None,
            build_id=None,
            lead_id=order.lead_id,
            created_at=now,
            updated_at=now,
            delivered_at=None,
            notes=order.notes,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("", response_model=OrderListResponse)
def list_orders(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    package: Optional[str] = Query(default=None, description="Filter by package"),
):
    """List all orders with pagination and filters."""
    orders, total = get_orders_from_db(
        status=status,
        package=package,
        limit=limit,
        offset=offset,
    )

    return OrderListResponse(
        orders=[
            OrderResponse(
                id=order["id"],
                source=order["source"],
                email=order["email"],
                phone=order["phone"],
                business_name=order["business_name"],
                package=order["package"],
                amount=order["amount"],
                currency=order["currency"],
                status=order["status"],
                payment_id=order["payment_id"],
                payment_status=order["payment_status"],
                build_id=order["build_id"],
                lead_id=order["lead_id"],
                created_at=order["created_at"],
                updated_at=order["updated_at"],
                delivered_at=order["delivered_at"],
                notes=order["notes"],
            )
            for order in orders
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=OrderStatsResponse)
def get_order_stats():
    """Get order statistics."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        # Get total
        cursor.execute("SELECT COUNT(*) FROM orders")
        total = cursor.fetchone()[0]

        # Get by status
        cursor.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
        by_status = {row[0]: row[1] for row in cursor.fetchall()}

        # Get total revenue
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status IN ('paid', 'building', 'delivered', 'upsold')")
        total_revenue = float(cursor.fetchone()[0])

        cursor.close()
        conn.close()

        return OrderStatsResponse(
            total=total,
            by_status=by_status,
            total_revenue=total_revenue,
            currency="USD",
        )

    except Exception as e:
        return OrderStatsResponse(
            total=0,
            by_status={},
            total_revenue=0.0,
            currency="USD",
        )


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: str):
    """Get a single order by ID."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, source, email, phone, business_name, package, amount, currency,
                   status, payment_id, payment_status, build_id, lead_id,
                   created_at, updated_at, delivered_at, notes
            FROM orders WHERE id = %s
        """, (order_id,))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Order not found")

        return OrderResponse(
            id=row[0],
            source=row[1],
            email=row[2],
            phone=row[3],
            business_name=row[4],
            package=row[5],
            amount=float(row[6]) if row[6] else None,
            currency=row[7],
            status=row[8],
            payment_id=row[9],
            payment_status=row[10],
            build_id=row[11],
            lead_id=row[12],
            created_at=row[13],
            updated_at=row[14],
            delivered_at=row[15],
            notes=row[16],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.patch("/{order_id}")
def update_order(order_id: str, updates: OrderUpdate):
    """Update an order."""
    try:
        import psycopg2
        from config.database import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Build update query dynamically
        set_clauses = []
        values = []

        if updates.status is not None:
            set_clauses.append("status = %s")
            values.append(updates.status)

        if updates.build_id is not None:
            set_clauses.append("build_id = %s")
            values.append(updates.build_id)

        if updates.business_name is not None:
            set_clauses.append("business_name = %s")
            values.append(updates.business_name)

        if updates.notes is not None:
            set_clauses.append("notes = %s")
            values.append(updates.notes)

        if updates.delivered_at is not None:
            set_clauses.append("delivered_at = %s")
            values.append(updates.delivered_at)

        if not set_clauses:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clauses.append("updated_at = %s")
        values.append(datetime.utcnow())
        values.append(order_id)

        cursor.execute(
            f"UPDATE orders SET {', '.join(set_clauses)} WHERE id = %s",
            values
        )

        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Order not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"success": True, "message": "Order updated"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

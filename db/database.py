"""Lead tracking database for cold email pipeline."""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum


class LeadStatus(Enum):
    """Lead lifecycle stages."""
    NEW = "new"
    SCRAPED = "scraped"
    QUALIFIED = "qualified"
    AUDITED = "audited"
    SCORED = "scored"
    REPORT_GENERATED = "report_generated"
    CONTACTED = "contacted"
    RESPONDED = "responded"
    INTERESTED = "interested"
    NEGOTIATING = "negotiating"
    CONVERTED = "converted"
    TRASHED = "trashed"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"


class LeadSource(Enum):
    """Where the lead came from."""
    GOOGLE_MAPS = "google_maps"
    REFERRAL = "referral"
    LANDING_PAGE = "landing_page"
    COLD_OUTREACH = "cold_outreach"
    FREELANCE_MARKETPLACE = "freelance_marketplace"
    MANUAL = "manual"


@dataclass
class Lead:
    """Lead data model."""
    id: Optional[int] = None
    business_name: str = ""
    owner_name: str = ""
    industry: str = ""
    location: str = ""
    email: str = ""
    phone: str = ""
    website: str = ""
    google_maps_url: str = ""
    rating: float = 0.0
    reviews_count: int = 0
    status: str = LeadStatus.NEW.value
    source: str = LeadSource.COLD_OUTREACH.value
    score: int = 0
    findings: str = ""  # JSON string of audit findings
    notes: str = ""
    contact_attempts: int = 0
    last_contacted: Optional[str] = None
    next_followup: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    campaign_id: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        if data.get('findings') and isinstance(data['findings'], str):
            try:
                data['findings_dict'] = json.loads(data['findings'])
            except:
                data['findings_dict'] = {}
        return data


@dataclass
class EmailRecord:
    """Record of sent emails."""
    id: Optional[int] = None
    lead_id: int = 0
    email_type: str = "initial"  # initial, followup_1, followup_2, etc.
    subject: str = ""
    body: str = ""
    pdf_report_path: str = ""
    sent_at: Optional[str] = None
    delivered: bool = False
    opened: bool = False
    clicked: bool = False
    replied: bool = False
    bounce_reason: str = ""


@dataclass
class Response:
    """Record of responses from leads."""
    id: Optional[int] = None
    lead_id: int = 0
    channel: str = "email"  # email, whatsapp, phone
    response_text: str = ""
    response_type: str = "positive"  # positive, negative, neutral, interested, not_interested, spam
    sentiment: str = "neutral"  # positive, negative, neutral
    interested_in: str = ""  # website_design, redesign, seo, etc.
    budget: str = ""
    timeline: str = ""
    notes: str = ""
    responded_at: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class Conversation:
    """Track conversation history with a lead."""
    id: Optional[int] = None
    lead_id: int = 0
    direction: str = "outbound"  # outbound, inbound
    channel: str = "email"  # email, whatsapp, phone
    message: str = ""
    created_at: Optional[str] = None


@dataclass
class Order:
    """Orders from converted leads."""
    id: Optional[int] = None
    lead_id: int = 0
    package: str = ""  # starter, professional, enterprise
    amount: float = 0.0
    currency: str = "INR"
    payment_status: str = "pending"  # pending, paid, failed, refunded
    payment_id: str = ""
    order_date: Optional[str] = None
    delivery_date: Optional[str] = None
    website_url: str = ""
    notes: str = ""


class LeadDatabase:
    """Main database class for lead tracking."""

    def __init__(self, db_path: str = None):
        """Initialize database connection."""
        if db_path is None:
            db_path = Path(__file__).parent / "leads.db"
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Leads table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                owner_name TEXT DEFAULT '',
                industry TEXT DEFAULT '',
                location TEXT DEFAULT '',
                email TEXT,
                phone TEXT DEFAULT '',
                website TEXT DEFAULT '',
                google_maps_url TEXT DEFAULT '',
                rating REAL DEFAULT 0.0,
                reviews_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'new',
                source TEXT DEFAULT 'cold_outreach',
                score INTEGER DEFAULT 0,
                findings TEXT DEFAULT '{}',
                notes TEXT DEFAULT '',
                contact_attempts INTEGER DEFAULT 0,
                last_contacted TEXT,
                next_followup TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(business_name, email)
            )
        """)

        # Email records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                email_type TEXT DEFAULT 'initial',
                subject TEXT DEFAULT '',
                body TEXT DEFAULT '',
                pdf_report_path TEXT DEFAULT '',
                sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                delivered INTEGER DEFAULT 0,
                opened INTEGER DEFAULT 0,
                clicked INTEGER DEFAULT 0,
                replied INTEGER DEFAULT 0,
                bounce_reason TEXT DEFAULT '',
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            )
        """)

        # Responses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                channel TEXT DEFAULT 'email',
                response_text TEXT DEFAULT '',
                response_type TEXT DEFAULT 'neutral',
                sentiment TEXT DEFAULT 'neutral',
                interested_in TEXT DEFAULT '',
                budget TEXT DEFAULT '',
                timeline TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                responded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            )
        """)

        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                direction TEXT DEFAULT 'outbound',
                channel TEXT DEFAULT 'email',
                message TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            )
        """)

        # Orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                package TEXT DEFAULT '',
                amount REAL DEFAULT 0.0,
                currency TEXT DEFAULT 'INR',
                payment_status TEXT DEFAULT 'pending',
                payment_id TEXT DEFAULT '',
                order_date TEXT DEFAULT CURRENT_TIMESTAMP,
                delivery_date TEXT,
                website_url TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            )
        """)

        # Campaign tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_date TEXT DEFAULT CURRENT_TIMESTAMP,
                end_date TEXT,
                target_count INTEGER DEFAULT 0,
                sent_count INTEGER DEFAULT 0,
                responded_count INTEGER DEFAULT 0,
                converted_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_industry ON leads(industry)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_location ON leads(location)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_responses_lead ON responses(lead_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_lead ON email_records(lead_id)")

        conn.commit()
        conn.close()

    # ==================== LEAD OPERATIONS ====================

    def add_lead(self, lead: Lead) -> int:
        """Add a new lead."""
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT OR IGNORE INTO leads (
                business_name, owner_name, industry, location, email, phone,
                website, google_maps_url, rating, reviews_count, status,
                source, score, findings, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead.business_name, lead.owner_name, lead.industry, lead.location,
            lead.email, lead.phone, lead.website, lead.google_maps_url,
            lead.rating, lead.reviews_count, lead.status, lead.source,
            lead.score, lead.findings, lead.notes, now, now
        ))

        lead_id = cursor.lastrowid
        if lead_id == 0:
            # Already exists, get existing ID
            cursor.execute("SELECT id FROM leads WHERE business_name = ? AND email = ?",
                          (lead.business_name, lead.email))
            row = cursor.fetchone()
            lead_id = row[0] if row else 0

        conn.commit()
        conn.close()
        return lead_id

    def add_leads_bulk(self, leads: List[Lead]) -> int:
        """Add multiple leads efficiently."""
        count = 0
        for lead in leads:
            if self.add_lead(lead):
                count += 1
        return count

    def get_lead(self, lead_id: int) -> Optional[Lead]:
        """Get a lead by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return Lead(**dict(row))
        return None

    def get_lead_by_email(self, email: str) -> Optional[Lead]:
        """Get a lead by email."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM leads WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return Lead(**dict(row))
        return None

    def update_lead(self, lead_id: int, **kwargs) -> bool:
        """Update lead fields."""
        if not kwargs:
            return False

        conn = self._get_connection()
        cursor = conn.cursor()

        kwargs['updated_at'] = datetime.now().isoformat()
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [lead_id]

        cursor.execute(f"UPDATE leads SET {set_clause} WHERE id = ?", values)
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected > 0

    def update_lead_status(self, lead_id: int, status: str) -> bool:
        """Update lead status."""
        return self.update_lead(lead_id, status=status)

    def trash_lead(self, lead_id: int, reason: str = "") -> bool:
        """Move lead to trash."""
        return self.update_lead(lead_id, status=LeadStatus.TRASHED.value, notes=reason)

    def get_leads(
        self,
        status: str = None,
        source: str = None,
        industry: str = None,
        location: str = None,
        min_score: int = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Lead]:
        """Get leads with filters."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM leads WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if source:
            query += " AND source = ?"
            params.append(source)
        if industry:
            query += " AND industry = ?"
            params.append(industry)
        if location:
            query += " AND location LIKE ?"
            params.append(f"%{location}%")
        if min_score is not None:
            query += " AND score >= ?"
            params.append(min_score)

        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [Lead(**dict(row)) for row in rows]

    def get_leads_needing_followup(self) -> List[Lead]:
        """Get leads that need follow-up."""
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        cursor.execute("""
            SELECT * FROM leads
            WHERE status IN ('contacted', 'responded', 'interested')
            AND (next_followup IS NULL OR next_followup <= ?)
            ORDER BY next_followup ASC
            LIMIT 50
        """, (now,))

        rows = cursor.fetchall()
        conn.close()
        return [Lead(**dict(row)) for row in rows]

    def get_untouched_leads(self, limit: int = 50) -> List[Lead]:
        """Get leads that haven't been contacted yet."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM leads
            WHERE status NOT IN ('contacted', 'responded', 'interested', 'converted', 'trashed')
            AND contact_attempts = 0
            ORDER BY score DESC, rating DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()
        return [Lead(**dict(row)) for row in rows]

    # ==================== EMAIL OPERATIONS ====================

    def record_email(self, record: EmailRecord) -> int:
        """Record a sent email."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO email_records (
                lead_id, email_type, subject, body, pdf_report_path,
                sent_at, delivered, opened, clicked, replied, bounce_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.lead_id, record.email_type, record.subject, record.body,
            record.pdf_report_path, record.sent_at or datetime.now().isoformat(),
            int(record.delivered), int(record.opened), int(record.clicked),
            int(record.replied), record.bounce_reason
        ))

        email_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return email_id

    def get_emails_for_lead(self, lead_id: int) -> List[EmailRecord]:
        """Get all emails for a lead."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM email_records WHERE lead_id = ? ORDER BY sent_at DESC", (lead_id,))
        rows = cursor.fetchall()
        conn.close()

        return [EmailRecord(**dict(row)) for row in rows]

    def mark_email_replied(self, email_id: int) -> bool:
        """Mark email as replied to."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("UPDATE email_records SET replied = 1 WHERE id = ?", (email_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    # ==================== RESPONSE OPERATIONS ====================

    def add_response(self, response: Response) -> int:
        """Add a response from a lead."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO responses (
                lead_id, channel, response_text, response_type,
                sentiment, interested_in, budget, timeline, notes,
                responded_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response.lead_id, response.channel, response.response_text,
            response.response_type, response.sentiment, response.interested_in,
            response.budget, response.timeline, response.notes,
            response.responded_at or datetime.now().isoformat(),
            datetime.now().isoformat()
        ))

        response_id = cursor.lastrowid

        # Update lead status based on response type
        if response.response_type in ['interested', 'positive']:
            self.update_lead_status(response.lead_id, LeadStatus.INTERESTED.value)
        elif response.response_type in ['not_interested', 'negative']:
            self.update_lead_status(response.lead_id, LeadStatus.TRASHED.value)

        conn.commit()
        conn.close()
        return response_id

    def get_responses_for_lead(self, lead_id: int) -> List[Response]:
        """Get all responses for a lead."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM responses WHERE lead_id = ? ORDER BY responded_at DESC", (lead_id,))
        rows = cursor.fetchall()
        conn.close()

        return [Response(**dict(row)) for row in rows]

    # ==================== CONVERSATION OPERATIONS ====================

    def add_conversation(self, conv: Conversation) -> int:
        """Add a conversation entry."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO conversations (lead_id, direction, channel, message, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (conv.lead_id, conv.direction, conv.channel, conv.message,
              conv.created_at or datetime.now().isoformat()))

        conv_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return conv_id

    def get_conversation_history(self, lead_id: int) -> List[Conversation]:
        """Get full conversation history for a lead."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM conversations WHERE lead_id = ? ORDER BY created_at ASC
        """, (lead_id,))

        rows = cursor.fetchall()
        conn.close()
        return [Conversation(**dict(row)) for row in rows]

    # ==================== ORDER OPERATIONS ====================

    def create_order(self, order: Order) -> int:
        """Create a new order."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO orders (
                lead_id, package, amount, currency, payment_status,
                payment_id, order_date, delivery_date, website_url, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order.lead_id, order.package, order.amount, order.currency,
            order.payment_status, order.payment_id, order.order_date or datetime.now().isoformat(),
            order.delivery_date, order.website_url, order.notes
        ))

        order_id = cursor.lastrowid

        # Update lead status to converted
        self.update_lead_status(order.lead_id, LeadStatus.CONVERTED.value)

        conn.commit()
        conn.close()
        return order_id

    def get_orders(self, lead_id: int = None, status: str = None) -> List[Order]:
        """Get orders with optional filters."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM orders WHERE 1=1"
        params = []

        if lead_id:
            query += " AND lead_id = ?"
            params.append(lead_id)
        if status:
            query += " AND payment_status = ?"
            params.append(status)

        query += " ORDER BY order_date DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [Order(**dict(row)) for row in rows]

    # ==================== STATISTICS ====================

    def get_stats(self) -> dict:
        """Get dashboard statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        # Total leads
        cursor.execute("SELECT COUNT(*) FROM leads")
        stats['total_leads'] = cursor.fetchone()[0]

        # Leads by status
        cursor.execute("SELECT status, COUNT(*) FROM leads GROUP BY status")
        stats['by_status'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Leads by industry
        cursor.execute("SELECT industry, COUNT(*) FROM leads WHERE industry != '' GROUP BY industry ORDER BY COUNT(*) DESC LIMIT 10")
        stats['by_industry'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Average score
        cursor.execute("SELECT AVG(score) FROM leads WHERE score > 0")
        stats['avg_score'] = cursor.fetchone()[0] or 0

        # Emails sent
        cursor.execute("SELECT COUNT(*) FROM email_records")
        stats['emails_sent'] = cursor.fetchone()[0]

        # Replies received
        cursor.execute("SELECT COUNT(*) FROM email_records WHERE replied = 1")
        stats['replies'] = cursor.fetchone()[0]
        stats['reply_rate'] = (stats['replies'] / stats['emails_sent'] * 100) if stats['emails_sent'] > 0 else 0

        # Responses by type
        cursor.execute("SELECT response_type, COUNT(*) FROM responses GROUP BY response_type")
        stats['responses_by_type'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Interested leads
        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'interested'")
        stats['interested_leads'] = cursor.fetchone()[0]

        # Conversions
        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'converted'")
        stats['conversions'] = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(amount) FROM orders WHERE payment_status = 'paid'")
        stats['revenue'] = cursor.fetchone()[0] or 0
        stats['conversion_rate'] = (stats['conversions'] / stats['total_leads'] * 100) if stats['total_leads'] > 0 else 0

        # Trashed
        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'trashed'")
        stats['trashed'] = cursor.fetchone()[0]

        # Needs follow-up
        cursor.execute("""
            SELECT COUNT(*) FROM leads
            WHERE status IN ('contacted', 'responded', 'interested')
            AND contact_attempts < 3
        """)
        stats['needs_followup'] = cursor.fetchone()[0]

        # Untouched leads
        cursor.execute("SELECT COUNT(*) FROM leads WHERE contact_attempts = 0 AND status NOT IN ('trashed', 'converted')")
        stats['untouched'] = cursor.fetchone()[0]

        conn.close()
        return stats

    def search_leads(self, query: str, limit: int = 50) -> List[Lead]:
        """Search leads by business name, owner, email, or notes."""
        conn = self._get_connection()
        cursor = conn.cursor()

        search = f"%{query}%"
        cursor.execute("""
            SELECT * FROM leads
            WHERE business_name LIKE ?
               OR owner_name LIKE ?
               OR email LIKE ?
               OR notes LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
        """, (search, search, search, search, limit))

        rows = cursor.fetchall()
        conn.close()
        return [Lead(**dict(row)) for row in rows]


# Global database instance
db = LeadDatabase()

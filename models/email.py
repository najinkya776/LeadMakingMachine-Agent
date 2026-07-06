"""
Email Model - Represents a sent or pending email
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Email:
    id: Optional[int] = None
    lead_id: Optional[int] = None
    campaign_id: Optional[int] = None
    subject: str = ""
    body: str = ""
    status: str = "pending"
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None

    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'campaign_id': self.campaign_id,
            'subject': self.subject,
            'body': self.body,
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if isinstance(self.sent_at, datetime) else self.sent_at,
            'delivered_at': self.delivered_at.isoformat() if isinstance(self.delivered_at, datetime) else self.delivered_at,
            'opened_at': self.opened_at.isoformat() if isinstance(self.opened_at, datetime) else self.opened_at,
            'replied_at': self.replied_at.isoformat() if isinstance(self.replied_at, datetime) else self.replied_at,
            'bounced_at': self.bounced_at.isoformat() if isinstance(self.bounced_at, datetime) else self.bounced_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Email':
        return cls(
            id=data.get('id'),
            lead_id=data.get('lead_id'),
            campaign_id=data.get('campaign_id'),
            subject=data.get('subject', ''),
            body=data.get('body', ''),
            status=data.get('status', 'pending'),
        )

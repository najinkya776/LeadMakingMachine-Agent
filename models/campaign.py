"""
Campaign Model - Represents an email campaign
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Campaign:
    id: Optional[int] = None
    name: str = ""
    subject: str = ""
    template: str = ""
    status: str = "draft"
    sent_count: int = 0
    response_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'subject': self.subject,
            'template': self.template,
            'status': self.status,
            'sent_count': self.sent_count,
            'response_count': self.response_count,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Campaign':
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            subject=data.get('subject', ''),
            template=data.get('template', ''),
            status=data.get('status', 'draft'),
            sent_count=data.get('sent_count', 0),
            response_count=data.get('response_count', 0),
        )

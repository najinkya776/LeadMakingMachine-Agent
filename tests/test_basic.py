"""
Tests for LeadMakingMachine
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Test that all modules can be imported"""
    from config.settings import Settings
    from models.lead import Lead
    from models.campaign import Campaign
    from models.email import Email
    from services.scraper import ScraperService
    from services.emailer import EmailService
    from services.responder import ResponseChecker
    from services.dashboard import Dashboard
    from services.followup import FollowUpService

    assert True


def test_lead_model():
    """Test Lead model"""
    from models.lead import Lead

    lead = Lead(
        company="Test Corp",
        email="test@example.com",
        score=75
    )

    assert lead.company == "Test Corp"
    assert lead.email == "test@example.com"
    assert lead.score == 75
    assert lead.status == "new"

    data = lead.to_dict()
    assert data['company'] == "Test Corp"
    assert data['email'] == "test@example.com"


def test_settings_defaults():
    """Test Settings default values"""
    from config.settings import Settings

    settings = Settings()

    # Should have defaults
    assert settings.SMTP_HOST == "smtp.gmail.com"
    assert settings.SMTP_PORT == 587
    assert settings.DAILY_EMAIL_LIMIT == 100
    assert settings.FOLLOWUP_DELAY_DAYS == 3
    assert settings.FOLLOWUP_MAX_ATTEMPTS == 3


def test_email_model():
    """Test Email model"""
    from models.email import Email

    email = Email(
        lead_id=1,
        subject="Test Subject",
        body="Test Body",
        status="pending"
    )

    assert email.lead_id == 1
    assert email.subject == "Test Subject"
    assert email.status == "pending"


def test_campaign_model():
    """Test Campaign model"""
    from models.campaign import Campaign

    campaign = Campaign(
        name="Test Campaign",
        subject="Test Subject",
        status="draft"
    )

    assert campaign.name == "Test Campaign"
    assert campaign.status == "draft"
    assert campaign.sent_count == 0

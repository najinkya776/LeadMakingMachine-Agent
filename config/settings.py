"""Application settings for LeadMakingMachine - Cold Email Lead Generation."""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# API Keys
# =============================================================================

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "__REDACTED__APIFY_TOKEN__")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# =============================================================================
# CONTACT DETAILS (for cold emails - NO PRICING MENTIONED)
# =============================================================================

CONTACT_INFO = {
    "business_name": "__BUSINESS_NAME_REDACTED__",
    "email": "__BUSINESS_EMAIL_REDACTED__",
    "whatsapp": "__BUSINESS_WHATSAPP_REDACTED__",
    "website": "__BUSINESS_WEBSITE_REDACTED__",
    "tagline": "__BUSINESS_TAGLINE_REDACTED__",
}

# =============================================================================
# EMAIL TEMPLATES - COLD OUTREACH (NO PRICING)
# =============================================================================

EMAIL_SUBJECT_TEMPLATES = [
    "Quick look at {business_name}'s online presence",
    "Something about {business_name} worth seeing",
    "Found something interesting about {business_name}",
    "{industry} in {location} - quick question",
]

EMAIL_BODY_TEMPLATE = """
Hi {owner_name},

I was researching {industry} businesses in {location} and came across {business_name}.

I ran a quick analysis of your online presence and found a few things worth sharing:

{findings_list}

I've attached a detailed report with specific suggestions.

The good news - all of this is fixable, and we can help with that.

Interested? Just reply to this email or WhatsApp me ({whatsapp}) - happy to chat about what would work best for {business_name}.

No pressure, no sales pitch. Just a friendly conversation about your options.

{contact_name}
__BUSINESS_NAME_REDACTED__
Email: {email}
WhatsApp: {whatsapp}
"""

# Follow-up email (if no response after 3 days)
FOLLOWUP_TEMPLATE = """
Hi {owner_name or 'there'},

Just following up on my earlier email about {business_name}.

I know you're busy - I just wanted to make sure you saw the report I attached.

{one_line_reminder}

If now isn't a good time, just let me know and I'll leave you alone. But if you're curious about improving your online presence, I'm here.

Reply here or WhatsApp: {whatsapp}

Cheers,
{contact_name}
"""

# =============================================================================
# Ideal Customer Profile (ICP)
# =============================================================================

ICP = {
    "locations": [
        "Pimpri-Chinchwad",
        "Pune",
        "Chinchwad",
        "Akurdi",
        "Nigdi",
        "Bhosari",
        "Moshi",
        "Talegaon",
        "Hinjewadi",
        "Baner",
        "Kothrud",
        "Viman Nagar",
        "Hadapsar",
    ],
    "industries": [
        "restaurant",
        "cafe",
        "clinic",
        "dental clinic",
        "salon",
        "beauty salon",
        "gym",
        "fitness center",
        "shop",
        "retail store",
        "bakery",
        "jewelry store",
        "furniture store",
        "electronics shop",
        "mobile shop",
        "clothes shop",
        "medical store",
        "hotel",
        "guest house",
        "tuition",
        "coaching center",
        "car workshop",
        "bike shop",
        "event hall",
        "photography studio",
        "law firm",
        "ca",
        "advocate",
        "real estate",
        "interior designer",
    ],
    "min_reviews": 3,
    "min_rating": 3.0,
    "exclude_industries": [
        "hospital",
        "large_corporation",
        "bank",
        "insurance",
        "government",
        "school",
        "college",
        "university",
    ],
    "exclude_status": ["closed", "permanently closed"],
}

# =============================================================================
# SERVICES WE OFFER (NOT mentioned in cold email - only discussed after reply)
# =============================================================================

SERVICES = {
    "website_design": "Custom website design",
    "website_building": "Website building from scratch",
    "redesign": "Website redesign & modernization",
    "seo": "SEO optimization",
    "mobile_optimization": "Mobile optimization",
    "speed_optimization": "Speed optimization",
    "landing_pages": "Landing pages",
    "ecommerce": "E-commerce stores",
}

# =============================================================================
# WHAT WE ANALYZE IN AUDIT (findings to highlight)
# =============================================================================

AUDIT_CHECKS = {
    "website_speed": "Website loading speed",
    "mobile_friendly": "Mobile responsiveness",
    "seo_basics": "Basic SEO elements (titles, descriptions)",
    "google_reviews": "Google reviews integration",
    "contact_info": "Contact information visibility",
    "social_links": "Social media links",
    "images": "Image optimization",
    "content_quality": "Content quality and structure",
    "call_to_action": "Call-to-action presence",
    "google_my_business": "Google Business Profile optimization",
}

# =============================================================================
# Scoring Thresholds
# =============================================================================

SCORING = {
    "high": 80,
    "medium": 50,
    "low": 0,
}

# =============================================================================
# Scraping Settings
# =============================================================================

SCRAPING_SETTINGS = {
    "max_leads_per_run": 100,
    "max_per_category": 20,
    "delay_between_requests": 2,
    "retry_attempts": 3,
    "timeout_seconds": 120,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# =============================================================================
# CrewAI Settings
# =============================================================================

CREWAI_SETTINGS = {
    "model": "anthropic/claude-opus-4-7",
    "temperature": 0.7,
    "verbose": True,
    "max_iterations": 10,
    "agents": {
        "scraper": {"max_iterations": 3},
        "social_scraper": {"max_iterations": 3},
        "qualifier": {"max_iterations": 2},
        "auditor": {"max_iterations": 2},
        "scorer": {"max_iterations": 2},
        "pitcher": {"max_iterations": 2},
        "reporter": {"max_iterations": 3},
    }
}

# =============================================================================
# SMTP Settings
# =============================================================================

SMTP_SETTINGS = {
    "host": os.getenv("SMTP_HOST", "smtp.hostinger.com"),
    "port": int(os.getenv("SMTP_PORT", "465")),
    "user": os.getenv("SMTP_USER", "__BUSINESS_EMAIL_REDACTED__"),
    "password": os.getenv("SMTP_PASSWORD", ""),
    "use_ssl": True,
    "from_email": "__BUSINESS_EMAIL_REDACTED__",
    "from_name": "__BUSINESS_NAME_REDACTED__",
}

# =============================================================================
# Lead Types
# =============================================================================

LEAD_TYPES = {
    "no_website": "Business has no website - highest opportunity",
    "has_website": "Business has website - audit for improvements",
    "social_only": "Business only has social media - no website",
    "poor_website": "Business has poor quality website - redesign opportunity",
    "outdated_website": "Business has outdated website - modernization opportunity",
}

# =============================================================================
# EMAIL SETTINGS
# =============================================================================

EMAIL_SETTINGS = {
    "from_name": "__BUSINESS_NAME_REDACTED__",
    "from_email": "__BUSINESS_EMAIL_REDACTED__",
    "reply_to": "__BUSINESS_EMAIL_REDACTED__",
    "max_emails_per_day": 20,
    "batch_size": 5,
    "delay_between_emails_seconds": 30,
    "smtp_host": os.getenv("SMTP_HOST", "smtp.hostinger.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "465")),
    "smtp_user": os.getenv("SMTP_USER", "__BUSINESS_EMAIL_REDACTED__"),
    "smtp_password": os.getenv("SMTP_PASSWORD", ""),
}

# =============================================================================
# FOLLOW-UP SETTINGS
# =============================================================================

FOLLOWUP = {
    "enabled": True,
    "max_followups": 2,
    "days_between_followups": [3, 7],
    "stop_if_replied": True,
}

# =============================================================================
# REPORT SETTINGS
# =============================================================================

REPORT_SETTINGS = {
    "include_screenshots": True,
    "include_scores": True,
    "include_recommendations": True,
    "tone": "helpful",
    "length": "concise",
}

# =============================================================================
# DELIVERY SETTINGS
# =============================================================================

DELIVERY = {
    "attach_pdf_report": True,
    "send_via_email": True,
    "send_via_whatsapp": False,
    "track_opens": True,
    "track_clicks": False,
}
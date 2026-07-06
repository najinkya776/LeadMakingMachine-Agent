"""
Test the cold email template with sample data.
Run: python test_email_template.py
"""

from config.settings import EMAIL_BODY_TEMPLATE, EMAIL_SUBJECT_TEMPLATES, CONTACT_INFO

# Sample lead data
sample_lead = {
    "business_name": "Sharma's Kitchen",
    "owner_name": "Rajesh Sharma",
    "industry": "restaurant",
    "location": "Pimpri-Chinchwad",
    "email": "rajesh@example.com",
    "phone": "+91 98765 43210",
    "website": "sharmaskitchen.com",
    "rating": 4.2,
    "reviews": 127,
    "findings_list": """
• Your website takes 9 seconds to load (industry average is 3s)
• No Google Business Profile linked to your website
• Missing customer testimonials section
• No online ordering option - competitors have this
• Mobile experience could be improved
""",
    "contact_name": "Your Name",  # Update this
}

# Pick a random subject template
import random
subject_template = random.choice(EMAIL_SUBJECT_TEMPLATES)

# Get the industry title-cased once
industry_title = sample_lead["industry"].title()

# Generate the email
subject = subject_template.format(
    business_name=sample_lead["business_name"],
    industry=industry_title,
    location=sample_lead["location"],
)

# Handle missing owner_name
owner_name = sample_lead.get("owner_name") or sample_lead.get("business_name", "there")

body = EMAIL_BODY_TEMPLATE.format(
    owner_name=owner_name,
    business_name=sample_lead["business_name"],
    industry=sample_lead["industry"],
    location=sample_lead["location"],
    findings_list=sample_lead["findings_list"],
    email=CONTACT_INFO["email"],
    whatsapp=CONTACT_INFO["whatsapp"],
    contact_name=sample_lead["contact_name"],
)

print("=" * 60)
print("EMAIL PREVIEW")
print("=" * 60)
print(f"\nTo: {sample_lead['email']}")
print(f"Subject: {subject}")
print(f"\n{'=' * 60}")
import sys
sys.stdout.reconfigure(encoding='utf-8')
print(body)
print("=" * 60)
print("\n✅ Template looks good! Update 'contact_name' before sending.")

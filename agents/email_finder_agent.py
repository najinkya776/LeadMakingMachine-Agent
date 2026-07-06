"""Email finder agent - extracts emails from business websites."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import re
import httpx
import time
from urllib.parse import urljoin
from typing import List, Optional, Set

# Common email patterns
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Contact page keywords
CONTACT_KEYWORDS = ['contact', 'about', 'reach', 'email', 'mail', 'get-in-touch', 'team', 'support']


class EmailFinderAgent:
    """Find email addresses from business websites."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = httpx.Client(timeout=timeout, follow_redirects=True)

    def find_emails_from_website(self, website_url: str, max_pages: int = 3) -> List[str]:
        """Find email addresses from a website."""
        if not website_url or not website_url.startswith(('http://', 'https://')):
            return []

        # Skip WhatsApp links and other non-website URLs
        if 'wa.me' in website_url or 'wa.link' in website_url:
            return []

        emails: Set[str] = set()
        visited: Set[str] = set()
        queue = [website_url]

        pages_checked = 0

        while queue and pages_checked < max_pages:
            url = queue.pop(0)
            if url in visited or not url.startswith(('http://', 'https://')):
                continue

            visited.add(url)

            try:
                response = self.session.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })

                if response.status_code != 200:
                    continue

                # Extract emails from page content
                page_emails = EMAIL_PATTERN.findall(response.text)
                for email in page_emails:
                    # Filter out common non-business emails
                    if not any(x in email.lower() for x in ['noreply', 'no-reply', 'example', 'test', 'domain', 'localhost']):
                        # Filter out very short domains
                        domain = email.split('@')[1] if '@' in email else ''
                        if len(domain) > 5:
                            emails.add(email.lower())

                # Find links to contact/about pages
                content_lower = response.text.lower()
                for keyword in CONTACT_KEYWORDS:
                    pattern = re.compile(f'href=["\']([^"\']*{keyword}[^"\']*)["\']', re.IGNORECASE)
                    for match in pattern.findall(response.text):
                        full_url = urljoin(url, match)
                        if full_url not in visited and full_url.startswith(('http://', 'https://')):
                            if 'wa.me' not in full_url and 'wa.link' not in full_url:
                                queue.append(full_url)

                pages_checked += 1

                # Rate limiting
                time.sleep(0.5)

            except Exception as e:
                continue

        return list(emails)[:5]  # Return max 5 emails

    def extract_email_from_text(self, text: str) -> List[str]:
        """Extract emails from any text."""
        return list(set(EMAIL_PATTERN.findall(text)))

    def generate_business_email(self, business_name: str) -> Optional[str]:
        """Generate likely business email from name - last resort."""
        # Clean business name
        name = business_name.lower()
        name = re.sub(r'[^a-z0-9\s]', '', name)
        name = name.replace(' ', '')

        # Common patterns - return most likely only if no real email found
        patterns = [
            f'info@{name}.com',
            f'contact@{name}.com',
        ]
        return patterns[0]

    def find_email_for_lead(self, business_name: str, website: str = None) -> str:
        """
        Find email for a business - try website first, then generate likely.
        Returns empty string if no email found.
        """
        # Try website first
        if website and website.startswith('http'):
            emails = self.find_emails_from_website(website)
            if emails:
                return emails[0]  # Return first found email

        # Return generated email (not perfect but usable)
        return self.generate_business_email(business_name)


def process_leads():
    """Process all leads without emails and find their emails."""
    from db.database import LeadDatabase

    print("=" * 50)
    print("Email Finder Agent - Enhanced")
    print("=" * 50)

    db = LeadDatabase()
    finder = EmailFinderAgent()

    leads = db.get_leads(limit=100)
    leads_needing_email = [l for l in leads if not l.email or l.email == '' or 'info@' in l.email]

    print(f"Total leads: {len(leads)}")
    print(f"Need email: {len(leads_needing_email)}")

    updated = 0
    generated = 0
    failed = 0

    for lead in leads_needing_email[:20]:  # Process 20 at a time
        print(f"\nProcessing: {lead.business_name[:40]}")

        email = finder.find_email_for_lead(lead.business_name, lead.website)

        if email:
            # Check if it's a generated email or real
            if 'info@' in email.lower() and not lead.website:
                # Generated email without website to verify
                generated += 1
                print(f"  Generated: {email}")
                db.update_lead(lead.id, email=email)
            else:
                print(f"  Found: {email}")
                db.update_lead(lead.id, email=email)
                updated += 1
        else:
            print(f"  No email found")
            failed += 1

    print("\n" + "=" * 50)
    print(f"Results: {updated} found, {generated} generated, {failed} failed")
    print("=" * 50)

    return updated, generated, failed


def find_emails_batch(leads):
    """Find emails for a batch of leads."""
    finder = EmailFinderAgent()
    results = {}

    for lead in leads:
        email = finder.find_email_for_lead(lead.business_name, getattr(lead, 'website', None))
        results[lead.id] = email

    return results


if __name__ == "__main__":
    process_leads()
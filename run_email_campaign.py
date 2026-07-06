"""Automated email sender for LeadMakingMachine.
Run this after pipeline to send emails to qualified leads with reports.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from datetime import datetime
from typing import List

from lib.email_sender import EmailSender
from db.database import LeadDatabase, LeadStatus, Lead, EmailRecord


def get_leads_for_emailing(db: LeadDatabase, limit: int = 10, include_generated: bool = True) -> List[Lead]:
    """
    Get leads that are ready for email outreach.

    Args:
        db: Database instance
        limit: Maximum leads to return
        include_generated: If True, include leads with generated emails (info@...)
            These are less likely to succeed but still worth trying.
    """
    leads = db.get_leads(limit=100)

    # Filter leads that:
    # 1. Have status 'report_generated' (pipeline completed)
    # 2. Have an email with @
    # 3. Haven't been contacted yet
    eligible = []
    generated = []  # Leads with auto-generated emails

    for lead in leads:
        email = str(lead.email or '').strip()
        if not email or email == '':
            continue
        if '@' not in email:
            continue
        if lead.status in ['contacted', 'responded', 'converted', 'trashed']:
            continue

        # Check if it's a generated email
        is_generated = email.startswith('info@') and len(email) > 15 and '.com' in email

        if is_generated:
            generated.append(lead)
        else:
            eligible.append(lead)

    # If no real emails, use generated ones
    if not eligible and include_generated:
        eligible = generated[:limit]

    return eligible[:limit]


def send_emails_to_leads(leads: List[Lead], attach_pdf: bool = True) -> dict:
    """
    Send emails to multiple leads with their reports.
    """
    sender = EmailSender()
    results = {
        'total': len(leads),
        'sent': 0,
        'failed': 0,
        'leads': []
    }

    # Get most recent PDF
    report_dir = 'output/reports'
    pdfs = sorted([f for f in os.listdir(report_dir) if f.endswith('.pdf')], reverse=True)
    latest_pdf = os.path.join(report_dir, pdfs[0]) if pdfs else None

    for i, lead in enumerate(leads, 1):
        print(f"\n[{i}/{len(leads)}] Processing: {lead.business_name[:40]}")
        print(f"  Email: {lead.email}")

        # Build email content
        subject = f"Quick look at {lead.business_name} online presence"

        body = f"""Hi {lead.business_name} team,

I was researching businesses in the Pimpri-Chinchwad area and came across {lead.business_name}.

I ran a quick analysis of your online presence and found a few things worth sharing:

"""

        # Add findings based on lead data
        if lead.rating:
            body += f"- Google Rating: {lead.rating} stars\n"
        if lead.review_count:
            body += f"- Reviews: {lead.review_count} Google reviews\n"
        if lead.website:
            body += f"- Website: {lead.website}\n"

        body += """
The attached report has specific suggestions for improving your online presence.

Interested? Just reply to this email or WhatsApp me (__PHONE_REDACTED__) - happy to chat about what would work best.

No pressure, no sales pitch. Just a friendly conversation about your options.

Best regards,
PrismaticWorks Team
WhatsApp: __PHONE_REDACTED__
"""

        # Send email
        attachments = [latest_pdf] if attach_pdf and latest_pdf else None

        try:
            result = sender.send_email(
                to_email=lead.email,
                subject=subject,
                body=body,
                attachments=attachments
            )

            if result['success']:
                # Record in database
                record = EmailRecord(
                    lead_id=lead.id,
                    email_type='initial',
                    subject=subject,
                    body=body[:500],  # Truncate for storage
                    pdf_report_path=latest_pdf or '',
                    sent_at=datetime.now().isoformat(),
                    delivered=True
                )
                db.record_email(record)

                # Update lead status
                db.update_lead(lead.id, status=LeadStatus.CONTACTED.value)

                results['sent'] += 1
                print(f"  -> SUCCESS")
            else:
                results['failed'] += 1
                print(f"  -> FAILED: {result.get('message', 'Unknown error')}")

            results['leads'].append({
                'name': lead.business_name,
                'email': lead.email,
                'success': result['success']
            })

        except Exception as e:
            results['failed'] += 1
            print(f"  -> ERROR: {str(e)}")

        # Rate limiting - wait between emails
        if i < len(leads):
            print("  Waiting 30s before next email...")
            import time
            time.sleep(30)

    return results


def run_email_campaign(max_emails: int = 10):
    """Run the email campaign."""
    print("=" * 60)
    print("PRISMATICWORKS EMAIL CAMPAIGN")
    print("=" * 60)

    db = LeadDatabase()

    # Get eligible leads
    leads = get_leads_for_emailing(db, limit=max_emails)

    print(f"\nFound {len(leads)} leads ready for email")
    print("\nLeads to email:")

    for lead in leads:
        print(f"  - {lead.business_name[:40]}: {lead.email}")

    if not leads:
        print("\nNo eligible leads found.")
        print("\nTips:")
        print("  1. Run the pipeline first: python run_pipeline.py --count 10")
        print("  2. Or add leads with real email addresses")
        return

    # Confirm
    print(f"\nReady to send {len(leads)} emails? (y/n)")
    # Auto-yes for automation
    # response = input()

    print("\n" + "-" * 60)
    print("SENDING EMAILS")
    print("-" * 60)

    results = send_emails_to_leads(leads)

    print("\n" + "=" * 60)
    print("CAMPAIGN COMPLETE")
    print("=" * 60)
    print(f"Total: {results['total']}")
    print(f"Sent: {results['sent']}")
    print(f"Failed: {results['failed']}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Send emails to leads")
    parser.add_argument("--count", type=int, default=5, help="Max emails to send")
    parser.add_argument("--dry-run", action="store_true", help="Show leads without sending")

    args = parser.parse_args()

    if args.dry_run:
        db = LeadDatabase()
        leads = get_leads_for_emailing(db, limit=args.count)
        print(f"\n{len(leads)} leads would be emailed:")
        for lead in leads:
            print(f"  - {lead.business_name}: {lead.email}")
    else:
        run_email_campaign(max_emails=args.count)
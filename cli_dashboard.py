"""
Lead Making Machine - CLI Dashboard
A simple terminal UI for managing leads, emails, and pipeline operations.
Works in Windows cmd without fancy dependencies.
"""

import os
import sys
import sqlite3
import subprocess
import csv
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# Configuration
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "leads.db")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def clear_screen():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def print_header(title: str):
    """Print a formatted header."""
    width = 70
    print("\n" + "=" * width)
    print(f"  {title}".ljust(width))
    print("=" * width)


def print_subheader(title: str):
    """Print a formatted subheader."""
    width = 70
    print(f"\n--- {title} ---".ljust(width))


def get_db_connection() -> sqlite3.Connection:
    """Get a connection to the leads database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize the database schema if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            company TEXT,
            phone TEXT,
            category TEXT,
            source TEXT,
            status TEXT DEFAULT 'new',
            emails_sent INTEGER DEFAULT 0,
            emails_opened INTEGER DEFAULT 0,
            replies INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_contacted TIMESTAMP,
            next_followup TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            subject TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            opened INTEGER DEFAULT 0,
            replied INTEGER DEFAULT 0,
            FOREIGN KEY (lead_id) REFERENCES leads (id)
        )
    """)

    conn.commit()
    conn.close()


def get_stats() -> Dict[str, int]:
    """Get current statistics from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    stats = {
        "total_leads": 0,
        "emails_sent": 0,
        "emails_opened": 0,
        "replies": 0,
        "conversions": 0,
        "new_leads": 0,
        "contacted": 0,
        "qualified": 0,
        "converted": 0,
    }

    try:
        cursor.execute("SELECT COUNT(*) FROM leads")
        stats["total_leads"] = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(emails_sent) FROM leads")
        stats["emails_sent"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT SUM(emails_opened) FROM leads")
        stats["emails_opened"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT SUM(replies) FROM leads")
        stats["replies"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT SUM(conversions) FROM leads")
        stats["conversions"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'new'")
        stats["new_leads"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'contacted'")
        stats["contacted"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'qualified'")
        stats["qualified"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'converted'")
        stats["converted"] = cursor.fetchone()[0]

    except sqlite3.OperationalError:
        pass  # Table doesn't exist yet

    conn.close()
    return stats


def get_recent_leads(limit: int = 10) -> List[sqlite3.Row]:
    """Get recent leads from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    leads = []
    try:
        cursor.execute("""
            SELECT id, name, email, company, category, status,
                   emails_sent, replies, conversions, created_at
            FROM leads
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        leads = cursor.fetchall()
    except sqlite3.OperationalError:
        pass  # Table doesn't exist yet

    conn.close()
    return leads


def get_all_leads() -> List[sqlite3.Row]:
    """Get all leads from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    leads = []
    try:
        cursor.execute("""
            SELECT id, name, email, company, category, status,
                   emails_sent, replies, conversions, created_at
            FROM leads
            ORDER BY created_at DESC
        """)
        leads = cursor.fetchall()
    except sqlite3.OperationalError:
        pass

    conn.close()
    return leads


def get_lead_by_id(lead_id: int) -> Optional[sqlite3.Row]:
    """Get a specific lead by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()

    lead = None
    try:
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        lead = cursor.fetchone()
    except sqlite3.OperationalError:
        pass

    conn.close()
    return lead


def update_lead_status(lead_id: int, new_status: str):
    """Update the status of a lead."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE leads
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, lead_id))
        conn.commit()
        print(f"  Lead #{lead_id} status updated to '{new_status}'")
    except sqlite3.OperationalError as e:
        print(f"  Error updating lead: {e}")

    conn.close()


def display_stats():
    """Display the current statistics."""
    stats = get_stats()

    print_subheader("CURRENT STATISTICS")
    print()
    print(f"  Total Leads:        {stats['total_leads']}")
    print(f"  Emails Sent:        {stats['emails_sent']}")
    print(f"  Emails Opened:      {stats['emails_opened']}")
    print(f"  Replies:            {stats['replies']}")
    print(f"  Conversions:        {stats['conversions']}")
    print()
    print("  --- Lead Status Breakdown ---")
    print(f"  New:       {stats['new_leads']}")
    print(f"  Contacted: {stats['contacted']}")
    print(f"  Qualified: {stats['qualified']}")
    print(f"  Converted: {stats['converted']}")


def display_leads_table(leads: List[sqlite3.Row]):
    """Display leads in a formatted table."""
    if not leads:
        print("\n  No leads found.")
        return

    # Table header
    print()
    print(f"  {'ID':<4} {'Name':<18} {'Email':<22} {'Company':<15} {'Status':<10} {'Sent':<5} {'Rep':<4}")
    print("  " + "-" * 82)

    for lead in leads:
        name = (lead["name"] or "N/A")[:17]
        email = (lead["email"] or "N/A")[:21]
        company = (lead["company"] or "N/A")[:14]
        status = lead["status"] or "new"
        sent = lead["emails_sent"] or 0
        replies = lead["replies"] or 0

        print(f"  {lead['id']:<4} {name:<18} {email:<22} {company:<15} {status:<10} {sent:<5} {replies:<4}")


def run_pipeline():
    """Run the lead generation pipeline."""
    print("\n  Running lead generation pipeline...")
    print("  (This will open a new command window)")

    bat_path = os.path.join(PROJECT_DIR, "RUN_PIPELINE.bat")
    if os.path.exists(bat_path):
        subprocess.Popen(f'start cmd /k "{bat_path}"', shell=True)
        print("  Pipeline started in new window.")
    else:
        print("  ERROR: RUN_PIPELINE.bat not found!")
        print(f"  Expected at: {bat_path}")


def run_email_sender():
    """Run the email sender."""
    print("\n  Running email sender...")
    print("  (This will open a new command window)")

    bat_path = os.path.join(PROJECT_DIR, "SEND_EMAILS.bat")
    if os.path.exists(bat_path):
        subprocess.Popen(f'start cmd /k "{bat_path}"', shell=True)
        print("  Email sender started in new window.")
    else:
        print("  ERROR: SEND_EMAILS.bat not found!")


def check_responses():
    """Check for email responses."""
    print("\n  Checking for email responses...")
    print("  (This will open a new command window)")

    bat_path = os.path.join(PROJECT_DIR, "FOLLOWUP.bat")
    if os.path.exists(bat_path):
        subprocess.Popen(f'start cmd /k "{bat_path}"', shell=True)
        print("  Followup check started in new window.")
    else:
        print("  ERROR: FOLLOWUP.bat not found!")


def view_lead_details():
    """View detailed information about a specific lead."""
    try:
        lead_id = int(input("\n  Enter lead ID: "))
    except ValueError:
        print("  Invalid ID. Please enter a number.")
        return

    lead = get_lead_by_id(lead_id)

    if lead is None:
        print(f"  Lead #{lead_id} not found.")
        return

    print_subheader(f"LEAD #{lead['id']} DETAILS")
    print()
    print(f"  Name:         {lead['name'] or 'N/A'}")
    print(f"  Email:        {lead['email'] or 'N/A'}")
    print(f"  Phone:        {lead['phone'] or 'N/A'}")
    print(f"  Company:      {lead['company'] or 'N/A'}")
    print(f"  Category:     {lead['category'] or 'N/A'}")
    print(f"  Source:       {lead['source'] or 'N/A'}")
    print(f"  Status:       {lead['status'] or 'new'}")
    print()
    print(f"  Emails Sent:  {lead['emails_sent'] or 0}")
    print(f"  Opened:       {lead['emails_opened'] or 0}")
    print(f"  Replies:      {lead['replies'] or 0}")
    print(f"  Conversions:  {lead['conversions'] or 0}")
    print()
    print(f"  Notes:        {lead['notes'] or 'No notes'}")
    print()
    print(f"  Created:      {lead['created_at'] or 'N/A'}")
    print(f"  Updated:      {lead['updated_at'] or 'N/A'}")
    print(f"  Last Contact: {lead['last_contacted'] or 'Never'}")
    print(f"  Next Follow:  {lead['next_followup'] or 'Not scheduled'}")


def update_lead_status_menu():
    """Update the status of a lead."""
    try:
        lead_id = int(input("\n  Enter lead ID: "))
    except ValueError:
        print("  Invalid ID. Please enter a number.")
        return

    lead = get_lead_by_id(lead_id)
    if lead is None:
        print(f"  Lead #{lead_id} not found.")
        return

    print(f"\n  Current status: {lead['status']}")
    print("\n  Available statuses:")
    print("    1. new")
    print("    2. contacted")
    print("    3. qualified")
    print("    4. converted")
    print("    5. unresponsive")
    print("    6. cancelled")

    choice = input("\n  Enter new status (1-6): ").strip()

    status_map = {
        "1": "new",
        "2": "contacted",
        "3": "qualified",
        "4": "converted",
        "5": "unresponsive",
        "6": "cancelled"
    }

    if choice in status_map:
        update_lead_status(lead_id, status_map[choice])
    else:
        print("  Invalid choice.")


def export_data():
    """Export leads data to CSV."""
    leads = get_all_leads()

    if not leads:
        print("\n  No leads to export.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(PROJECT_DIR, f"leads_export_{timestamp}.csv")

    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ID", "Name", "Email", "Phone", "Company", "Category",
                "Source", "Status", "Emails Sent", "Opened", "Replies",
                "Conversions", "Notes", "Created", "Last Contacted"
            ])

            for lead in leads:
                writer.writerow([
                    lead["id"],
                    lead["name"] or "",
                    lead["email"] or "",
                    lead["phone"] or "",
                    lead["company"] or "",
                    lead["category"] or "",
                    lead["source"] or "",
                    lead["status"] or "new",
                    lead["emails_sent"] or 0,
                    lead["emails_opened"] or 0,
                    lead["replies"] or 0,
                    lead["conversions"] or 0,
                    lead["notes"] or "",
                    lead["created_at"] or "",
                    lead["last_contacted"] or ""
                ])

        print(f"\n  Exported {len(leads)} leads to:")
        print(f"  {filename}")

    except Exception as e:
        print(f"\n  Error exporting data: {e}")


def add_sample_leads():
    """Add some sample leads for testing."""
    conn = get_db_connection()
    cursor = conn.cursor()

    sample_leads = [
        ("John Smith", "__EMAIL_REDACTED__", "TechCorp Inc", "+1-555-0101", "technology", "website"),
        ("Sarah Johnson", "__EMAIL_REDACTED__", "StartupIO", "+1-555-0102", "technology", "linkedin"),
        ("Mike Williams", "__EMAIL_REDACTED__", "RetailPlus", "+1-555-0103", "retail", "website"),
        ("Emily Brown", "__EMAIL_REDACTED__", "HealthFirst Medical", "+1-555-0104", "healthcare", "referral"),
        ("David Lee", "__EMAIL_REDACTED__", "FoodieHub Restaurant", "+1-555-0105", "restaurant", "website"),
    ]

    for name, email, company, phone, category, source in sample_leads:
        try:
            cursor.execute("""
                INSERT INTO leads (name, email, company, phone, category, source, status, emails_sent)
                VALUES (?, ?, ?, ?, ?, ?, 'contacted', 1)
            """, (name, email, company, phone, category, source))
        except:
            pass

    conn.commit()
    conn.close()
    print("\n  Added sample leads for testing.")


def show_help():
    """Display help information."""
    print_subheader("AVAILABLE COMMANDS")
    print()
    print("  1. Dashboard     - Show main dashboard with stats and recent leads")
    print("  2. Leads         - View all leads")
    print("  3. Run Pipeline  - Start the lead generation pipeline")
    print("  4. Send Emails   - Run the email outreach agent")
    print("  5. Check Replies - Check for email responses")
    print("  6. View Lead     - View detailed info for a specific lead")
    print("  7. Update Status - Change a lead's status")
    print("  8. Export        - Export all leads to CSV file")
    print("  9. Add Samples   - Add sample leads for testing")
    print("  10. Help         - Show this help message")
    print("  0. Quit          - Exit the dashboard")


def main_menu():
    """Display the main menu."""
    print()
    print("  1. Dashboard")
    print("  2. View All Leads")
    print("  3. Run Pipeline")
    print("  4. Send Emails")
    print("  5. Check Responses")
    print("  6. View Lead Details")
    print("  7. Update Lead Status")
    print("  8. Export Data")
    print("  9. Add Sample Leads")
    print("  H. Help")
    print("  0. Quit")


def main():
    """Main entry point for the CLI dashboard."""
    clear_screen()
    print_header("LEAD MAKING MACHINE - CLI DASHBOARD")

    # Initialize database
    init_database()

    print("\n  Welcome to the Lead Making Machine CLI Dashboard!")
    print("  Type 'H' for help with available commands.\n")

    while True:
        main_menu()
        choice = input("\n  Select option: ").strip().lower()

        if choice == "1" or choice == "d":
            clear_screen()
            print_header("DASHBOARD")
            display_stats()
            print_subheader("RECENT LEADS")
            leads = get_recent_leads(10)
            display_leads_table(leads)

        elif choice == "2" or choice == "l":
            clear_screen()
            print_header("ALL LEADS")
            leads = get_all_leads()
            display_leads_table(leads)

        elif choice == "3" or choice == "p":
            run_pipeline()

        elif choice == "4" or choice == "e":
            run_email_sender()

        elif choice == "5" or choice == "r":
            check_responses()

        elif choice == "6" or choice == "v":
            clear_screen()
            print_header("VIEW LEAD DETAILS")
            view_lead_details()

        elif choice == "7" or choice == "u":
            clear_screen()
            print_header("UPDATE LEAD STATUS")
            update_lead_status_menu()

        elif choice == "8" or choice == "x":
            export_data()

        elif choice == "9" or choice == "s":
            add_sample_leads()

        elif choice == "h" or choice == "help":
            clear_screen()
            print_header("HELP")
            show_help()

        elif choice == "0" or choice == "q" or choice == "quit":
            print("\n  Goodbye!\n")
            break

        else:
            print("\n  Invalid option. Type 'H' for help.")

        input("\n  Press Enter to continue...")


if __name__ == "__main__":
    main()

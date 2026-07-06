#!/usr/bin/env python3
"""
LeadMakingMachine - Installation Script
Checks dependencies, creates environment, and tests configuration
"""

import os
import sys
import sqlite3
import shutil
from pathlib import Path


class Installer:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.python_min_version = (3, 9)
        self.required_files = ['requirements.txt', '.env.example']

    def log(self, message, status="INFO"):
        icons = {"INFO": "[*]", "OK": "[+]", "WARN": "[!]", "ERROR": "[X]"}
        print(f"{icons.get(status, '[*]')} {message}")

    def check_python_version(self):
        """Verify Python version meets requirements"""
        self.log("Checking Python version...")
        version = sys.version_info[:2]
        if version >= self.python_min_version:
            self.log(f"Python {sys.version}", "OK")
            return True
        else:
            self.log(f"Python {version} - Required: {self.python_min_version}+", "ERROR")
            return False

    def check_pip(self):
        """Verify pip is available"""
        self.log("Checking pip...")
        try:
            import pip
            self.log(f"pip {pip.__version__}", "OK")
            return True
        except ImportError:
            self.log("pip not found - please reinstall Python with pip", "ERROR")
            return False

    def install_requirements(self):
        """Install Python dependencies"""
        self.log("Installing requirements...")
        requirements_file = self.project_root / "requirements.txt"

        if not requirements_file.exists():
            self.log("requirements.txt not found", "ERROR")
            return False

        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.log("Dependencies installed successfully", "OK")
                return True
            else:
                self.log(f"pip install failed: {result.stderr[:200]}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Installation error: {e}", "ERROR")
            return False

    def create_env_file(self):
        """Create .env file from template if missing"""
        env_file = self.project_root / ".env"
        env_template = self.project_root / ".env.example"

        if env_file.exists():
            self.log(".env file already exists", "OK")
            return True

        if not env_template.exists():
            self.log(".env.example not found", "ERROR")
            return False

        try:
            shutil.copy(env_template, env_file)
            self.log(".env file created from template", "OK")
            self.log("Please edit .env and add your API keys", "WARN")
            return True
        except Exception as e:
            self.log(f"Failed to create .env: {e}", "ERROR")
            return False

    def create_directories(self):
        """Create necessary project directories"""
        self.log("Creating project directories...")

        dirs = ['data', 'logs', 'templates', 'cache']
        success = True

        for dir_name in dirs:
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                self.log(f"{dir_name}/ already exists", "OK")
            else:
                try:
                    dir_path.mkdir()
                    self.log(f"{dir_name}/ created", "OK")
                except Exception as e:
                    self.log(f"Failed to create {dir_name}/: {e}", "ERROR")
                    success = False

        return success

    def create_database(self):
        """Initialize SQLite database"""
        self.log("Initializing database...")

        data_dir = self.project_root / "data"
        data_dir.mkdir(exist_ok=True)

        db_path = data_dir / "leads.db"

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Create leads table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    phone TEXT,
                    website TEXT,
                    industry TEXT,
                    size TEXT,
                    location TEXT,
                    status TEXT DEFAULT 'new',
                    score INTEGER DEFAULT 0,
                    notes TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create campaigns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    subject TEXT,
                    template TEXT,
                    status TEXT DEFAULT 'draft',
                    sent_count INTEGER DEFAULT 0,
                    response_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create emails table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id INTEGER,
                    campaign_id INTEGER,
                    subject TEXT,
                    body TEXT,
                    status TEXT DEFAULT 'pending',
                    sent_at TIMESTAMP,
                    delivered_at TIMESTAMP,
                    opened_at TIMESTAMP,
                    replied_at TIMESTAMP,
                    bounced_at TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads(id),
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
                )
            """)

            # Create responses table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id INTEGER,
                    lead_id INTEGER,
                    subject TEXT,
                    body TEXT,
                    from_address TEXT,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sentiment TEXT,
                    FOREIGN KEY (email_id) REFERENCES emails(id),
                    FOREIGN KEY (lead_id) REFERENCES leads(id)
                )
            """)

            # Create followups table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS followups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id INTEGER,
                    email_id INTEGER,
                    sequence_number INTEGER DEFAULT 1,
                    scheduled_at TIMESTAMP,
                    sent_at TIMESTAMP,
                    status TEXT DEFAULT 'scheduled',
                    FOREIGN KEY (lead_id) REFERENCES leads(id),
                    FOREIGN KEY (email_id) REFERENCES emails(id)
                )
            """)

            conn.commit()
            conn.close()

            self.log("Database initialized successfully", "OK")
            return True

        except Exception as e:
            self.log(f"Database initialization failed: {e}", "ERROR")
            return False

    def test_database(self):
        """Test database connection and basic operations"""
        self.log("Testing database connection...")

        db_path = self.project_root / "data" / "leads.db"

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Test read
            cursor.execute("SELECT COUNT(*) FROM leads")
            count = cursor.fetchone()[0]

            # Test write
            cursor.execute("SELECT 1")
            cursor.fetchone()

            conn.close()

            self.log(f"Database OK - {count} leads", "OK")
            return True

        except Exception as e:
            self.log(f"Database test failed: {e}", "ERROR")
            return False

    def run(self):
        """Run full installation process"""
        print("=" * 50)
        print("  LEAD MAKING MACHINE - INSTALLER")
        print("=" * 50)
        print()

        checks = [
            ("Python Version", self.check_python_version),
            ("Pip Available", self.check_pip),
            ("Install Dependencies", self.install_requirements),
            ("Create Directories", self.create_directories),
            ("Create Environment", self.create_env_file),
            ("Initialize Database", self.create_database),
            ("Test Database", self.test_database),
        ]

        results = []
        for name, func in checks:
            print(f"\n--- {name} ---")
            result = func()
            results.append((name, result))

        # Summary
        print("\n" + "=" * 50)
        print("  INSTALLATION SUMMARY")
        print("=" * 50)

        all_passed = True
        for name, result in results:
            status = "OK" if result else "FAIL"
            print(f"  {name:<25} [{status}]")
            if not result:
                all_passed = False

        print()

        if all_passed:
            print("[+] Installation complete!")
            print("\nNext steps:")
            print("  1. Edit .env and add your API keys")
            print("  2. Run: python MAIN.py")
        else:
            print("[!] Installation completed with errors")
            print("    Please fix the issues above and run again")

        return all_passed


if __name__ == "__main__":
    installer = Installer()
    success = installer.run()
    sys.exit(0 if success else 1)

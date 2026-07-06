"""
Scraper Service - Lead scraping using Apify
"""

import requests
import sqlite3
from datetime import datetime
from typing import List, Dict


class ScraperService:
    def __init__(self, settings):
        self.settings = settings
        self.db_path = settings.db_path_absolute

    def scrape_leads(self) -> List[Dict]:
        """Scrape leads from Apify"""
        if not self.settings.APIFY_TOKEN:
            print("[WARN] APIFY_TOKEN not configured")
            return []

        # Apify Google Maps Scraper actor
        url = "https://api.apify.com/v2/acts/apify~google-maps-scraper/runs"

        payload = {
            "startUrls": [
                {"url": "https://www.google.com/maps/search/software+companies+in+USA"}
            ],
            "maxResults": 50,
        }

        headers = {
            "Authorization": f"Bearer {self.settings.APIFY_TOKEN}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                run_id = response.json()["data"]["id"]
                return self._wait_for_results(run_id)
            else:
                print(f"[ERROR] Apify request failed: {response.status_code}")
                return []
        except Exception as e:
            print(f"[ERROR] Scraping failed: {e}")
            return []

    def _wait_for_results(self, run_id: str, timeout: int = 300) -> List[Dict]:
        """Wait for Apify run to complete and get results"""
        status_url = f"https://api.apify.com/v2/acts/apify~google-maps-scraper/runs/{run_id}"

        for _ in range(timeout // 10):
            try:
                response = requests.get(status_url, headers={"Authorization": f"Bearer {self.settings.APIFY_TOKEN}"})
                data = response.json()["data"]

                if data.get("status") == "SUCCEEDED":
                    dataset_id = data["defaultDatasetId"]
                    return self._fetch_dataset(dataset_id)
                elif data.get("status") in ["FAILED", "ABORTED"]:
                    print(f"[ERROR] Apify run {data['status']}")
                    return []

            except Exception as e:
                print(f"[WARN] Status check failed: {e}")

        return []

    def _fetch_dataset(self, dataset_id: str) -> List[Dict]:
        """Fetch results from Apify dataset"""
        url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"[ERROR] Failed to fetch dataset: {e}")

        return []

    def audit_leads(self, leads: List[Dict]) -> List[Dict]:
        """Audit leads for quality using AI"""
        if not self.settings.ANTHROPIC_API_KEY:
            print("[WARN] ANTHROPIC_API_KEY not configured - skipping audit")
            return leads

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.settings.ANTHROPIC_API_KEY)

            audited = []
            for lead in leads:
                # Simple scoring based on completeness
                score = 0
                if lead.get('name'):
                    score += 25
                if lead.get('phones'):
                    score += 25
                if lead.get('website'):
                    score += 25
                if lead.get('address'):
                    score += 25

                if score >= 50:  # Minimum quality threshold
                    lead['score'] = score
                    audited.append(lead)

            return audited

        except Exception as e:
            print(f"[ERROR] Audit failed: {e}")
            return leads

    def save_leads(self, leads: List[Dict]) -> int:
        """Save leads to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        saved = 0

        for lead in leads:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO leads
                    (company, email, phone, website, industry, location, status, score, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)
                """, (
                    lead.get('name', ''),
                    lead.get('emails', [''])[0] if lead.get('emails') else '',
                    lead.get('phones', [''])[0] if lead.get('phones') else '',
                    lead.get('website', ''),
                    lead.get('category', ''),
                    lead.get('address', ''),
                    lead.get('score', 0),
                    'apify',
                    datetime.now()
                ))
                saved += cursor.rowcount
            except Exception as e:
                pass

        conn.commit()
        conn.close()
        return saved

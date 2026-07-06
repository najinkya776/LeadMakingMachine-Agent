"""Apify client for web scraping operations."""

import httpx
import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from config.apify import (
    APIFY_TOKEN,
    APIFY_ACTORS,
    GOOGLE_MAPS_SETTINGS,
    FACEBOOK_SETTINGS,
    INSTAGRAM_SETTINGS,
)


class ApifyClient:
    """Client for Apify API operations."""

    BASE_URL = "https://api.apify.com/v2"

    def __init__(self, token: Optional[str] = None):
        """Initialize Apify client."""
        self.token = token or APIFY_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _get_headers(self) -> dict:
        """Get headers with auth token."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def start_actor(
        self,
        actor_id: str,
        input_data: dict,
        wait_for_finish: bool = True,
        timeout: int = 180,
    ) -> dict:
        """Start an actor and optionally wait for results."""
        url = f"{self.BASE_URL}/acts/{actor_id}/runs"

        response = httpx.post(
            url,
            json=input_data,
            headers=self._get_headers(),
            timeout=timeout,
        )
        response.raise_for_status()

        run = response.json()["data"]

        if wait_for_finish:
            return self.wait_for_run(run["id"], timeout=timeout, actor_id=actor_id)

        return run

    def wait_for_run(self, run_id: str, timeout: int = 120, actor_id: str = "") -> dict:
        """Wait for actor run to complete."""
        start_time = datetime.utcnow()
        interval = 8  # Poll every 8 seconds

        while True:
            elapsed = (datetime.utcnow() - start_time).seconds
            if elapsed > timeout:
                raise TimeoutError(f"Run {run_id} timed out after {timeout}s")

            response = httpx.get(
                f"{self.BASE_URL}/acts/{actor_id}/runs/{run_id}",
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()

            run_data = response.json()["data"]
            status = run_data.get("status", "")

            if status == "SUCCEEDED":
                return run_data
            elif status in ["FAILED", "ABORTED", "TIMED_OUT"]:
                raise RuntimeError(f"Run failed with status: {status}")

            time.sleep(interval)

    def get_dataset_items(
        self,
        dataset_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[dict]:
        """Get items from a dataset."""
        # Extract dataset ID from URL if full URL provided
        if "/" in str(dataset_id):
            dataset_id = dataset_id.split("/")[-1]

        url = f"{self.BASE_URL}/datasets/{dataset_id}/items"
        params = {"limit": limit, "offset": offset, "clean": True}

        response = httpx.get(
            url,
            params=params,
            headers=self._get_headers(),
            timeout=60,
        )
        response.raise_for_status()

        return response.json()

    def scrape_google_maps(
        self,
        queries: List[str],
        location: str = "Pimpri-Chinchwad, Pune, India",
        max_results: int = 50,
    ) -> List[dict]:
        """
        Scrape Google Maps for business listings.
        Uses startUrls with Google Maps search URLs.
        """
        actor_id = APIFY_ACTORS["google_maps_scraper"]

        # Create Google Maps search URLs
        start_urls = []
        for query in queries:
            # Clean query for URL
            clean_query = query.replace(" ", "+").replace(",", "%2C")
            maps_url = f"https://www.google.com/maps/search/{clean_query}"
            start_urls.append({"url": maps_url})

        input_data = {
            "startUrls": start_urls,
            "maxResults": max_results,
            "language": "en",
        }

        print(f"[Apify] Scraping {len(queries)} queries...")

        try:
            run = self.start_actor(actor_id, input_data)

            if run.get("defaultDatasetId"):
                items = self.get_dataset_items(run["defaultDatasetId"])
                print(f"[Apify] Got {len(items)} results")
                return items

        except Exception as e:
            print(f"[Apify] Scraping error: {e}")

        return []

    def scrape_google_maps_by_category(
        self,
        category: str,
        location: str = "Pimpri-Chinchwad, Pune, India",
        max_results: int = 50,
    ) -> List[dict]:
        """Scrape Google Maps for a specific category."""
        query = f"{category}+near+{location}"
        return self.scrape_google_maps([query], location, max_results)

    def scrape_facebook_pages(
        self,
        business_names: List[str],
        max_items: int = 50,
    ) -> List[dict]:
        """Scrape Facebook pages for businesses."""
        actor_id = APIFY_ACTORS["facebook_pages_scraper"]

        # Create Facebook search URLs
        start_urls = []
        for name in business_names:
            fb_url = f"https://www.facebook.com/search?q={name.replace(' ', '+')}"
            start_urls.append({"url": fb_url})

        input_data = {
            "startUrls": start_urls,
            "maxItems": max_items,
            "scrapeAbout": True,
            "scrapePosts": False,
            "scrapeReviews": True,
        }

        try:
            run = self.start_actor(actor_id, input_data)

            if run.get("defaultDatasetId"):
                return self.get_dataset_items(run["defaultDatasetId"])

        except Exception as e:
            print(f"[Apify] Facebook scraping error: {e}")

        return []

    def scrape_instagram(
        self,
        usernames: List[str],
        max_items: int = 30,
    ) -> List[dict]:
        """Scrape Instagram profiles."""
        actor_id = APIFY_ACTORS["instagram_scraper"]

        # Create Instagram profile URLs
        start_urls = []
        for username in usernames:
            ig_url = f"https://www.instagram.com/{username}/"
            start_urls.append({"url": ig_url})

        input_data = {
            "startUrls": start_urls,
            "maxItems": max_items,
            "scrapePosts": True,
            "scrapeReels": False,
        }

        try:
            run = self.start_actor(actor_id, input_data)

            if run.get("defaultDatasetId"):
                return self.get_dataset_items(run["defaultDatasetId"])

        except Exception as e:
            print(f"[Apify] Instagram scraping error: {e}")

        return []

    def crawl_website(
        self,
        url: str,
        max_pages: int = 10,
        max_depth: int = 2,
    ) -> List[dict]:
        """Crawl website content."""
        actor_id = APIFY_ACTORS["website_content_crawler"]

        input_data = {
            "startUrls": [{"url": url}],
            "maxCrawlDuration": 300,
            "maxPages": max_pages,
            "maxDepth": max_depth,
            "stayWithinDomain": True,
        }

        try:
            run = self.start_actor(actor_id, input_data)

            if run.get("defaultDatasetId"):
                return self.get_dataset_items(run["defaultDatasetId"])

        except Exception as e:
            print(f"[Apify] Website crawl error: {e}")

        return []

    def quick_scrape(
        self,
        actor_id: str,
        input_data: dict,
    ) -> str:
        """Start a scrape without waiting for completion. Returns run ID."""
        url = f"{self.BASE_URL}/acts/{actor_id}/runs"

        response = httpx.post(
            url,
            json=input_data,
            headers=self._get_headers(),
            timeout=30,
        )
        response.raise_for_status()

        return response.json()["data"]["id"]

    def get_run_status(self, run_id: str, actor_id: str = "") -> dict:
        """Get status of an actor run."""
        response = httpx.get(
            f"{self.BASE_URL}/acts/{actor_id}/runs/{run_id}",
            headers=self._get_headers(),
            timeout=30,
        )
        response.raise_for_status()

        return response.json()["data"]

    def get_run_results(self, run_id: str, actor_id: str = "") -> List[dict]:
        """Get results from a completed run."""
        run = self.get_run_status(run_id, actor_id)

        if run.get("status") != "SUCCEEDED":
            return []

        if run.get("defaultDatasetId"):
            return self.get_dataset_items(run["defaultDatasetId"])

        return []


def scrape_businesses(
    categories: List[str],
    location: str = "Pimpri-Chinchwad, Pune",
    max_per_category: int = 50,
) -> List[dict]:
    """Scrape businesses by categories using Apify."""
    client = ApifyClient()
    all_leads = []

    for category in categories:
        try:
            leads = client.scrape_google_maps_by_category(
                category, location, max_per_category
            )
            all_leads.extend(leads)
            print(f"[Apify] {category}: {len(leads)} leads")
        except Exception as e:
            print(f"[Apify] Error scraping {category}: {e}")
            continue

    return all_leads
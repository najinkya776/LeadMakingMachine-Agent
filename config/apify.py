"""Apify configuration and actor settings."""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Apify Token
# =============================================================================

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "__REDACTED__APIFY_TOKEN__")

# =============================================================================
# Apify Actor IDs
# =============================================================================

APIFY_ACTORS = {
    "google_maps_scraper": "compass~crawler-google-places",
    "facebook_pages_scraper": "apify~facebook-pages-scraper",
    "instagram_scraper": "apify~instagram-scraper",
    "website_content_crawler": "apify~website-content-crawler",
}

# =============================================================================
# Alternative actor IDs (numeric IDs)
# =============================================================================

APIFY_ACTOR_IDS = {
    "google_maps_scraper": "nwua9Gu5YrADL7ZDj",
    "facebook_pages_scraper": "4Hv5RhChiaDk6iwad",
}

# =============================================================================
# Google Maps Scraper Settings
# =============================================================================

GOOGLE_MAPS_SETTINGS = {
    "searchQueries": [],
    "maxResults": 100,
    "language": "en",
    "locations": ["Pimpri-Chinchwad, Pune, India"],
    "coordinates": {
        "lat": 18.6298,
        "lng": 73.7997,
    },
    "zoom": 12,
    "startUrls": [],
    "maxConcurrency": 5,
}

# =============================================================================
# Facebook Scraper Settings
# =============================================================================

FACEBOOK_SETTINGS = {
    "maxItems": 50,
    "scrapeAbout": True,
    "scrapePosts": True,
    "scrapeReviews": True,
    "scrapeMessages": False,
}

# =============================================================================
# Instagram Scraper Settings
# =============================================================================

INSTAGRAM_SETTINGS = {
    "maxItems": 30,
    "scrapePosts": True,
    "scrapeReels": False,
    "scrapeStories": False,
}

# =============================================================================
# Crawler Settings
# =============================================================================

CRAWLER_SETTINGS = {
    "maxDepth": 3,
    "maxPages": 10,
    "maxCost": 1000,
    "stayWithinDomain": True,
}
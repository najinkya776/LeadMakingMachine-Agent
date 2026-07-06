"""Curated target regions for lead harvesting.

Each region expands to a list of concrete search locations (cities). Google Maps
search returns far more results for specific cities than for a whole country, so
scraping across several cities is how we "get as much data as possible" for a region.

Two tiers:
  * tier1_english - high-value, English-speaking markets. One conversion here is
    worth far more than in the domestic market, and outreach is easy (no language
    barrier).
  * india - top domestic metros, kept for the existing domestic funnel.
"""

# region_key -> metadata + the cities we actually scrape for that region.
REGIONS = {
    # ===================== TIER 1 - ENGLISH-SPEAKING =====================
    "usa": {
        "label": "United States",
        "flag": "🇺🇸",
        "tier": "tier1_english",
        "country": "USA",
        "cities": [
            "New York, USA", "Los Angeles, USA", "Chicago, USA", "Houston, USA",
            "Phoenix, USA", "Dallas, USA", "Miami, USA", "Atlanta, USA",
            "Seattle, USA", "Denver, USA",
        ],
    },
    "uk": {
        "label": "United Kingdom",
        "flag": "🇬🇧",
        "tier": "tier1_english",
        "country": "UK",
        "cities": [
            "London, UK", "Manchester, UK", "Birmingham, UK", "Leeds, UK",
            "Glasgow, UK", "Liverpool, UK", "Bristol, UK", "Edinburgh, UK",
        ],
    },
    "canada": {
        "label": "Canada",
        "flag": "🇨🇦",
        "tier": "tier1_english",
        "country": "Canada",
        "cities": [
            "Toronto, Canada", "Vancouver, Canada", "Montreal, Canada",
            "Calgary, Canada", "Ottawa, Canada", "Edmonton, Canada",
        ],
    },
    "australia": {
        "label": "Australia",
        "flag": "🇦🇺",
        "tier": "tier1_english",
        "country": "Australia",
        "cities": [
            "Sydney, Australia", "Melbourne, Australia", "Brisbane, Australia",
            "Perth, Australia", "Adelaide, Australia", "Gold Coast, Australia",
        ],
    },
    "new_zealand": {
        "label": "New Zealand",
        "flag": "🇳🇿",
        "tier": "tier1_english",
        "country": "New Zealand",
        "cities": [
            "Auckland, New Zealand", "Wellington, New Zealand",
            "Christchurch, New Zealand", "Hamilton, New Zealand",
        ],
    },
    "ireland": {
        "label": "Ireland",
        "flag": "🇮🇪",
        "tier": "tier1_english",
        "country": "Ireland",
        "cities": [
            "Dublin, Ireland", "Cork, Ireland", "Galway, Ireland", "Limerick, Ireland",
        ],
    },
    "singapore": {
        "label": "Singapore",
        "flag": "🇸🇬",
        "tier": "tier1_english",
        "country": "Singapore",
        "cities": ["Singapore"],
    },
    "uae": {
        "label": "UAE (Dubai)",
        "flag": "🇦🇪",
        "tier": "tier1_english",
        "country": "UAE",
        "cities": [
            "Dubai, UAE", "Abu Dhabi, UAE", "Sharjah, UAE",
        ],
    },

    # ===================== INDIA - TOP METROS =====================
    "mumbai": {
        "label": "Mumbai",
        "flag": "🇮🇳",
        "tier": "india",
        "country": "India",
        "cities": [
            "Mumbai, India", "Navi Mumbai, India", "Thane, India",
        ],
    },
    "delhi_ncr": {
        "label": "Delhi NCR",
        "flag": "🇮🇳",
        "tier": "india",
        "country": "India",
        "cities": [
            "New Delhi, India", "Gurgaon, India", "Noida, India", "Faridabad, India",
        ],
    },
    "bangalore": {
        "label": "Bangalore",
        "flag": "🇮🇳",
        "tier": "india",
        "country": "India",
        "cities": ["Bangalore, India", "Whitefield, Bangalore, India"],
    },
    "pune": {
        "label": "Pune",
        "flag": "🇮🇳",
        "tier": "india",
        "country": "India",
        "cities": [
            "Pune, India", "Pimpri-Chinchwad, Pune, India", "Hinjewadi, Pune, India",
        ],
    },
    "hyderabad": {
        "label": "Hyderabad",
        "flag": "🇮🇳",
        "tier": "india",
        "country": "India",
        "cities": ["Hyderabad, India", "Secunderabad, India"],
    },
    "chennai": {
        "label": "Chennai",
        "flag": "🇮🇳",
        "tier": "india",
        "country": "India",
        "cities": ["Chennai, India"],
    },
    "ahmedabad": {
        "label": "Ahmedabad",
        "flag": "🇮🇳",
        "tier": "india",
        "country": "India",
        "cities": ["Ahmedabad, India", "Gandhinagar, India"],
    },
    "kolkata": {
        "label": "Kolkata",
        "flag": "🇮🇳",
        "tier": "india",
        "country": "India",
        "cities": ["Kolkata, India", "Howrah, India"],
    },
}

TIER_LABELS = {
    "tier1_english": "Top-Tier English Markets",
    "india": "India - Top Metros",
}


def get_region(key: str) -> dict:
    """Return the region dict for a key, or raise KeyError."""
    return REGIONS[key]


def get_locations(key: str) -> list:
    """Return the list of city search locations for a region key."""
    return list(REGIONS[key]["cities"])


def list_regions_grouped() -> dict:
    """Return regions grouped by tier, for UI rendering.

    Shape: { tier_key: {"label": str, "regions": [ {key, label, flag, country, city_count} ]}}
    """
    grouped = {}
    for key, meta in REGIONS.items():
        tier = meta["tier"]
        grouped.setdefault(tier, {"label": TIER_LABELS.get(tier, tier), "regions": []})
        grouped[tier]["regions"].append({
            "key": key,
            "label": meta["label"],
            "flag": meta["flag"],
            "country": meta["country"],
            "city_count": len(meta["cities"]),
        })
    return grouped

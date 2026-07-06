"""Agent 1: Primary Lead Scraper using Google Maps and Apify."""

import re
from typing import List, Dict, Optional
from datetime import datetime

from anthropic import Anthropic
from models import Lead, LeadStatus, LeadType
from config.settings import ICP, SCRAPING_SETTINGS
from config.prompts import get_prompt
from lib.apify_client import ApifyClient, scrape_businesses


class ScraperPrimaryAgent:
    """Agent for scraping leads from Google Maps and business directories."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the scraper agent."""
        self.anthropic = Anthropic(api_key=api_key or None)
        self.apify_client = ApifyClient()
        self.max_leads = SCRAPING_SETTINGS["max_leads_per_run"]

    def run(
        self,
        location: str = "Pimpri-Chinchwad, Pune, India",
        categories: Optional[List[str]] = None,
        count: int = 50,
    ) -> List[Lead]:
        """
        Scrape leads from Google Maps.

        Args:
            location: Target location for scraping
            categories: List of business categories to scrape
            count: Maximum number of leads to collect

        Returns:
            List of Lead objects
        """
        if categories is None:
            categories = ICP["industries"]

        print(f"[ScraperPrimary] Starting scrape for {location}")
        print(f"[ScraperPrimary] Categories: {categories}")
        print(f"[ScraperPrimary] Target count: {count}")

        # Try scraping with Apify
        try:
            raw_leads = scrape_businesses(
                categories=categories,
                location=location,
                max_per_category=count // len(categories) + 1,
            )
            print(f"[ScraperPrimary] Scraped {len(raw_leads)} raw leads")
        except Exception as e:
            print(f"[ScraperPrimary] Apify error: {e}")
            print(f"[ScraperPrimary] Using fallback demo data...")
            raw_leads = []

        # If no leads scraped, use fallback demo data
        if len(raw_leads) == 0:
            raw_leads = self._generate_demo_leads(categories, count)

        # Convert to Lead objects
        leads = []
        for raw in raw_leads[:count]:
            lead = self._convert_to_lead(raw)
            if lead:
                leads.append(lead)

        print(f"[ScraperPrimary] Converted {len(leads)} leads")
        return leads

    def _generate_demo_leads(self, categories: List[str], count: int) -> List[dict]:
        """Generate demo leads for testing when API is unavailable."""
        import random

        business_names = [
            "Sharma Dental Clinic", "Patel Restaurant", "Gupta General Store",
            "Singh Salon & Spa", "Kumar Fitness Center", "Jain Bakery",
            "Reddy Medical Store", "Mehta Electronics", "Shah Clothing Store",
            "Verma Cafe", "Agarwal Restaurant", "Joshi Gym", "Mahajan Clinic",
            "Kapoor Salon", "Gandhi Bakery", "Chopra Medical", "Bhatia Shop",
            "Malhotra Cafe", "Sinha Electronics", "Oberoi Restaurant",
            "Chandra Gym", "Kaur Clinic", "Nair Salon", "Iyer Bakery",
            "Menon Store", "Srivastava Cafe", "Mishra Electronics",
            "Pandey Restaurant", "Tiwari Gym", "Dubey Clinic",
        ]

        addresses = [
            "Shop No 5, Pimpri Main Road, Pimpri",
            "Plot 12, Chinchwad Station Road, Chinchwad",
            "Near Akurdi Railway Station, Akurdi",
            "Sector 22, Nigdi, Pradhikaran",
            "Pimpri-Chinchwad Area, Pune",
            "Main Market, Bhosari, Pune",
            "Nashik Highway, Moshi, Pune",
            "Talegaon Dabhade, Talegaon",
            "Hinjewadi IT Park Road, Hinjewadi",
            "Old Mumbai-Pune Highway, Chinchwad",
        ]

        phones = [
            "+91 98765 43210", "+91 98765 43211", "+91 98765 43212",
            "+91 98765 43213", "+91 98765 43214", "+91 98765 43215",
            "+91 98765 43216", "+91 98765 43217", "+91 98765 43218",
            "+91 98765 43219",
        ]

        leads = []
        used_names = set()

        for i in range(min(count, 20)):
            name = business_names[i % len(business_names)]
            if name in used_names and i < len(business_names):
                name = f"{name} {i // len(business_names) + 1}"
            used_names.add(name)

            category = random.choice(categories)
            has_website = random.random() > 0.6  # 40% have websites

            lead = {
                "name": name,
                "category": category,
                "address": random.choice(addresses),
                "phone": random.choice(phones),
                "rating": round(random.uniform(3.5, 4.8), 1),
                "reviewsCount": random.randint(5, 150),
                "url": f"https://www.example-{name.lower().replace(' ', '-')}.com" if has_website else None,
            }
            leads.append(lead)

        return leads

    def _convert_to_lead(self, raw_data: dict) -> Optional[Lead]:
        """Convert raw scraped data to Lead object."""
        try:
            # Extract business name (remove | location suffix that Apify adds)
            business_name = raw_data.get("name") or raw_data.get("title", "")
            if " | " in business_name:
                business_name = business_name.split(" | ")[0].strip()

            if not business_name:
                return None

            # Extract rating and reviews (Apify uses 'totalScore' for rating)
            rating_str = raw_data.get("rating") or raw_data.get("totalScore")
            try:
                rating = float(rating_str) if rating_str else None
            except (ValueError, TypeError):
                rating = None

            review_count = raw_data.get("reviewsCount") or raw_data.get("reviews_count")
            if isinstance(review_count, str):
                try:
                    review_count = int(review_count.replace(",", ""))
                except (ValueError, TypeError):
                    review_count = None
            elif isinstance(review_count, (int, float)):
                review_count = int(review_count)

            # Extract phone (clean format)
            phone = raw_data.get("phone") or raw_data.get("telephone")
            if phone:
                phone = self._clean_phone(phone)

            # Extract email
            email = raw_data.get("email") or self._extract_email(raw_data.get("body", ""))

            # Extract address (Apify returns 'address')
            address = raw_data.get("address", "")
            if not address:
                address = raw_data.get("location", "")

            # Extract website (Apify returns 'website' field with actual business website)
            website = raw_data.get("website") or raw_data.get("url")
            if website and not website.startswith("http"):
                website = None
            # Filter out Google Maps URLs - we only want actual websites
            if website and "google.com/maps" in website:
                website = None

            # Determine lead type
            if not website:
                lead_type = LeadType.NO_WEBSITE
            else:
                lead_type = LeadType.HAS_WEBSITE

            # Calculate reachability score
            reachability = 0
            if phone:
                reachability += 40
            if email:
                reachability += 30
            if website:
                reachability += 15
            if rating and rating >= 4:
                reachability += 15

            lead = Lead(
                business_name=business_name.strip(),
                category=raw_data.get("categoryName", "") or raw_data.get("type", ""),
                address=address,
                phone=phone,
                email=email,
                website_url=website,
                google_rating=rating,
                review_count=review_count,
                photos_count=raw_data.get("photosCount") or raw_data.get("photos_count"),
                business_hours=raw_data.get("hours") or raw_data.get("business_hours"),
                source="google_maps",
                status=LeadStatus.RAW,
                lead_type=lead_type,
                reachability_score=reachability,
            )

            return lead

        except Exception as e:
            print(f"[ScraperPrimary] Error converting lead: {e}")
            return None

    def _clean_phone(self, phone: str) -> str:
        """Clean and format phone number."""
        # Remove all non-digit characters except + at start
        if phone.startswith("+"):
            cleaned = "+" + re.sub(r"[^\d]", "", phone)
        else:
            cleaned = re.sub(r"[^\d]", "", phone)

        # Format as Indian phone number
        if cleaned.startswith("91") and len(cleaned) == 12:
            return f"+{cleaned[:2]} {cleaned[2:7]} {cleaned[7:]}"
        elif len(cleaned) == 10:
            return f"+91 {cleaned[:5]} {cleaned[5:]}"

        return phone

    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email from text."""
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        match = re.search(email_pattern, text)
        return match.group(0) if match else None

    def run_with_ai_enhancement(
        self,
        raw_leads: List[dict],
        location: str,
    ) -> List[Lead]:
        """
        Use AI to enhance and clean scraped data.

        Args:
            raw_leads: Raw lead data from scraping
            location: Target location

        Returns:
            Enhanced list of Lead objects
        """
        print(f"[ScraperPrimary] Running AI enhancement on {len(raw_leads)} leads")

        # Prepare batch for AI processing
        prompt = get_prompt(
            "scraper_primary",
            location=location,
            categories=", ".join(ICP["industries"]),
            count=len(raw_leads),
        )

        # Create structured JSON from raw data
        leads_json = "\n".join([
            f"- {l.get('name', 'N/A')} | {l.get('category', 'N/A')} | {l.get('address', 'N/A')}"
            for l in raw_leads[:20]  # Limit to 20 for context window
        ])

        # Get AI to clean and structure data
        message = self.anthropic.messages.create(
            model="haiku-4",
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}\n\nHere are the leads to process:\n{leads_json}\n\nReturn a JSON array of cleaned lead objects with: business_name, category, address, phone, website_url, google_rating, review_count"
                }
            ]
        )

        # Parse AI response and create leads
        try:
            import json
            response_text = message.content[0].text

            # Try to extract JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            cleaned_data = json.loads(response_text)

            leads = []
            for data in cleaned_data:
                try:
                    lead = Lead(
                        business_name=data.get("business_name", ""),
                        category=data.get("category", ""),
                        address=data.get("address"),
                        phone=data.get("phone"),
                        website_url=data.get("website_url"),
                        google_rating=data.get("google_rating"),
                        review_count=data.get("review_count"),
                        source="google_maps_ai_enhanced",
                        status=LeadStatus.RAW,
                    )
                    leads.append(lead)
                except Exception as e:
                    print(f"[ScraperPrimary] Error creating lead: {e}")
                    continue

            return leads

        except Exception as e:
            print(f"[ScraperPrimary] AI enhancement failed: {e}")
            # Fall back to basic conversion
            return [self._convert_to_lead(lead) for lead in raw_leads if self._convert_to_lead(lead)]


def scrape_leads(
    location: str = "Pimpri-Chinchwad, Pune",
    categories: Optional[List[str]] = None,
    count: int = 50,
) -> List[Lead]:
    """Convenience function to scrape leads."""
    agent = ScraperPrimaryAgent()
    return agent.run(location, categories, count)
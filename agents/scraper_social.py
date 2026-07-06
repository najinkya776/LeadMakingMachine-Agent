"""Agent 2: Social Media Scraper for Facebook and Instagram."""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass

from anthropic import Anthropic
from models import Lead, SocialHandles
from config.prompts import get_prompt
from lib.apify_client import ApifyClient


@dataclass
class SocialMediaData:
    """Social media data for a business."""
    facebook_url: Optional[str] = None
    instagram_handle: Optional[str] = None
    facebook_followers: Optional[int] = None
    instagram_followers: Optional[int] = None
    facebook_rating: Optional[float] = None
    posting_frequency: Optional[str] = None
    last_post_date: Optional[str] = None
    is_active: bool = True


class ScraperSocialAgent:
    """Agent for scraping social media presence of businesses."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the social scraper agent."""
        self.anthropic = Anthropic(api_key=api_key or None)
        self.apify_client = ApifyClient()

    def run(self, leads: List[Lead]) -> List[Lead]:
        """
        Scrape social media data for a list of leads.

        Args:
            leads: List of Lead objects to enhance with social data

        Returns:
            Updated list of Lead objects with social handles
        """
        print(f"[ScraperSocial] Starting social media scraping for {len(leads)} leads")

        # Extract business names for searching
        business_names = [lead.business_name for lead in leads if lead.business_name]

        # Scrape Facebook pages
        facebook_data = self._scrape_facebook(business_names)

        # Scrape Instagram
        instagram_data = self._scrape_instagram(business_names)

        # Update leads with social data
        for lead in leads:
            business_name = lead.business_name.lower()

            # Find matching Facebook data
            fb_key = next(
                (k for k in facebook_data.keys() if k.lower() in business_name or business_name in k.lower()),
                None
            )

            if fb_key:
                fb_info = facebook_data[fb_key]
                if lead.social_handles:
                    lead.social_handles.facebook = fb_info.facebook_url
                else:
                    lead.social_handles = SocialHandles(facebook=fb_info.facebook_url)

            # Find matching Instagram data
            ig_key = next(
                (k for k in instagram_data.keys() if k.lower() in business_name or business_name in k.lower()),
                None
            )

            if ig_key:
                ig_info = instagram_data[ig_key]
                if lead.social_handles:
                    lead.social_handles.instagram = ig_info.instagram_handle
                else:
                    lead.social_handles = SocialHandles(instagram=ig_info.instagram_handle)

            # Update lead type if only social exists
            if not lead.website_url and lead.social_handles:
                if lead.social_handles.facebook or lead.social_handles.instagram:
                    lead.lead_type = "social_only"

        print(f"[ScraperSocial] Completed social media scraping")
        return leads

    def _scrape_facebook(self, business_names: List[str]) -> Dict[str, SocialMediaData]:
        """Scrape Facebook pages for businesses."""
        print(f"[ScraperSocial] Scraping Facebook for {len(business_names)} businesses")

        try:
            results = self.apify_client.scrape_facebook_pages(
                business_names=business_names[:20],  # Limit for API
                max_items=50,
            )

            facebook_data = {}
            for result in results:
                name = result.get("name", "")
                if name:
                    facebook_data[name] = SocialMediaData(
                        facebook_url=result.get("url", ""),
                        facebook_followers=result.get("followers") or result.get("likes"),
                        facebook_rating=result.get("rating"),
                        posting_frequency="unknown",
                        last_post_date=result.get("lastPostDate"),
                    )

            return facebook_data

        except Exception as e:
            print(f"[ScraperSocial] Facebook scraping failed: {e}")
            return {}

    def _scrape_instagram(self, business_names: List[str]) -> Dict[str, SocialMediaData]:
        """Scrape Instagram profiles for businesses."""
        print(f"[ScraperSocial] Scraping Instagram for {len(business_names)} businesses")

        # Clean business names for Instagram handles
        usernames = [
            name.lower()
            .replace(" ", "")
            .replace("&", "")
            .replace(".", "")
            .replace("-", "")
            .replace("_", "")
            [:30]  # Instagram handle limit
            for name in business_names[:15]  # Limit for API
        ]

        try:
            results = self.apify_client.scrape_instagram(
                usernames=usernames,
                max_items=30,
            )

            instagram_data = {}
            for result in results:
                username = result.get("username", "")
                if username:
                    instagram_data[username] = SocialMediaData(
                        instagram_handle=f"@{username}",
                        instagram_followers=result.get("followers"),
                        posting_frequency=self._estimate_posting_frequency(result),
                        last_post_date=result.get("lastPostDate"),
                    )

            return instagram_data

        except Exception as e:
            print(f"[ScraperSocial] Instagram scraping failed: {e}")
            return {}

    def _estimate_posting_frequency(self, profile_data: dict) -> str:
        """Estimate posting frequency based on profile data."""
        posts = profile_data.get("posts", 0)

        if posts == 0:
            return "inactive"
        elif posts < 10:
            return "rare"
        elif posts < 50:
            return "occasional"
        elif posts < 200:
            return "regular"
        else:
            return "very_active"

    def run_with_ai_search(self, leads: List[Lead]) -> List[Lead]:
        """
        Use AI to find social media handles that might not be found by scraper.

        Args:
            leads: List of Lead objects

        Returns:
            Updated list of Lead objects
        """
        print(f"[ScraperSocial] Running AI-powered social media search")

        for lead in leads:
            if lead.social_handles and (lead.social_handles.facebook or lead.social_handles.instagram):
                continue  # Already has social data

            try:
                # Use AI to suggest social handles based on business name
                message = self.anthropic.messages.create(
                    model="haiku-4",
                    max_tokens=500,
                    messages=[
                        {
                            "role": "user",
                            "content": f"""Find social media profiles for this business.
                            Business: {lead.business_name}
                            Category: {lead.category}
                            Location: {lead.address or 'Unknown'}

                            Return JSON with:
                            - facebook_url: full URL or null
                            - instagram_handle: handle starting with @ or null
                            - confidence: high/medium/low based on how confident you are"""
                        }
                    ]
                )

                response = message.content[0].text

                # Parse response
                import json
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]

                social_data = json.loads(response)

                if not lead.social_handles:
                    lead.social_handles = SocialHandles()

                if social_data.get("facebook_url"):
                    lead.social_handles.facebook = social_data["facebook_url"]
                if social_data.get("instagram_handle"):
                    lead.social_handles.instagram = social_data["instagram_handle"]

            except Exception as e:
                print(f"[ScraperSocial] AI search failed for {lead.business_name}: {e}")
                continue

        return leads


def enrich_leads_with_social(leads: List[Lead]) -> List[Lead]:
    """Convenience function to enrich leads with social data."""
    agent = ScraperSocialAgent()
    return agent.run(leads)
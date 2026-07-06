"""Agent 8: Pitch Generator for businesses WITHOUT a website."""

from typing import Optional

from anthropic import Anthropic
from models import Lead, Report
from config.prompts import get_prompt


class PitchNoWebsiteAgent:
    """Agent for generating pitches for businesses without websites."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the pitch generator agent."""
        self.anthropic = Anthropic(api_key=api_key or None)

    def run(self, lead: Lead, social_analysis: Optional[dict] = None) -> str:
        """
        Generate a compelling pitch for a business without a website.

        Args:
            lead: Lead object (should not have website)
            social_analysis: Optional social media analysis

        Returns:
            Pitch content as markdown string
        """
        if lead.website_url:
            print(f"[PitchNoWebsite] Warning: {lead.business_name} has a website")

        print(f"[PitchNoWebsite] Generating pitch for {lead.business_name}")

        try:
            prompt = get_prompt(
                "pitch_no_website",
                business_name=lead.business_name,
                category=lead.category,
                address=lead.address or "Pimpri-Chinchwad, Pune",
                phone=lead.phone or "Unknown",
                rating=f"{lead.google_rating}★" if lead.google_rating else "N/A",
                review_count=str(lead.review_count) if lead.review_count else "N/A",
                social_handles=self._format_social(lead, social_analysis),
            )

            message = self.anthropic.messages.create(
                model="sonnet-4-6-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            pitch = message.content[0].text
            print(f"[PitchNoWebsite] Pitch generated ({len(pitch)} chars)")

            return pitch

        except Exception as e:
            print(f"[PitchNoWebsite] Pitch generation failed: {e}")
            return self._generate_fallback_pitch(lead)

    def _format_social(self, lead: Lead, social_analysis: Optional[dict]) -> str:
        """Format social media info for prompt."""
        if not lead.social_handles and not social_analysis:
            return "Not found on social media"

        parts = []
        if lead.social_handles:
            if lead.social_handles.facebook:
                parts.append(f"Facebook: {lead.social_handles.facebook}")
            if lead.social_handles.instagram:
                parts.append(f"Instagram: {lead.social_handles.instagram}")

        if not parts:
            return "Limited social media presence"

        return ", ".join(parts)

    def _generate_fallback_pitch(self, lead: Lead) -> str:
        """Generate basic pitch when AI fails."""
        category_impact = {
            "restaurant": "customers can find you on Google and food delivery apps",
            "salon": "customers can book appointments online and see your work",
            "clinic": "patients can find you and book appointments easily",
            "shop": "customers can see your products and find your location",
            "gym": "members can see class schedules and book sessions",
        }

        impact = category_impact.get(
            lead.category.lower() if lead.category else "",
            "customers can find you online and learn about your services"
        )

        return f"""# Website Pitch for {lead.business_name}

## Opening Hook

We noticed {lead.business_name} has {lead.review_count or 'some'} great reviews on Google.
Thank you for building a trusted local business!

## The Problem

In today's digital world, customers search online before visiting any business.
If they can't find you online, you're missing out on potential customers
who are actively looking for {lead.category or 'your services'}.

## The Opportunity

Imagine if every person searching for "{lead.category or 'your services'}" in
{lead.address or 'Pimpri-Chinchwad'} found your business first.

A professional website can help you:
- Get found on Google (SEO)
- Show your services/products 24/7
- Build trust with potential customers
- Accept bookings and inquiries online
- Stand out from competitors without websites

## The Impact

Based on your {lead.review_count or 'growing'} reviews and great location,
we estimate a website could help you reach 50-100 more customers monthly.

## Next Steps

1. Free consultation to understand your needs
2. Custom website design proposal within 24 hours
3. Affordable pricing tailored for small businesses

Would you be open to a quick 15-minute call to discuss how we can help
{lead.business_name} grow?
"""

    def generate_estimate(
        self,
        lead: Lead,
        audit: Optional[dict] = None,
    ) -> dict:
        """
        Generate pricing estimate based on business needs.

        Args:
            lead: Lead object
            audit: Optional audit data

        Returns:
            Dictionary with pricing estimate
        """
        pricing = {
            "basic": {"price": "₹15,000 - ₹25,000", "timeline": "2-3 weeks"},
            "standard": {"price": "₹30,000 - ₹50,000", "timeline": "4-6 weeks"},
            "premium": {"price": "₹60,000 - ₹1,50,000", "timeline": "6-8 weeks"},
        }

        # Determine recommended tier
        has_social = lead.social_handles and (
            lead.social_handles.facebook or lead.social_handles.instagram
        )
        has_reviews = lead.review_count and lead.review_count >= 10

        if has_social or has_reviews:
            recommended = "standard"
        else:
            recommended = "basic"

        return {
            "lead_id": lead.id,
            "business_name": lead.business_name,
            "pricing": pricing,
            "recommended_tier": recommended,
            "rationale": f"Based on {lead.category} business with "
                         f"{'good' if has_reviews else 'limited'} Google reviews "
                         f"and {'active' if has_social else 'minimal'} social presence.",
        }

    def generate_mockup_description(self, lead: Lead) -> str:
        """
        Generate a description of what the website could look like.

        Args:
            lead: Lead object

        Returns:
            Markdown description of proposed website
        """
        try:
            prompt = f"""Create a detailed description of a professional website for:
{lead.business_name} - {lead.category or 'Local Business'}
Location: {lead.address or 'Pimpri-Chinchwad, Pune'}

Describe what the website should include:
1. Homepage design and layout
2. Key pages (About, Services, Contact, Gallery)
3. Special features for this business type
4. Mobile-first considerations
5. Branding and color suggestions

Keep it concise but specific to this business."""

            message = self.anthropic.messages.create(
                model="haiku-4",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )

            return message.content[0].text

        except Exception as e:
            print(f"[PitchNoWebsite] Mockup description failed: {e}")
            return ""


def generate_no_website_pitch(lead: Lead, social_analysis: Optional[dict] = None) -> str:
    """Convenience function to generate pitch for no-website lead."""
    agent = PitchNoWebsiteAgent()
    return agent.run(lead, social_analysis)
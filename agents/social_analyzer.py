"""Agent 6: Social Media Analyzer - Analyze social media presence and gaps."""

from typing import Optional, Dict, List

from anthropic import Anthropic
from models import Lead, SocialHandles
from config.prompts import get_prompt


class SocialAnalyzerAgent:
    """Agent for analyzing social media presence and scoring digital gaps."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the social analyzer agent."""
        self.anthropic = Anthropic(api_key=api_key or None)

    def run(self, lead: Lead) -> Dict:
        """
        Analyze social media presence for a lead.

        Args:
            lead: Lead object with social handles

        Returns:
            Dictionary with social analysis results
        """
        print(f"[SocialAnalyzer] Analyzing social presence for {lead.business_name}")

        result = {
            "lead_id": lead.id,
            "business_name": lead.business_name,
            "social_score": 0,
            "platforms_analyzed": [],
            "activity_level": "unknown",
            "engagement_rate": 0,
            "gap_analysis": [],
            "recommendations": [],
            "missing_platforms": [],
        }

        if not lead.social_handles:
            result["social_score"] = 10  # Very low - no social presence
            result["gap_analysis"].append("No social media accounts found")
            result["missing_platforms"] = ["Facebook", "Instagram", "Google Business"]
            result["recommendations"].append("Create business pages on Facebook and Instagram")
            return result

        # Analyze Facebook
        if lead.social_handles.facebook:
            fb_analysis = self._analyze_facebook(lead)
            result["platforms_analyzed"].append("Facebook")
            result.update(fb_analysis)

        # Analyze Instagram
        if lead.social_handles.instagram:
            ig_analysis = self._analyze_instagram(lead)
            result["platforms_analyzed"].append("Instagram")
            result.update(ig_analysis)

        # Determine missing platforms
        platforms_found = result["platforms_analyzed"]
        all_platforms = ["Facebook", "Instagram", "Google Business", "Twitter", "LinkedIn"]

        for platform in all_platforms:
            platform_key = platform.lower().replace(" ", "_")
            if platform_key not in [p.lower().replace("_", " ") for p in platforms_found]:
                if platform.lower() not in [p.lower() for p in result["missing_platforms"]]:
                    result["missing_platforms"].append(platform)

        # Calculate overall social score
        result["social_score"] = self._calculate_social_score(result)

        # Generate AI recommendations
        result["recommendations"] = self._generate_recommendations(result, lead)

        print(f"[SocialAnalyzer] Social score: {result['social_score']}/100")
        return result

    def _analyze_facebook(self, lead: Lead) -> Dict:
        """Analyze Facebook presence."""
        # This would normally use actual data from scraping
        # For now, generate insights based on available data

        return {
            "has_facebook": True,
            "facebook_url": lead.social_handles.facebook,
            "facebook_followers": 0,  # Would come from scraper
            "facebook_activity": "unknown",
        }

    def _analyze_instagram(self, lead: Lead) -> Dict:
        """Analyze Instagram presence."""
        return {
            "has_instagram": True,
            "instagram_handle": lead.social_handles.instagram,
            "instagram_followers": 0,  # Would come from scraper
            "instagram_activity": "unknown",
        }

    def _calculate_social_score(self, analysis: Dict) -> int:
        """Calculate overall social media score."""
        score = 0

        # Base score for presence
        if analysis.get("has_facebook"):
            score += 30
        if analysis.get("has_instagram"):
            score += 30

        # Activity level bonus
        activity = analysis.get("activity_level", "unknown")
        activity_bonus = {
            "very_active": 20,
            "regular": 15,
            "occasional": 10,
            "rare": 5,
            "inactive": 0,
        }
        score += activity_bonus.get(activity, 0)

        # Engagement bonus
        score += min(analysis.get("engagement_rate", 0), 20)

        return min(100, score)

    def _generate_recommendations(self, analysis: Dict, lead: Lead) -> List[str]:
        """Generate social media recommendations using AI."""
        recommendations = []

        # Missing platforms
        missing = analysis.get("missing_platforms", [])
        if missing:
            recommendations.append(f"Create presence on: {', '.join(missing[:3])}")

        # Activity recommendations
        activity = analysis.get("activity_level", "unknown")
        if activity in ["inactive", "rare"]:
            recommendations.append("Post consistently - aim for 3-4 posts per week")

        # Engagement recommendations
        if analysis.get("engagement_rate", 0) < 5:
            recommendations.append("Engage with followers through comments and stories")

        # Use AI for personalized recommendations
        try:
            prompt = get_prompt(
                "social_analyzer",
                business_name=lead.business_name,
                facebook_url=lead.social_handles.facebook or "None",
                instagram_handle=lead.social_handles.instagram or "None",
            )

            context = f"""Current Analysis for {lead.business_name}:
- Social Score: {analysis['social_score']}/100
- Platforms: {', '.join(analysis['platforms_analyzed']) or 'None'}
- Missing: {', '.join(analysis['missing_platforms']) or 'None'}
- Activity: {analysis['activity_level']}
- Engagement Rate: {analysis['engagement_rate']}%

Provide 5 specific, actionable recommendations to improve social media presence."""

            message = self.anthropic.messages.create(
                model="haiku-4",
                max_tokens=800,
                messages=[{"role": "user", "content": context}]
            )

            recommendations.append(message.content[0].text)

        except Exception as e:
            print(f"[SocialAnalyzer] AI recommendations failed: {e}")

        return recommendations

    def analyze_competitor_social(self, business_name: str, category: str) -> Dict:
        """
        Analyze social media presence of competitors.

        Args:
            business_name: Name of the business
            category: Business category

        Returns:
            Dictionary with competitor insights
        """
        try:
            prompt = f"""Research social media best practices and benchmarks for {category} businesses in India.

Consider:
- Which platforms are most effective
- Posting frequency benchmarks
- Content types that perform well
- Engagement rate benchmarks for the industry

Provide recommendations specific to a {category} business targeting customers in Pimpri-Chinchwad/Pune area."""

            message = self.anthropic.messages.create(
                model="haiku-4",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )

            return {
                "category": category,
                "competitor_insights": message.content[0].text,
            }

        except Exception as e:
            print(f"[SocialAnalyzer] Competitor analysis failed: {e}")
            return {}

    def calculate_gap_score(self, lead: Lead) -> int:
        """
        Calculate the digital gap - difference between current and optimal.

        Args:
            lead: Lead object

        Returns:
            Gap score 0-100 (higher = bigger opportunity)
        """
        gap = 0

        # Website gap
        if not lead.website_url:
            gap += 30

        # Social media gap
        if not lead.social_handles or not (lead.social_handles.facebook or lead.social_handles.instagram):
            gap += 25

        # Google presence gap (based on reviews)
        if not lead.review_count or lead.review_count < 10:
            gap += 20

        # Contact info gap
        if not lead.phone or not lead.email:
            gap += 15

        # Business info gap
        if not lead.business_hours:
            gap += 10

        return min(100, gap)


def analyze_social(lead: Lead) -> Dict:
    """Convenience function to analyze social media presence."""
    agent = SocialAnalyzerAgent()
    return agent.run(lead)
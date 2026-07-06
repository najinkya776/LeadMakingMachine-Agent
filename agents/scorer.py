"""Agent 7: Lead Scoring Agent - Combine all data and score opportunity."""

from typing import Optional, Dict, List
from dataclasses import dataclass

from anthropic import Anthropic
from models import Lead, Audit, LeadStatus
from config.settings import SCORING, ICP


@dataclass
class LeadScore:
    """Complete score breakdown for a lead."""
    total_score: int
    classification: str  # high, medium, low

    # Component scores
    audit_score: int
    seo_score: int
    social_score: int
    business_score: int
    lead_type_bonus: int

    # Score weights
    audit_weight: float = 0.30
    seo_weight: float = 0.20
    social_weight: float = 0.15
    business_weight: float = 0.20
    lead_type_weight: float = 0.15

    # Metadata
    scoring_factors: List[str] = None

    def __post_init__(self):
        if self.scoring_factors is None:
            self.scoring_factors = []


class ScorerAgent:
    """Agent for calculating lead opportunity scores."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the scorer agent."""
        self.anthropic = Anthropic(api_key=api_key or None)
        self.scoring_config = SCORING

    def run(
        self,
        lead: Lead,
        audit: Optional[Audit] = None,
        social_analysis: Optional[Dict] = None,
    ) -> LeadScore:
        """
        Calculate opportunity score for a lead.

        Args:
            lead: Lead object
            audit: Audit object (optional)
            social_analysis: Social analysis dictionary (optional)

        Returns:
            LeadScore with score breakdown
        """
        print(f"[Scorer] Scoring lead: {lead.business_name}")

        # Calculate component scores
        audit_score = self._score_audit(audit)
        seo_score = self._score_seo(audit)
        social_score = self._score_social(social_analysis)
        business_score = self._score_business(lead)
        lead_type_bonus = self._score_lead_type(lead, audit)

        # Calculate weighted total
        total = (
            audit_score * 0.30 +
            seo_score * 0.20 +
            social_score * 0.15 +
            business_score * 0.20 +
            lead_type_bonus * 0.15
        )

        total_score = min(100, max(0, int(total)))

        # Determine classification
        if total_score >= self.scoring_config["high"]:
            classification = "high"
        elif total_score >= self.scoring_config["medium"]:
            classification = "medium"
        else:
            classification = "low"

        # Collect scoring factors
        factors = self._collect_factors(
            lead, audit, social_analysis,
            audit_score, seo_score, social_score,
            business_score, lead_type_bonus
        )

        score = LeadScore(
            total_score=total_score,
            classification=classification,
            audit_score=audit_score,
            seo_score=seo_score,
            social_score=social_score,
            business_score=business_score,
            lead_type_bonus=lead_type_bonus,
            scoring_factors=factors,
        )

        print(f"[Scorer] Score: {total_score} ({classification})")
        return score

    def _score_audit(self, audit: Optional[Audit]) -> int:
        """Score audit results (0-100)."""
        if not audit:
            return 30  # Default for no audit

        score = 0

        # Page speed contribution
        if audit.page_speed_score is not None:
            score += audit.page_speed_score * 0.4

        # Mobile score contribution
        if audit.mobile_score is not None:
            score += audit.mobile_score * 0.3

        # Design quality
        design_map = {
            "very_poor": 10,
            "poor": 25,
            "average": 50,
            "good": 75,
            "excellent": 100,
        }
        design_score = design_map.get(audit.design_quality, 40) if audit.design_quality else 40
        score += design_score * 0.3

        return min(100, int(score))

    def _score_seo(self, audit: Optional[Audit]) -> int:
        """Score SEO results (0-100)."""
        if not audit:
            return 30

        score = 50  # Base

        # HTTPS bonus
        if audit.https_enabled:
            score += 10

        # SEO score from audit
        if audit.seo_score is not None:
            score = audit.seo_score

        # Sitemap bonus
        if audit.has_sitemap:
            score += 5

        # Robots.txt bonus
        if audit.has_robots_txt:
            score += 5

        # Meta tags
        if audit.meta_tags_complete:
            score += 5

        # Broken links penalty
        score -= min(audit.broken_links_count * 2, 20)

        return min(100, max(0, score))

    def _score_social(self, social_analysis: Optional[Dict]) -> int:
        """Score social media presence (0-100)."""
        if not social_analysis:
            return 25  # Default for no social data

        return social_analysis.get("social_score", 25)

    def _score_business(self, lead: Lead) -> int:
        """Score business signals (0-100)."""
        score = 40  # Base

        # Google rating
        if lead.google_rating is not None:
            rating_score = lead.google_rating * 10  # 5 stars = 50 points
            score += rating_score

        # Review count
        if lead.review_count is not None:
            if lead.review_count >= 50:
                score += 20
            elif lead.review_count >= 20:
                score += 15
            elif lead.review_count >= 10:
                score += 10
            elif lead.review_count >= 5:
                score += 5

        # Reachability
        if lead.reachability_score is not None:
            score += min(lead.reachability_score * 0.3, 15)

        return min(100, score)

    def _score_lead_type(self, lead: Lead, audit: Optional[Audit]) -> int:
        """Score based on lead type and opportunity."""
        score = 30  # Base

        # No-website leads are highest opportunity
        if not lead.website_url:
            score += 40

            # Social-only adds more opportunity
            if lead.social_handles and (lead.social_handles.facebook or lead.social_handles.instagram):
                score += 10

        # Has website but poor audit = good opportunity
        elif audit:
            if audit.design_quality in ["poor", "very_poor"]:
                score += 30
            elif audit.design_quality == "average":
                score += 20

            # Old tech stack = opportunity
            if audit.is_wordpress and audit.audit_data:
                score += 10

        return min(100, score)

    def _collect_factors(
        self,
        lead: Lead,
        audit: Optional[Audit],
        social: Optional[Dict],
        audit_score: int,
        seo_score: int,
        social_score: int,
        business_score: int,
        lead_type_score: int,
    ) -> List[str]:
        """Collect factors that contributed to the score."""
        factors = []

        # Positive factors
        if audit and audit.page_speed_score and audit.page_speed_score >= 80:
            factors.append("Fast page load speed")
        if audit and audit.https_enabled:
            factors.append("Secure HTTPS")
        if lead.google_rating and lead.google_rating >= 4:
            factors.append(f"Strong Google rating ({lead.google_rating}★)")
        if lead.review_count and lead.review_count >= 10:
            factors.append(f"Good review volume ({lead.review_count})")
        if not lead.website_url:
            factors.append("No website - highest opportunity")
        if audit and audit.design_quality in ["poor", "very_poor"]:
            factors.append("Poor design - clear improvement needed")

        # Negative factors
        if audit and audit.broken_links_count > 5:
            factors.append(f"Many broken links ({audit.broken_links_count})")
        if not lead.phone:
            factors.append("No phone number")
        if not lead.email:
            factors.append("No email address")

        return factors[:10]  # Limit to top 10

    def run_batch(
        self,
        leads: List[Lead],
        audits: Dict[str, Audit],
        social_analyses: Dict[str, Dict],
    ) -> List[LeadScore]:
        """
        Score multiple leads.

        Args:
            leads: List of leads
            audits: Dict mapping lead_id to Audit
            social_analyses: Dict mapping lead_id to social analysis

        Returns:
            List of LeadScore objects
        """
        scores = []

        for lead in leads:
            audit = audits.get(lead.id)
            social = social_analyses.get(lead.id)
            score = self.run(lead, audit, social)
            scores.append(score)

        return scores

    def run_with_ai_recalibration(
        self,
        lead: Lead,
        base_score: LeadScore,
        audits: List[Audit],
        similar_leads: List[Lead],
    ) -> LeadScore:
        """
        Use AI to recalibrate score based on context and similar leads.

        Args:
            lead: Lead object
            base_score: Initial score from rule-based calculation
            audits: List of audit objects for similar leads
            similar_leads: List of similar leads with known outcomes

        Returns:
            Recalibrated LeadScore
        """
        try:
            context = f"""Lead: {lead.business_name}
Category: {lead.category}
Location: {lead.address}
Has Website: {bool(lead.website_url)}

Base Score: {base_score.total_score}/100
- Audit Score: {base_score.audit_score}
- SEO Score: {base_score.seo_score}
- Social Score: {base_score.social_score}
- Business Score: {base_score.business_score}
- Lead Type Bonus: {base_score.lead_type_bonus}

Classification: {base_score.classification}

Scoring Factors: {', '.join(base_score.scoring_factors[:5])}

Analyze and provide a refined score (0-100) with explanation.
Consider market conditions, local competition, and seasonal factors.
Return just the numeric score and a 1-line explanation."""

            message = self.anthropic.messages.create(
                model="haiku-4",
                max_tokens=300,
                messages=[{"role": "user", "content": context}]
            )

            response = message.content[0].text

            # Try to extract score from response
            import re
            match = re.search(r"(\d+)", response)
            if match:
                refined_score = int(match.group(1))
                base_score.total_score = refined_score

                # Recalculate classification
                if refined_score >= self.scoring_config["high"]:
                    base_score.classification = "high"
                elif refined_score >= self.scoring_config["medium"]:
                    base_score.classification = "medium"
                else:
                    base_score.classification = "low"

        except Exception as e:
            print(f"[Scorer] AI recalibration failed: {e}")

        return base_score


def calculate_lead_score(
    lead: Lead,
    audit: Optional[Audit] = None,
    social_analysis: Optional[Dict] = None,
) -> LeadScore:
    """Convenience function to calculate lead score."""
    agent = ScorerAgent()
    return agent.run(lead, audit, social_analysis)
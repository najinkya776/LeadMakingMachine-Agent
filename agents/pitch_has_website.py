"""Agent 9: Pitch Generator for businesses WITH an existing website."""

from typing import Optional

from anthropic import Anthropic
from models import Lead, Audit
from config.prompts import get_prompt


class PitchHasWebsiteAgent:
    """Agent for generating improvement pitches for businesses with websites."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the pitch generator agent."""
        self.anthropic = Anthropic(api_key=api_key or None)

    def run(self, lead: Lead, audit: Optional[Audit] = None) -> str:
        """
        Generate a pitch for improving an existing website.

        Args:
            lead: Lead object with website
            audit: Audit object with website analysis (can be None)

        Returns:
            Pitch content as markdown string
        """
        if not lead.website_url:
            print(f"[PitchHasWebsite] Error: {lead.business_name} has no website")
            return "Error: No website to improve"

        print(f"[PitchHasWebsite] Generating improvement pitch for {lead.business_name}")

        # Use defaults if audit is None
        if audit is None:
            audit_data = {
                'page_speed': 'N/A',
                'mobile_score': 'N/A',
                'seo_score': 'N/A',
                'broken_links': '0',
                'tech_stack': 'Unknown',
                'design_quality': 'Unknown',
            }
        else:
            audit_data = {
                'page_speed': str(audit.page_speed_score) if audit.page_speed_score else "N/A",
                'mobile_score': str(audit.mobile_score) if audit.mobile_score else "N/A",
                'seo_score': str(audit.seo_score) if audit.seo_score else "N/A",
                'broken_links': str(audit.broken_links_count) if audit.broken_links_count else "0",
                'tech_stack': audit.tech_stack or "Unknown",
                'design_quality': str(audit.design_quality) if audit.design_quality else "Unknown",
            }

        try:
            prompt = f"""Generate a pitch for improving the website of {lead.business_name}.

Website: {lead.website_url}
Category: {lead.category or 'Local Business'}

Audit Results:
- Page Speed: {audit_data['page_speed']}/100
- Mobile Score: {audit_data['mobile_score']}/100
- SEO Score: {audit_data['seo_score']}/100
- Broken Links: {audit_data['broken_links']}
- Tech Stack: {audit_data['tech_stack']}
- Design Quality: {audit_data['design_quality']}

Write a professional pitch that:
1. Opens with a genuine compliment (find something good)
2. Identifies 3-5 specific improvement opportunities
3. Explains the business impact of each improvement
4. Provides competitive analysis
5. Offers a specific proposal with pricing estimate

Keep it under 600 words. Format as markdown."""

            message = self.anthropic.messages.create(
                model="sonnet-4-6-20250514",
                max_tokens=2500,
                messages=[{"role": "user", "content": prompt}]
            )

            pitch = message.content[0].text
            print(f"[PitchHasWebsite] Pitch generated ({len(pitch)} chars)")

            return pitch

        except Exception as e:
            print(f"[PitchHasWebsite] Pitch generation failed: {e}")
            return self._generate_fallback_pitch(lead, audit)

    def _generate_fallback_pitch(self, lead: Lead, audit: Optional[Audit] = None) -> str:
        """Generate basic improvement pitch when AI fails."""
        issues = []

        if audit:
            if audit.page_speed_score and audit.page_speed_score < 60:
                issues.append("slow page load times")
            if audit.mobile_score and audit.mobile_score < 70:
                issues.append("poor mobile experience")
            if audit.broken_links_count and audit.broken_links_count > 0:
                issues.append(f"{audit.broken_links_count} broken links")
            if audit.design_quality in ["poor", "very_poor"]:
                issues.append("outdated design")
            if not audit.https_enabled:
                issues.append("missing SSL certificate")

        if not issues:
            issues = ["general website improvements"]

        key_findings = []
        if audit:
            key_findings.append(f"Page Speed: {audit.page_speed_score or 'Needs improvement'}/100")
            key_findings.append(f"Mobile: {audit.mobile_score or 'Needs improvement'}/100")
            key_findings.append(f"SEO: {audit.seo_score or 'Needs improvement'}/100")
            key_findings.append(f"Tech: {audit.tech_stack or 'Could be updated'}")

        return f"""# Website Improvement Pitch for {lead.business_name}

## What We Liked

Thank you for having an online presence for {lead.business_name}.
Your website at {lead.website_url} is a great starting point.

## Opportunities for Improvement

Based on our analysis, we identified several areas for improvement:

{chr(10).join(f"- {issue}" for issue in issues) if issues else "- General modernization needed"}

Key findings:
{chr(10).join(f"- {k}" for k in key_findings) if key_findings else "- Website audit completed"}

## Business Impact

By improving these areas, you can expect:
- Higher Google rankings (more customers find you)
- Better user experience (customers stay longer)
- More mobile conversions (customers can easily contact you)
- Increased trust through modern design

## Proposed Solution

Based on your business type ({lead.category}) and current website state,
we recommend our Standard Package which includes:

✓ Modern, responsive design
✓ Page speed optimization
✓ Mobile-friendly experience
✓ SEO improvements
✓ Contact form and WhatsApp integration
✓ 3 months of support

## Investment Estimate

- Basic Package: ₹15,000 - ₹25,000
- Standard Package: ₹30,000 - ₹50,000 (Recommended)
- Premium Package: ₹60,000 - ₹1,50,000

## Next Steps

1. Free website audit consultation
2. Detailed proposal with specific improvements
3. Timeline and payment schedule

Ready to improve your online presence? Let's schedule a quick call!
"""

    def generate_competitive_analysis(
        self,
        lead: Lead,
        audit: Audit,
    ) -> str:
        """
        Generate competitive analysis for the business's website.

        Args:
            lead: Lead object
            audit: Audit object

        Returns:
            Competitive analysis as markdown
        """
        try:
            prompt = f"""Create a competitive analysis for {lead.business_name} website:
URL: {lead.website_url}
Category: {lead.category}

Current website analysis:
- Tech Stack: {audit.tech_stack or 'Unknown'}
- CMS: {audit.cms_type or 'Unknown'}
- Design Quality: {audit.design_quality or 'Unknown'}
- Page Speed: {audit.page_speed_score or 'N/A'}/100

Compare against:
1. Top 3 competitors in {lead.category} in Pune/Pimpri-Chinchwad
2. Industry best practices for websites
3. Modern design trends for small businesses

Provide:
- What's working well (1-2 items)
- What competitors do better (2-3 items)
- Key differentiators to recommend
- Specific improvements for competitive advantage"""

            message = self.anthropic.messages.create(
                model="sonnet-4-6-20250514",
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}]
            )

            return message.content[0].text

        except Exception as e:
            print(f"[PitchHasWebsite] Competitive analysis failed: {e}")
            return ""

    def generate_seo_recommendations(self, audit: Audit) -> str:
        """
        Generate specific SEO improvement recommendations.

        Args:
            audit: Audit object with SEO data

        Returns:
            SEO recommendations as markdown
        """
        recommendations = []

        # HTTPs recommendation
        if not audit.https_enabled:
            recommendations.append("- Install SSL certificate (HTTPS) - critical for SEO")

        # Meta tags
        if not audit.meta_tags_complete:
            recommendations.append("- Add proper meta title and description to all pages")

        # Sitemap
        if not audit.has_sitemap:
            recommendations.append("- Create and submit XML sitemap to Google Search Console")

        # Robots.txt
        if not audit.has_robots_txt:
            recommendations.append("- Create robots.txt file to guide search engines")

        # Broken links
        if audit.broken_links_count > 0:
            recommendations.append(f"- Fix {audit.broken_links_count} broken links to improve user experience")

        # Mobile
        if audit.mobile_score and audit.mobile_score < 80:
            recommendations.append("- Optimize for mobile-first indexing")

        return "\n".join(recommendations) if recommendations else "- Website appears well-optimized for basic SEO"

    def calculate_roi_estimate(self, lead: Lead, audit: Audit) -> dict:
        """
        Calculate estimated ROI from website improvements.

        Args:
            lead: Lead object
            audit: Audit object

        Returns:
            Dictionary with ROI estimate
        """
        # Base estimates
        monthly_customers = lead.review_count * 2 if lead.review_count else 20
        avg_order_value = 500  # ₹500 average for local businesses

        # Improvement factors
        seo_improvement = (audit.seo_score or 40) / 100
        speed_improvement = (audit.page_speed_score or 50) / 100

        # Estimated increase
        current_monthly_revenue = monthly_customers * avg_order_value
        estimated_increase_pct = (seo_improvement * 30) + (speed_improvement * 20)
        estimated_monthly_increase = current_monthly_revenue * (estimated_increase_pct / 100)

        # Investment estimates
        basic_investment = 20000
        standard_investment = 40000
        premium_investment = 100000

        return {
            "current_monthly_revenue": current_monthly_revenue,
            "estimated_monthly_increase": int(estimated_monthly_increase),
            "annual_increase": int(estimated_monthly_increase * 12),
            "basic_roi_months": int(basic_investment / estimated_monthly_increase) if estimated_monthly_increase > 0 else 12,
            "standard_roi_months": int(standard_investment / estimated_monthly_increase) if estimated_monthly_increase > 0 else 12,
            "premium_roi_months": int(premium_investment / estimated_monthly_increase) if estimated_monthly_increase > 0 else 12,
        }


def generate_website_pitch(lead: Lead, audit: Audit) -> str:
    """Convenience function to generate pitch for website."""
    agent = PitchHasWebsiteAgent()
    return agent.run(lead, audit)
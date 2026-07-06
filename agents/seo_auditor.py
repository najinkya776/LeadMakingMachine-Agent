"""Agent 5: SEO Auditor - Deep SEO analysis using Lighthouse."""

from typing import Optional, Dict, List, Tuple

from anthropic import Anthropic
from models import Audit
from lib.lighthouse import LighthouseAnalyzer, analyze_website_sync


class SEOAuditorAgent:
    """Agent for detailed SEO analysis and recommendations."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the SEO auditor agent."""
        self.anthropic = Anthropic(api_key=api_key or None)

    def run(self, audit: Audit, url: Optional[str] = None) -> Audit:
        """
        Perform SEO analysis on an existing audit.

        Args:
            audit: Existing audit object (may have partial data)
            url: Website URL (uses audit.website_url if not provided)

        Returns:
            Updated audit with SEO scores and recommendations
        """
        target_url = url or audit.website_url

        if not target_url:
            print("[SEO] No URL provided for SEO analysis")
            return audit

        print(f"[SEO] Starting SEO analysis for {target_url}")

        try:
            # Run Lighthouse for detailed SEO metrics
            lh_result = analyze_website_sync(target_url)

            if lh_result:
                audit.seo_score = lh_result.seo_score

                # Add detailed SEO audit data
                audit.audit_data = audit.audit_data or {}
                audit.audit_data["seo_details"] = {
                    "lighthouse_seo_score": lh_result.seo_score,
                    "accessibility_score": lh_result.accessibility_score,
                    "best_practices_score": lh_result.best_practices_score,
                    "core_web_vitals": {
                        "lcp": lh_result.lcp,
                        "fid": lh_result.fid,
                        "cls": lh_result.cls,
                    },
                    "performance_metrics": {
                        "fcp": lh_result.first_contentful_paint,
                        "speed_index": lh_result.speed_index,
                        "tti": lh_result.time_to_interactive,
                        "tbt": lh_result.total_blocking_time,
                    },
                    "critical_issues": lh_result.critical_issues,
                    "warnings": lh_result.warnings,
                }

            # Generate recommendations with AI
            audit = self._generate_seo_recommendations(audit)

            print(f"[SEO] SEO analysis complete - Score: {audit.seo_score}")

        except Exception as e:
            print(f"[SEO] SEO analysis failed: {e}")

        return audit

    def _generate_seo_recommendations(self, audit: Audit) -> Audit:
        """Generate SEO recommendations using AI."""
        if not audit.audit_data:
            return audit

        seo_data = audit.audit_data.get("seo_details", {})

        try:
            prompt = f"""Analyze these SEO metrics and provide actionable recommendations:

Core Web Vitals:
- LCP (Largest Contentful Paint): {seo_data.get('core_web_vitals', {}).get('lcp', 'N/A')}s (target: <2.5s)
- FID (First Input Delay): {seo_data.get('core_web_vitals', {}).get('fid', 'N/A')}ms (target: <100ms)
- CLS (Cumulative Layout Shift): {seo_data.get('core_web_vitals', {}).get('cls', 'N/A')} (target: <0.1)

Performance:
- First Contentful Paint: {seo_data.get('performance_metrics', {}).get('fcp', 'N/A')}s
- Speed Index: {seo_data.get('performance_metrics', {}).get('speed_index', 'N/A')}s
- Time to Interactive: {seo_data.get('performance_metrics', {}).get('tti', 'N/A')}s

Scores:
- SEO Score: {seo_data.get('lighthouse_seo_score', 'N/A')}/100
- Accessibility: {seo_data.get('accessibility_score', 'N/A')}/100
- Best Practices: {seo_data.get('best_practices_score', 'N/A')}/100

Critical Issues: {', '.join(seo_data.get('critical_issues', [])[:3]) or 'None'}
Warnings: {', '.join(seo_data.get('warnings', [])[:5]) or 'None'}

Provide:
1. Top 3 priority fixes
2. Quick wins (doable in <1 hour)
3. Medium effort improvements (1-4 hours)
4. Estimated traffic impact of fixes
5. Keywords to target based on metrics"""

            message = self.anthropic.messages.create(
                model="haiku-4",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            recommendations = message.content[0].text

            audit.audit_data["seo_recommendations"] = recommendations

        except Exception as e:
            print(f"[SEO] Recommendation generation failed: {e}")

        return audit

    def analyze_keyword_opportunities(self, audit: Audit, business_category: str) -> Dict:
        """
        Analyze keyword opportunities for the business.

        Args:
            audit: Audit object
            business_category: Business category

        Returns:
            Dictionary with keyword opportunities
        """
        try:
            prompt = f"""Suggest SEO keywords for a {business_category} business in Pune/Pimpri-Chinchwad area.

Consider:
- Local SEO keywords (location-based)
- Industry-specific keywords
- Long-tail opportunities
- Voice search optimization

Provide:
1. Primary keywords (3-5)
2. Secondary keywords (5-10)
3. Local keywords (3-5)
4. Long-tail keywords (5)
5. Content ideas for each keyword type"""

            message = self.anthropic.messages.create(
                model="haiku-4",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            return {
                "keywords": message.content[0].text,
                "category": business_category,
            }

        except Exception as e:
            print(f"[SEO] Keyword analysis failed: {e}")
            return {}

    def calculate_seo_score(self, audit: Audit) -> int:
        """
        Calculate overall SEO score from components.

        Args:
            audit: Audit object with SEO data

        Returns:
            SEO score 0-100
        """
        if audit.seo_score:
            return audit.seo_score

        # Calculate from components
        score = 100

        # HTTPS penalty
        if not audit.https_enabled:
            score -= 15

        # Meta tags penalty
        if not audit.meta_tags_complete:
            score -= 10

        # Sitemap penalty
        if not audit.has_sitemap:
            score -= 10

        # Robots.txt penalty
        if not audit.has_robots_txt:
            score -= 5

        # Broken links penalty
        score -= min(audit.broken_links_count * 2, 20)

        # Tech stack penalty
        if audit.tech_stack == "unknown":
            score -= 5

        return max(0, min(100, score))


def analyze_seo(audit: Audit) -> Audit:
    """Convenience function for SEO analysis."""
    agent = SEOAuditorAgent()
    return agent.run(audit)
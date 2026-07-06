"""Agent 4: Website Auditor - Full website audit with Playwright and Lighthouse."""

import asyncio
from typing import Optional, Dict, List
from datetime import datetime

from anthropic import Anthropic
from models import Lead, Audit, DesignQuality
from config.prompts import get_prompt
from lib.crawler import WebsiteCrawler, crawl_website_sync, detect_tech_stack_sync
from lib.lighthouse import LighthouseAnalyzer, analyze_website_sync


class AuditorAgent:
    """Agent for performing comprehensive website audits."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the auditor agent."""
        self.anthropic = Anthropic(api_key=api_key or None)

    def run(self, lead: Lead) -> Optional[Audit]:
        """
        Perform full audit of a lead's website.

        Args:
            lead: Lead object with website URL

        Returns:
            Audit object with findings
        """
        if not lead.website_url:
            print(f"[Auditor] No website for {lead.business_name}")
            return None

        print(f"[Auditor] Starting audit for {lead.business_name}")
        print(f"[Auditor] URL: {lead.website_url}")

        try:
            audit = Audit(
                lead_id=lead.id,
                website_url=lead.website_url,
            )

            # Run Lighthouse analysis
            lh_result = analyze_website_sync(lead.website_url)
            if lh_result:
                audit.page_speed_score = lh_result.performance_score
                audit.mobile_score = lh_result.accessibility_score
                audit.seo_score = lh_result.seo_score

            # Crawl website
            crawl_result = crawl_website_sync(lead.website_url, max_pages=5)

            if crawl_result:
                # Check HTTPS
                audit.https_enabled = lead.website_url.startswith("https")

                # Count broken links
                audit.broken_links_count = len(crawl_result.broken_links)

                # Check for sitemap and robots.txt
                audit.has_sitemap = any("sitemap" in url for url in crawl_result.internal_links)
                audit.has_robots_txt = any("robots.txt" in url for url in crawl_result.internal_links)

                # Check meta tags
                has_title = any(r.title for r in crawl_result.results)
                has_meta_desc = any(r.meta_description for r in crawl_result.results)
                audit.meta_tags_complete = has_title and has_meta_desc

            # Detect tech stack
            tech_stack = detect_tech_stack_sync(lead.website_url)
            audit.tech_stack = tech_stack.get("tech_stack")
            audit.is_wordpress = tech_stack.get("is_wordpress", False)
            audit.is_wix = tech_stack.get("is_wix", False)
            audit.is_shopify = tech_stack.get("is_shopify", False)
            audit.cms_type = tech_stack.get("cms")

            # Run async checks (skip for now - requires playwright installation)
            # audit = self._run_async_checks(audit, lead.website_url)

            # Calculate design quality
            audit.design_quality = self._assess_design_quality(audit)

            print(f"[Auditor] Audit complete for {lead.business_name}")
            print(f"[Auditor] Scores - Speed: {audit.page_speed_score}, SEO: {audit.seo_score}, Broken: {audit.broken_links_count}")

            return audit

        except Exception as e:
            print(f"[Auditor] Audit failed for {lead.business_name}: {e}")
            return None

    async def _run_async_checks(self, audit: Audit, url: str) -> Audit:
        """Run async checks on the website."""
        crawler = WebsiteCrawler(max_pages=3)

        async with crawler:
            # Check for contact form
            audit.has_contact_form = await crawler.check_contact_form(url)

            # Check for CTA buttons
            has_cta, cta_list = await crawler.check_cta_buttons(url)
            audit.has_cta = has_cta

            # Check for WhatsApp
            audit.has_whatsapp = await crawler.check_whatsapp(url)

            # Check mobile friendliness
            is_mobile, issues = await crawler.check_mobile_friendly(url)
            if not is_mobile:
                audit.mobile_score = min(audit.mobile_score or 50, 40)

        return audit

    def _assess_design_quality(self, audit: Audit) -> DesignQuality:
        """Assess design quality based on audit metrics."""
        score = 0

        # Page speed contribution
        if audit.page_speed_score:
            score += audit.page_speed_score * 0.3

        # Mobile score contribution
        if audit.mobile_score:
            score += audit.mobile_score * 0.25

        # HTTPS bonus
        if audit.https_enabled:
            score += 10

        # Broken links penalty
        score -= min(audit.broken_links_count * 2, 20)

        # Tech stack quality indicator
        if audit.is_wordpress or audit.is_shopify:
            score += 5  # Known good platforms
        elif audit.tech_stack == "unknown":
            score -= 5

        # Contact and CTA bonus
        if audit.has_contact_form:
            score += 10
        if audit.has_cta:
            score += 10
        if audit.has_whatsapp:
            score += 5

        # Convert to quality enum
        if score >= 80:
            return DesignQuality.EXCELLENT
        elif score >= 65:
            return DesignQuality.GOOD
        elif score >= 50:
            return DesignQuality.AVERAGE
        elif score >= 30:
            return DesignQuality.POOR
        else:
            return DesignQuality.VERY_POOR

    def run_batch(self, leads: List[Lead]) -> List[Audit]:
        """
        Perform audits on multiple leads.

        Args:
            leads: List of Lead objects with websites

        Returns:
            List of Audit objects
        """
        audits = []
        leads_with_websites = [lead for lead in leads if lead.website_url]

        print(f"[Auditor] Batch audit for {len(leads_with_websites)} websites")

        for lead in leads_with_websites:
            audit = self.run(lead)
            if audit:
                audits.append(audit)

        return audits

    def run_with_ai_insights(self, audit: Audit, lead: Lead) -> Audit:
        """
        Use AI to provide deeper insights and recommendations.

        Args:
            audit: Existing audit object
            lead: Associated lead

        Returns:
            Audit with AI-generated insights added to audit_data
        """
        try:
            prompt = get_prompt(
                "auditor",
                url=lead.website_url,
                business_name=lead.business_name,
                category=lead.category,
            )

            # Build context from existing audit
            context = f"""Audit Results for {lead.business_name}:
- Page Speed: {audit.page_speed_score}/100
- Mobile Score: {audit.mobile_score}/100
- SEO Score: {audit.seo_score}/100
- HTTPS: {audit.https_enabled}
- Broken Links: {audit.broken_links_count}
- Tech Stack: {audit.tech_stack or 'Unknown'}
- CMS: {audit.cms_type or 'Unknown'}
- Contact Form: {audit.has_contact_form}
- CTA Buttons: {audit.has_cta}
- WhatsApp: {audit.has_whatsapp}
- Design Quality: {audit.design_quality}

Provide:
1. Top 5 improvement opportunities
2. Estimated impact of each improvement
3. Priority order for implementation
4. Specific technical recommendations"""

            message = self.anthropic.messages.create(
                model="sonnet-4-6-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": context}]
            )

            insights = message.content[0].text

            if audit.audit_data is None:
                audit.audit_data = {}

            audit.audit_data["ai_insights"] = insights

        except Exception as e:
            print(f"[Auditor] AI insights failed: {e}")

        return audit


def audit_website(lead: Lead) -> Optional[Audit]:
    """Convenience function to audit a website."""
    agent = AuditorAgent()
    return agent.run(lead)
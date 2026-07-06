"""Website crawler using Playwright for content extraction."""

import asyncio
import re
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import httpx


@dataclass
class CrawlResult:
    """Result of crawling a single page."""
    url: str
    title: str
    meta_description: str
    headings: Dict[str, List[str]]
    links: List[str]
    images: List[str]
    text_content: str
    status_code: int


@dataclass
class CrawlSummary:
    """Summary of website crawl."""
    base_url: str
    pages_crawled: int
    results: List[CrawlResult]
    internal_links: List[str]
    external_links: List[str]
    broken_links: List[str]


class WebsiteCrawler:
    """Website crawler using Playwright."""

    def __init__(
        self,
        max_pages: int = 10,
        max_depth: int = 2,
        timeout: int = 30000,
        user_agent: Optional[str] = None,
    ):
        """Initialize crawler."""
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.playwright = await async_playwright().start()
        self._browser = await self.playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1280, "height": 720},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def crawl(self, start_url: str) -> CrawlSummary:
        """Crawl website starting from URL."""
        visited = set()
        to_visit = [(start_url, 0)]
        results = []
        internal_links = set()
        external_links = set()

        base_domain = urlparse(start_url).netloc

        while to_visit and len(results) < self.max_pages:
            url, depth = to_visit.pop(0)

            if url in visited or depth > self.max_depth:
                continue

            visited.add(url)

            try:
                result = await self._crawl_page(url)
                results.append(result)

                # Collect links
                for link in result.links:
                    if link.startswith("/") or base_domain in link:
                        internal_links.add(urljoin(url, link))
                        full_url = urljoin(url, link)
                        if full_url not in visited and len(results) < self.max_pages:
                            to_visit.append((full_url, depth + 1))
                    elif link.startswith("http"):
                        external_links.add(link)

            except Exception as e:
                print(f"Error crawling {url}: {e}")
                continue

        return CrawlSummary(
            base_url=start_url,
            pages_crawled=len(results),
            results=results,
            internal_links=list(internal_links),
            external_links=list(external_links),
            broken_links=[r.url for r in results if r.status_code >= 400],
        )

    async def _crawl_page(self, url: str) -> CrawlResult:
        """Crawl a single page."""
        page = await self._context.new_page()

        try:
            response = await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

            # Get metadata
            title = await page.title()
            meta_desc = await page.evaluate("""
                () => {
                    const meta = document.querySelector('meta[name="description"]');
                    return meta ? meta.content : '';
                }
            """)

            # Get headings
            headings = {"h1": [], "h2": [], "h3": [], "h4": [], "h5": [], "h6": []}
            for tag in headings:
                headings[tag] = await page.evaluate(
                    f"""() => Array.from(document.querySelectorAll('{tag}')).map(el => el.textContent.trim())"""
                )

            # Get links
            links = await page.evaluate("""
                () => Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(h => h.startsWith('http') || h.startsWith('/'))
            """)

            # Get images
            images = await page.evaluate("""
                () => Array.from(document.querySelectorAll('img[src]'))
                    .map(img => img.src)
            """)

            # Get text content (first 5000 chars)
            text_content = await page.evaluate("""
                () => document.body ? document.body.innerText.slice(0, 5000) : ''
            """)

            return CrawlResult(
                url=url,
                title=title or "",
                meta_description=meta_desc or "",
                headings=headings,
                links=links or [],
                images=images or [],
                text_content=text_content or "",
                status_code=response.status if response else 0,
            )

        finally:
            await page.close()

    async def check_https(self, url: str) -> bool:
        """Check if website has HTTPS."""
        try:
            page = await self._context.new_page()
            response = await page.goto(f"https://{url}", timeout=10000, wait_until="domcontentloaded")
            return response is not None and response.status < 400
        except:
            return False

    async def check_mobile_friendly(self, url: str) -> Tuple[bool, str]:
        """Check if site is mobile friendly."""
        try:
            # Create mobile context
            mobile_context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
                viewport={"width": 375, "height": 667},
                device_scale_factor=2,
            )
            page = await mobile_context.new_page()

            response = await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

            # Check for viewport meta tag
            has_viewport = await page.evaluate("""
                () => !!document.querySelector('meta[name="viewport"]')
            """)

            # Check for horizontal scroll (indicates non-mobile-friendly)
            has_horizontal_scroll = await page.evaluate("""
                () => document.body.scrollWidth > document.body.clientWidth
            """)

            await mobile_context.close()

            is_mobile_friendly = has_viewport and not has_horizontal_scroll
            issues = []

            if not has_viewport:
                issues.append("Missing viewport meta tag")
            if has_horizontal_scroll:
                issues.append("Horizontal scrolling required")

            return is_mobile_friendly, "; ".join(issues) if issues else "OK"

        except Exception as e:
            return False, str(e)

    async def detect_tech_stack(self, url: str) -> Dict[str, any]:
        """Detect website technology stack."""
        result = {
            "tech_stack": "unknown",
            "cms": None,
            "is_wordpress": False,
            "is_wix": False,
            "is_shopify": False,
            "is_react": False,
            "is_nextjs": False,
            "js_frameworks": [],
        }

        try:
            page = await self._context.new_page()
            response = await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

            # Check HTML source for indicators
            html_content = await page.content()

            # WordPress detection
            if "wp-content" in html_content or "wp-includes" in html_content:
                result["is_wordpress"] = True
                result["cms"] = "WordPress"
                result["tech_stack"] = "WordPress"

            # Wix detection
            if "_wix混淆" in html_content or "wix.com" in html_content:
                result["is_wix"] = True
                result["cms"] = "Wix"
                result["tech_stack"] = "Wix"

            # Shopify detection
            if "cdn.shopify.com" in html_content or "myshopify.com" in html_content:
                result["is_shopify"] = True
                result["cms"] = "Shopify"
                result["tech_stack"] = "Shopify"

            # React detection
            if "__NEXT_DATA__" in html_content:
                result["is_nextjs"] = True
                result["js_frameworks"].append("Next.js")
            if "React" in html_content or "react" in html_content:
                result["is_react"] = True
                result["js_frameworks"].append("React")

            # Check script tags for other frameworks
            scripts = await page.evaluate("""
                () => Array.from(document.querySelectorAll('script[src]'))
                    .map(s => s.src)
            """)

            for script in scripts:
                if "gatsby" in script:
                    result["js_frameworks"].append("Gatsby")
                if "nuxt" in script:
                    result["js_frameworks"].append("Nuxt")
                if "angular" in script:
                    result["js_frameworks"].append("Angular")
                if "vue" in script:
                    result["js_frameworks"].append("Vue.js")
                if "bootstrap" in script:
                    result["js_frameworks"].append("Bootstrap")

            await page.close()

        except Exception as e:
            print(f"Error detecting tech stack for {url}: {e}")

        return result

    async def check_contact_form(self, url: str) -> bool:
        """Check if page has a contact form."""
        try:
            page = await self._context.new_page()
            await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

            has_form = await page.evaluate("""
                () => {
                    const forms = document.querySelectorAll('form');
                    return Array.from(forms).some(f =>
                        f.action || f.querySelector('button, input[type="submit"]')
                    );
                }
            """)

            await page.close()
            return has_form

        except:
            return False

    async def check_cta_buttons(self, url: str) -> Tuple[bool, List[str]]:
        """Check for CTA buttons on the page."""
        try:
            page = await self._context.new_page()
            await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

            ctas = await page.evaluate("""
                () => {
                    const keywords = ['contact', 'get', 'call', 'buy', 'order',
                        'schedule', 'book', 'quote', 'consultation', 'free'];
                    const buttons = document.querySelectorAll('button, a, input[type="submit"]');
                    return Array.from(buttons)
                        .filter(b => keywords.some(k =>
                            b.textContent.toLowerCase().includes(k) ||
                            b.value?.toLowerCase().includes(k)
                        ))
                        .map(b => b.textContent.trim() || b.value?.trim() || 'Button');
                }
            """)

            await page.close()
            return len(ctas) > 0, ctas[:5]

        except:
            return False, []

    async def check_whatsapp(self, url: str) -> bool:
        """Check if page has WhatsApp integration."""
        try:
            page = await self._context.new_page()
            content = await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")
            page_text = await page.content()

            has_whatsapp = (
                "wa.me" in page_text or
                "whatsapp.com" in page_text or
                "api.whatsapp.com" in page_text or
                await page.query_selector('a[href*="whatsapp"]')
            )

            await page.close()
            return has_whatsapp

        except:
            return False


# Synchronous wrapper
def crawl_website_sync(url: str, max_pages: int = 10) -> CrawlSummary:
    """Synchronous wrapper for website crawling."""
    crawler = WebsiteCrawler(max_pages=max_pages)

    async def run_crawl():
        async with crawler:
            return await crawler.crawl(url)

    return asyncio.run(run_crawl())


def detect_tech_stack_sync(url: str) -> dict:
    """Synchronous wrapper for tech stack detection."""
    crawler = WebsiteCrawler()

    async def run_detection():
        async with crawler:
            return await crawler.detect_tech_stack(url)

    return asyncio.run(run_detection())
"""Lighthouse CI integration for SEO and performance analysis."""

import asyncio
import json
import subprocess
from typing import Dict, Optional, List
from dataclasses import dataclass
from pathlib import Path
import tempfile
import os


@dataclass
class LighthouseResult:
    """Lighthouse audit result."""
    url: str
    performance_score: int
    accessibility_score: int
    best_practices_score: int
    seo_score: int
    pwa_score: int

    # Core Web Vitals
    lcp: float  # Largest Contentful Paint (seconds)
    fid: float   # First Input Delay (ms)
    cls: float   # Cumulative Layout Shift

    # Detailed metrics
    first_contentful_paint: float
    speed_index: float
    time_to_interactive: float
    total_blocking_time: float

    # Issues
    critical_issues: List[str]
    warnings: List[str]

    # Raw data
    raw_data: Optional[dict] = None


class LighthouseAnalyzer:
    """Lighthouse CI analyzer for website performance and SEO."""

    def __init__(
        self,
        output_dir: Optional[str] = None,
        n_workers: int = 2,
    ):
        """Initialize Lighthouse analyzer."""
        self.output_dir = output_dir or tempfile.mkdtemp()
        self.n_workers = n_workers

    async def analyze(self, url: str) -> LighthouseResult:
        """Run Lighthouse analysis on a URL."""
        # Create output file
        output_path = os.path.join(self.output_dir, f"lh_report_{hash(url)}.json")

        # Build Lighthouse command
        cmd = [
            "npx",
            "lighthouse",
            url,
            "--output=json",
            f"--output-path={output_path}",
            "--chrome-flags='--headless --no-sandbox'",
            "--only-categories=performance,accessibility,best-practices,seo,pwa",
            "--quiet",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                raise RuntimeError(f"Lighthouse failed: {result.stderr}")

            # Read results
            with open(output_path, "r") as f:
                data = json.load(f)

            return self._parse_result(url, data)

        except FileNotFoundError:
            raise RuntimeError(
                "Lighthouse not found. Install with: npm install -g lighthouse"
            )
        except Exception as e:
            raise RuntimeError(f"Lighthouse analysis failed: {e}")
        finally:
            # Cleanup
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass

    def _parse_result(self, url: str, data: dict) -> LighthouseResult:
        """Parse Lighthouse JSON output."""
        categories = data.get("categories", {})
        audits = data.get("audits", {})

        # Extract scores (0-100)
        performance = int((categories.get("performance", {}).get("score") or 0) * 100)
        accessibility = int((categories.get("accessibility", {}).get("score") or 0) * 100)
        best_practices = int((categories.get("best-practices", {}).get("score") or 0) * 100)
        seo = int((categories.get("seo", {}).get("score") or 0) * 100)
        pwa = int((categories.get("pwa", {}).get("score") or 0) * 100)

        # Core Web Vitals
        metrics = audits.get("metrics", {}).get("details", {}).get("metrics", [])

        def get_metric_value(metric_name: str) -> float:
            for m in metrics:
                if m.get("id") == metric_name:
                    return m.get("value", 0)
            return 0

        lcp = get_metric_value("largest-contentful-paint") / 1000  # Convert to seconds
        fid = get_metric_value("max-first-input-delay")  # ms
        cls = get_metric_value("cumulative-layout-shift")

        fcp = get_metric_value("first-contentful-paint") / 1000
        speed_index = get_metric_value("speed-index") / 1000
        tti = get_metric_value("interactive") / 1000
        tbt = get_metric_value("total-blocking-time") / 1000

        # Extract issues
        critical = []
        warnings = []

        # Check for critical issues
        critical_audits = [
            "uses-webp-images",
            "uses-long-cache-ttl",
            "uses-resize-not-matching",
            "uses-responsive-images",
            "render-blocking-resources",
            "unused-css-rules",
            "unused-javascript",
        ]

        for audit_id in critical_audits:
            audit = audits.get(audit_id, {})
            if audit.get("score", 1) < 0.5:
                critical.append(audit.get("description", audit_id))

        # Check for warnings
        warning_audits = [
            "uses-optimized-images",
            "uses-text-compression",
            "uses-rel-preconnect",
            "render-blocking-resources",
            "third-party-facades",
        ]

        for audit_id in warning_audits:
            audit = audits.get(audit_id, {})
            if audit.get("score", 1) < 0.9 and audit.get("score", 1) >= 0.5:
                warnings.append(audit.get("description", audit_id))

        return LighthouseResult(
            url=url,
            performance_score=performance,
            accessibility_score=accessibility,
            best_practices_score=best_practices,
            seo_score=seo,
            pwa_score=pwa,
            lcp=lcp,
            fid=fid,
            cls=cls,
            first_contentful_paint=fcp,
            speed_index=speed_index,
            time_to_interactive=tti,
            total_blocking_time=tbt,
            critical_issues=critical[:5],
            warnings=warnings[:10],
            raw_data=data,
        )

    async def analyze_batch(self, urls: List[str]) -> List[LighthouseResult]:
        """Analyze multiple URLs in parallel."""
        tasks = [self.analyze(url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)


def analyze_website_sync(url: str) -> Optional[LighthouseResult]:
    """Synchronous wrapper for Lighthouse analysis."""
    analyzer = LighthouseAnalyzer()
    try:
        return asyncio.run(analyzer.analyze(url))
    except Exception as e:
        print(f"Lighthouse analysis failed for {url}: {e}")
        return None


def get_seo_checklist() -> Dict[str, List[str]]:
    """Get SEO checklist with common issues to check."""
    return {
        "meta_tags": [
            "Document does not have a meta description",
            "Document does not have a title",
            "Title is too short",
            "Title is too long",
        ],
        "headings": [
            "Heading structure is not semantic",
            "Document does not have a h1 heading",
            "Headings are not in a sequentially descending order",
        ],
        "images": [
            "Image elements do not have alt attributes",
            "Image elements have alt attributes with empty text",
        ],
        "links": [
            "Document does not have a sitemap",
            "Document does not have a robots.txt",
        ],
        "accessibility": [
            "Background and foreground colors do not have a sufficient contrast ratio",
            "Tap targets are not sized appropriately",
            "Interactive elements are not focusable",
        ],
    }
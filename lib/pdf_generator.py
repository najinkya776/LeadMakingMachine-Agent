"""PDF report generator for lead outreach."""

import os
from datetime import datetime
from typing import Optional
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from jinja2 import Template

from models import Lead, Audit, Report


class PDFGenerator:
    """Generate professional PDF reports for leads."""

    # Color scheme
    COLORS = {
        "primary": HexColor("#2563EB"),
        "secondary": HexColor("#64748B"),
        "success": HexColor("#10B981"),
        "warning": HexColor("#F59E0B"),
        "danger": HexColor("#EF4444"),
        "light": HexColor("#F8FAFC"),
        "dark": HexColor("#1E293B"),
    }

    def __init__(self, output_dir: Optional[str] = None):
        """Initialize PDF generator."""
        self.output_dir = output_dir or "output/reports"
        os.makedirs(self.output_dir, exist_ok=True)

        # Setup styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Title"],
                fontSize=28,
                textColor=self.COLORS["primary"],
                spaceAfter=20,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading1"],
                fontSize=16,
                textColor=self.COLORS["dark"],
                spaceBefore=15,
                spaceAfter=10,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="SubHeader",
                parent=self.styles["Heading2"],
                fontSize=13,
                textColor=self.COLORS["secondary"],
                spaceBefore=10,
                spaceAfter=6,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="CustomBody",
                parent=self.styles["BodyText"],
                fontSize=11,
                textColor=self.COLORS["dark"],
                leading=16,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="ScoreValue",
                parent=self.styles["Normal"],
                fontSize=36,
                textColor=self.COLORS["primary"],
                alignment=TA_CENTER,
            )
        )

    def generate_report(
        self,
        lead: Lead,
        audit: Optional[Audit],
        report: Report,
    ) -> str:
        """Generate PDF report for a lead."""
        filename = f"report_{lead.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(self.output_dir, filename)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        # Build content
        content = []

        # Header
        content.extend(self._build_header(lead, report))

        # Executive Summary
        content.extend(self._build_summary(lead, report))

        # Current State (if audit available)
        if audit:
            content.extend(self._build_current_state(lead, audit, report))

        # Recommendations
        content.extend(self._build_recommendations(audit, report))

        # Pricing Section
        content.extend(self._build_pricing(report))

        # Next Steps
        content.extend(self._build_next_steps())

        # Build PDF
        doc.build(content)

        return filepath

    def _build_header(self, lead: Lead, report: Report) -> list:
        """Build report header."""
        elements = []

        # Company branding area
        elements.append(
            Paragraph(
                "WEBSITE PITCHER",
                self.styles["SectionHeader"],
            )
        )
        elements.append(Spacer(1, 10))

        # Report title
        elements.append(
            Paragraph(
                f"Digital Presence Audit Report",
                self.styles["ReportTitle"],
            )
        )

        # Business name and date
        elements.append(
            Paragraph(
                f"Prepared for: {lead.business_name}",
                self.styles["SubHeader"],
            )
        )

        date_str = datetime.now().strftime("%B %d, %Y")
        elements.append(
            Paragraph(
                f"Date: {date_str}",
                self.styles["CustomBody"],
            )
        )

        elements.append(Spacer(1, 20))

        # Score box
        score_text = f"{report.opportunity_score}"
        classification = report.classification.upper()

        score_color = (
            self.COLORS["success"]
            if report.opportunity_score >= 80
            else self.COLORS["warning"]
            if report.opportunity_score >= 50
            else self.COLORS["danger"]
        )

        score_data = [
            [
                Paragraph(score_text, self.styles["ScoreValue"]),
                Paragraph(
                    f"<font color='#{score_color.hexval()[2:]}'>{classification}</font><br/>"
                    "Opportunity Score",
                    self.styles["CustomBody"],
                ),
            ]
        ]

        score_table = Table(score_data, colWidths=[2 * inch, 4 * inch])
        score_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), self.COLORS["light"]),
                    ("ALIGN", (0, 0), (0, 0), "CENTER"),
                    ("ALIGN", (1, 0), (1, 0), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (0, 0), 20),
                    ("RIGHTPADDING", (1, 0), (1, 0), 20),
                    ("BOX", (0, 0), (-1, -1), 1, self.COLORS["primary"]),
                    ("ROUNDEDCORNERS", [5, 5, 5, 5]),
                ]
            )
        )

        elements.append(score_table)
        elements.append(Spacer(1, 30))

        return elements

    def _build_summary(self, lead: Lead, report: Report) -> list:
        """Build executive summary section."""
        elements = []

        elements.append(
            Paragraph("Executive Summary", self.styles["SectionHeader"])
        )
        elements.append(Spacer(1, 5))

        if report.executive_summary:
            elements.append(Paragraph(report.executive_summary, self.styles["CustomBody"]))
        else:
            # Generate from pitch
            pitch_preview = report.pitch_content[:300] + "..." if len(report.pitch_content) > 300 else report.pitch_content
            elements.append(Paragraph(pitch_preview, self.styles["CustomBody"]))

        elements.append(Spacer(1, 20))

        return elements

    def _build_current_state(
        self,
        lead: Lead,
        audit: Audit,
        report: Report,
    ) -> list:
        """Build current state assessment section."""
        elements = []

        elements.append(Paragraph("Current State Assessment", self.styles["SectionHeader"]))
        elements.append(Spacer(1, 10))

        # Business info table
        business_info = [
            ["Business Name", lead.business_name],
            ["Category", lead.category or "N/A"],
            ["Address", lead.address or "N/A"],
            ["Phone", lead.phone or "N/A"],
            ["Website", lead.website_url or "Not found"],
        ]

        info_table = Table(business_info, colWidths=[2 * inch, 5 * inch])
        info_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), self.COLORS["light"]),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, self.COLORS["secondary"]),
                ]
            )
        )
        elements.append(info_table)
        elements.append(Spacer(1, 15))

        # Audit scores
        if audit:
            elements.append(Paragraph("Website Audit Scores", self.styles["SubHeader"]))
            elements.append(Spacer(1, 5))

            score_data = [
                ["Metric", "Score", "Status"],
                ["Page Speed", f"{audit.page_speed_score or 'N/A'}/100", self._score_status(audit.page_speed_score)],
                ["Mobile Friendly", f"{audit.mobile_score or 'N/A'}/100", self._score_status(audit.mobile_score)],
                ["SEO Health", f"{audit.seo_score or 'N/A'}/100", self._score_status(audit.seo_score)],
                ["HTTPS", "Yes" if audit.https_enabled else "No", "✓" if audit.https_enabled else "✗"],
                ["Broken Links", str(audit.broken_links_count), self._broken_links_status(audit.broken_links_count)],
            ]

            score_table = Table(score_data, colWidths=[2.5 * inch, 1.5 * inch, 2 * inch])
            score_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), self.COLORS["primary"]),
                        ("TEXTCOLOR", (0, 0), (-1, 0), white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, self.COLORS["secondary"]),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, self.COLORS["light"]]),
                    ]
                )
            )
            elements.append(score_table)
            elements.append(Spacer(1, 20))

        return elements

    def _build_recommendations(self, audit: Optional[Audit], report: Report) -> list:
        """Build recommendations section."""
        elements = []

        elements.append(Paragraph("Recommendations", self.styles["SectionHeader"]))
        elements.append(Spacer(1, 10))

        # Parse pitch content for recommendations
        recommendations = [
            "Conduct a comprehensive website redesign to improve user experience",
            "Implement mobile-first design approach for better accessibility",
            "Add clear call-to-action buttons on all pages",
            "Optimize page load speed for improved SEO rankings",
            "Implement contact form with business information prominently displayed",
        ]

        for i, rec in enumerate(recommendations, 1):
            elements.append(
                Paragraph(f"<b>{i}.</b> {rec}", self.styles["CustomBody"])
            )
            elements.append(Spacer(1, 5))

        elements.append(Spacer(1, 15))

        return elements

    def _build_pricing(self, report: Report) -> list:
        """Build pricing section."""
        elements = []

        elements.append(Paragraph("Investment Options", self.styles["SectionHeader"]))
        elements.append(Spacer(1, 10))

        pricing_data = [
            ["Package", "Features", "Investment"],
            [
                "Basic",
                "5-page website, mobile responsive, contact form",
                "₹15,000 - ₹25,000",
            ],
            [
                "Standard",
                "10-page website, SEO optimization, social media integration",
                "₹30,000 - ₹50,000",
            ],
            [
                "Premium",
                "Full website with CMS, advanced SEO, analytics, 1-year support",
                "₹60,000 - ₹1,50,000",
            ],
        ]

        pricing_table = Table(pricing_data, colWidths=[1.5 * inch, 4 * inch, 1.5 * inch])
        pricing_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.COLORS["primary"]),
                    ("TEXTCOLOR", (0, 0), (-1, 0), white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, self.COLORS["secondary"]),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, self.COLORS["light"]]),
                ]
            )
        )
        elements.append(pricing_table)
        elements.append(Spacer(1, 20))

        return elements

    def _build_next_steps(self) -> list:
        """Build next steps section."""
        elements = []

        elements.append(Paragraph("Next Steps", self.styles["SectionHeader"]))
        elements.append(Spacer(1, 10))

        steps = [
            "Schedule a free 30-minute consultation to discuss your needs",
            "Receive a customized proposal within 24 hours",
            "Review and approve the proposal",
            "Get started with your website improvement project",
        ]

        for i, step in enumerate(steps, 1):
            elements.append(
                Paragraph(f"<b>{i}.</b> {step}", self.styles["CustomBody"])
            )
            elements.append(Spacer(1, 5))

        elements.append(Spacer(1, 30))

        # Footer
        elements.append(
            Paragraph(
                "Generated by Website Pitcher - Multi-Agent Lead Generation System",
                self.styles["SubHeader"],
            )
        )

        return elements

    def _score_status(self, score: Optional[int]) -> str:
        """Get status text for score."""
        if score is None:
            return "N/A"
        if score >= 80:
            return "✓ Excellent"
        if score >= 60:
            return "○ Good"
        if score >= 40:
            return "⚠ Needs Work"
        return "✗ Poor"

    def _broken_links_status(self, count: int) -> str:
        """Get status for broken links."""
        if count == 0:
            return "✓ None"
        if count < 5:
            return f"⚠ {count} found"
        return f"✗ {count} found"


def generate_pdf_report(
    lead: Lead,
    audit: Optional[Audit],
    report: Report,
    output_dir: Optional[str] = None,
) -> str:
    """Generate PDF report (convenience function)."""
    generator = PDFGenerator(output_dir)
    return generator.generate_report(lead, audit, report)
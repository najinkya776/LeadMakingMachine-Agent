"""Agent Orchestrator - CrewAI crew definition and pipeline orchestration."""

import os
import sys
import json
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass

from crewai import Agent, Crew, Process, Task
from crewai.tasks import TaskOutput

from agents.scraper_primary import ScraperPrimaryAgent
from agents.scraper_social import ScraperSocialAgent
from agents.qualifier import QualifierAgent
from agents.auditor import AuditorAgent
from agents.seo_auditor import SEOAuditorAgent
from agents.social_analyzer import SocialAnalyzerAgent
from agents.scorer import ScorerAgent, LeadScore
from agents.pitch_no_website import PitchNoWebsiteAgent
from agents.pitch_has_website import PitchHasWebsiteAgent
from agents.reporter import ReporterAgent

from models import Lead, Audit, Report, LeadStatus
from models.lead import SocialHandles as PydanticSocialHandles
from config.settings import CREWAI_SETTINGS
from db.database import LeadDatabase, Lead as DBLLead, LeadStatus as DBLeadStatus


# ==================== MODEL CONVERSION HELPERS ====================

def pydantic_lead_to_db(lead: Lead, score: int = 0) -> DBLLead:
    """
    Convert a Pydantic Lead (from agents) to db.database Lead dataclass.

    Args:
        lead: Pydantic Lead model
        score: Optional score value

    Returns:
        DBLLead dataclass compatible with db.database
    """
    import uuid as uuid_mod

    # Extract social handles to JSON if present
    social_handles_json = "{}"
    if lead.social_handles:
        if isinstance(lead.social_handles, PydanticSocialHandles):
            social_handles_json = lead.social_handles.model_dump_json()
        elif isinstance(lead.social_handles, dict):
            temp = PydanticSocialHandles(**lead.social_handles)
            social_handles_json = temp.model_dump_json()

    return DBLLead(
        id=None,
        business_name=lead.business_name,
        owner_name="",
        industry=lead.category,
        location=lead.address or "",
        email=lead.email or "",
        phone=lead.phone or "",
        website=lead.website_url or "",
        google_maps_url="",
        rating=lead.google_rating or 0.0,
        reviews_count=lead.review_count or 0,
        status=DBLeadStatus.SCRAPED.value,
        source=lead.source,
        score=score,
        findings=social_handles_json,
        notes="",
        contact_attempts=0,
        last_contacted=None,
        next_followup=None,
        created_at=None,
        updated_at=None,
    )


def db_lead_to_pydantic(db_lead: DBLLead) -> Lead:
    """
    Convert a db.database Lead dataclass to Pydantic Lead model.

    Args:
        db_lead: DBLLead dataclass from db.database

    Returns:
        Pydantic Lead model
    """
    import uuid as uuid_mod
    from models.lead import SocialHandles as PydanticSocialHandles

    # Parse social handles if present
    social_handles = None
    if db_lead.findings:
        try:
            social_handles = PydanticSocialHandles.model_validate_json(db_lead.findings)
        except Exception:
            pass

    # Map database status to pydantic status
    status = LeadStatus.RAW
    if db_lead.status == DBLeadStatus.QUALIFIED.value:
        status = LeadStatus.QUALIFIED
    elif db_lead.status == DBLeadStatus.SCORED.value:
        status = LeadStatus.SCORED
    elif db_lead.status == DBLeadStatus.AUDITED.value:
        status = LeadStatus.AUDITING

    return Lead(
        id=str(db_lead.id) if db_lead.id else str(uuid_mod.uuid4()),
        business_name=db_lead.business_name,
        category=db_lead.industry,
        address=db_lead.location,
        phone=db_lead.phone,
        email=db_lead.email,
        website_url=db_lead.website,
        google_rating=db_lead.rating,
        review_count=db_lead.reviews_count,
        source=db_lead.source,
        status=status,
        social_handles=social_handles,
    )


@dataclass
class PipelineState:
    """State object for the pipeline."""
    current_step: str = "idle"
    leads: List[Lead] = None
    qualified_leads: List[Lead] = None
    audits: Dict[str, Audit] = None
    scores: Dict[str, LeadScore] = None
    reports: List[Report] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.leads is None:
            self.leads = []
        if self.qualified_leads is None:
            self.qualified_leads = []
        if self.audits is None:
            self.audits = {}
        if self.scores is None:
            self.scores = {}
        if self.reports is None:
            self.reports = []
        if self.errors is None:
            self.errors = []


class OrchestratorAgent:
    """Main orchestrator for the 10-agent lead generation pipeline."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the orchestrator."""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        # Initialize all agents
        self.scraper_primary = ScraperPrimaryAgent(self.api_key)
        self.scraper_social = ScraperSocialAgent(self.api_key)
        self.qualifier = QualifierAgent(self.api_key)
        self.auditor = AuditorAgent(self.api_key)
        self.seo_auditor = SEOAuditorAgent(self.api_key)
        self.social_analyzer = SocialAnalyzerAgent(self.api_key)
        self.scorer = ScorerAgent(self.api_key)
        self.pitch_no_website = PitchNoWebsiteAgent(self.api_key)
        self.pitch_has_website = PitchHasWebsiteAgent(self.api_key)
        self.reporter = ReporterAgent(self.api_key)

        # Initialize database
        self.db = LeadDatabase()

        self.state = PipelineState()

    def run_full_pipeline(
        self,
        location: str = "Pimpri-Chinchwad, Pune, India",
        categories: Optional[List[str]] = None,
        count: int = 50,
    ) -> PipelineState:
        """
        Run the complete lead generation pipeline.

        Args:
            location: Target location for scraping
            categories: Business categories to target
            count: Maximum number of leads to collect

        Returns:
            PipelineState with all results
        """
        print("=" * 60)
        print("Starting Website Pitcher Pipeline")
        print("=" * 60)

        try:
            # Step 1: Scrape leads
            self.state.current_step = "scraping"
            print("\n[Step 1/6] Scraping leads...")
            self.state.leads = self.scraper_primary.run(location, categories, count)
            print(f"   Scraped {len(self.state.leads)} leads")

            # Save scraped leads to database
            self._save_leads_to_db(self.state.leads, DBLeadStatus.SCRAPED.value)

            # Step 2: Enrich with social media data
            self.state.current_step = "social_enrichment"
            print("\n[Step 2/6] Enriching with social media data...")
            self.state.leads = self.scraper_social.run(self.state.leads)
            print(f"   Social data added to {len(self.state.leads)} leads")

            # Step 3: Qualify leads
            self.state.current_step = "qualifying"
            print("\n[Step 3/6] Qualifying leads...")
            self.state.qualified_leads = self.qualifier.run(self.state.leads)
            print(f"   Qualified {len(self.state.qualified_leads)} leads")

            # Update status to qualified in database
            self._update_leads_status(self.state.qualified_leads, DBLeadStatus.QUALIFIED.value)

            # Step 4: Audit and score
            self.state.current_step = "auditing"
            print("\n[Step 4/6] Auditing websites...")
            audits = {}
            social_analyses = {}
            scores = {}

            for lead in self.state.qualified_leads:
                # Audit website if exists
                if lead.website_url:
                    audit = self.auditor.run(lead)
                    if audit:
                        audits[lead.id] = audit
                        # Enhance with SEO audit
                        audits[lead.id] = self.seo_auditor.run(audits[lead.id])

                # Analyze social presence
                social_analysis = self.social_analyzer.run(lead)
                social_analyses[lead.id] = social_analysis

                # Score lead
                score = self.scorer.run(lead, audits.get(lead.id), social_analysis)
                scores[lead.id] = score

                print(f"   Scored: {lead.business_name.encode('ascii', 'replace').decode('ascii')} - {score.total_score}/100 ({score.classification})")

            self.state.audits = audits
            self.state.scores = scores

            # Update status to audited in database
            self._update_leads_status(self.state.qualified_leads, DBLeadStatus.AUDITED.value)

            # Step 5: Generate pitches
            self.state.current_step = "pitching"
            print("\n[Step 5/6] Generating pitches...")
            for lead in self.state.qualified_leads:
                score = scores.get(lead.id)
                if not score or score.total_score < 50:
                    continue  # Skip low-scoring leads

                audit = audits.get(lead.id)

                # Choose pitch type based on lead type
                if not lead.website_url:
                    pitch = self.pitch_no_website.run(lead, social_analyses.get(lead.id))
                else:
                    pitch = self.pitch_has_website.run(lead, audit)

                # Step 6: Generate reports
                print(f"   Pitch generated for: {lead.business_name}")

            # Step 6: Generate reports
            self.state.current_step = "reporting"
            print("\n[Step 6/6] Generating reports...")
            for lead in self.state.qualified_leads:
                score = scores.get(lead.id)
                if not score:
                    continue

                audit = audits.get(lead.id)
                lead_type = "no_website" if not lead.website_url else "has_website"

                # Get pitch (would need to store in a more robust way)
                if not lead.website_url:
                    pitch = self.pitch_no_website.run(lead, social_analyses.get(lead.id))
                else:
                    pitch = self.pitch_has_website.run(lead, audit)

                report = self.reporter.run(
                    lead=lead,
                    audit=audit,
                    score=score.total_score,
                    classification=score.classification,
                    pitch=pitch,
                    lead_type=lead_type,
                )

                self.state.reports.append(report)
                print(f"   Report generated: {lead.business_name} - {report.pdf_path}")

            # Update status to report_generated in database
            self._update_leads_status(self.state.qualified_leads, DBLeadStatus.REPORT_GENERATED.value)

            print("\n" + "=" * 60)
            print("Pipeline Complete!")
            print("=" * 60)
            print(f"Total leads: {len(self.state.leads)}")
            print(f"Qualified: {len(self.state.qualified_leads)}")
            print(f"Reports: {len(self.state.reports)}")
            print(f"Errors: {len(self.state.errors)}")

            return self.state

        except Exception as e:
            print(f"\n[ERROR] Pipeline failed: {e}")
            self.state.errors.append(str(e))
            return self.state

    def run_single_lead(
        self,
        lead: Lead,
        audit: Optional[Audit] = None,
    ) -> Report:
        """
        Process a single lead through the pipeline.

        Args:
            lead: Lead object to process
            audit: Optional pre-computed audit

        Returns:
            Report object
        """
        # Social analysis
        social_analysis = self.social_analyzer.run(lead)

        # Score
        score = self.scorer.run(lead, audit, social_analysis)

        # Generate pitch
        if not lead.website_url:
            pitch = self.pitch_no_website.run(lead, social_analysis)
        else:
            pitch = self.pitch_has_website.run(lead, audit)

        # Generate report
        report = self.reporter.run(
            lead=lead,
            audit=audit,
            score=score.total_score,
            classification=score.classification,
            pitch=pitch,
            lead_type="no_website" if not lead.website_url else "has_website",
        )

        return report

    def get_high_priority_leads(self, min_score: int = 80) -> List[Lead]:
        """Get leads with scores above threshold."""
        if not self.state.scores:
            return []

        high_priority = []
        for lead in self.state.qualified_leads:
            score = self.state.scores.get(lead.id)
            if score and score.total_score >= min_score:
                high_priority.append(lead)

        return high_priority

    def get_pipeline_summary(self) -> Dict:
        """Get summary of pipeline results."""
        return {
            "total_leads": len(self.state.leads),
            "qualified_leads": len(self.state.qualified_leads),
            "audits_completed": len(self.state.audits),
            "reports_generated": len(self.state.reports),
            "errors": len(self.state.errors),
            "high_priority_count": len(self.get_high_priority_leads()),
            "avg_score": self._calculate_avg_score(),
        }

    def _calculate_avg_score(self) -> float:
        """Calculate average score across all scored leads."""
        if not self.state.scores:
            return 0

        total = sum(s.total_score for s in self.state.scores.values())
        return round(total / len(self.state.scores), 1)

    def _save_leads_to_db(self, leads: List[Lead], status: str = "scraped") -> int:
        """
        Save leads to the database with specified status.

        Args:
            leads: List of Pydantic Lead objects
            status: Status to set for the leads

        Returns:
            Number of leads saved
        """
        count = 0
        for lead in leads:
            try:
                db_lead = pydantic_lead_to_db(lead)
                db_lead.status = status
                self.db.add_lead(db_lead)
                count += 1
            except Exception as e:
                print(f"   [DB] Error saving lead {lead.business_name}: {e}")
        print(f"   [DB] Saved {count} leads with status '{status}'")
        return count

    def _update_leads_status(self, leads: List[Lead], status: str) -> int:
        """
        Update lead statuses in the database by finding them and updating.

        Args:
            leads: List of Pydantic Lead objects
            status: New status value

        Returns:
            Number of leads updated
        """
        count = 0
        for lead in leads:
            try:
                # Find lead by email or business name
                db_lead = None
                if lead.email:
                    db_lead = self.db.get_lead_by_email(lead.email)
                if not db_lead:
                    # Try to find by business name
                    existing = self.db.get_leads(industry=lead.category, limit=100)
                    for ex in existing:
                        if ex.business_name == lead.business_name:
                            db_lead = ex
                            break
                if db_lead and db_lead.id:
                    self.db.update_lead_status(db_lead.id, status)
                    count += 1
            except Exception as e:
                print(f"   [DB] Error updating lead {lead.business_name}: {e}")
        print(f"   [DB] Updated {count} leads to status '{status}'")
        return count

    def mark_leads_contacted(self, leads: List[Lead]) -> int:
        """
        Mark leads as contacted (after sending emails).

        Args:
            leads: List of Pydantic Lead objects that have been emailed

        Returns:
            Number of leads marked
        """
        return self._update_leads_status(leads, DBLeadStatus.CONTACTED.value)

    def send_emails_to_leads(
        self,
        leads: List[Lead] = None,
        max_emails: int = 5,
        email_type: str = "initial"
    ) -> Dict[str, Any]:
        """
        Send outreach emails to leads and update their status.

        Args:
            leads: Optional list of leads (if None, fetches from database)
            max_emails: Maximum emails to send
            email_type: Type of email (initial, followup_1, etc.)

        Returns:
            Dict with results summary
        """
        from agents.email_agent import EmailAgent

        email_agent = EmailAgent()

        if leads is None:
            # Fetch leads needing contact from database
            db_leads = self.db.get_leads_needing_followup()
            leads = [db_lead_to_pydantic(db_lead) for db_lead in db_leads]

        results = email_agent.send_bulk(leads, max_emails=max_emails)

        # Mark successfully contacted leads
        contacted = [r.lead for r in results if r.success]
        self.mark_leads_contacted(contacted)

        return {
            "total_sent": len(results),
            "successful": len([r for r in results if r.success]),
            "failed": len([r for r in results if not r.success]),
            "results": results,
        }

    def export_leads_csv(self, filepath: str = "output/leads_export.csv"):
        """Export leads to CSV file."""
        import csv

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Business Name", "Category", "Phone", "Email", "Website",
                "Google Rating", "Reviews", "Lead Type", "Score", "Classification"
            ])

            for lead in self.state.qualified_leads:
                score = self.state.scores.get(lead.id)
                writer.writerow([
                    lead.business_name,
                    lead.category,
                    lead.phone,
                    lead.email,
                    lead.website_url,
                    lead.google_rating,
                    lead.review_count,
                    lead.lead_type.value if lead.lead_type else "",
                    score.total_score if score else "",
                    score.classification if score else "",
                ])

        print(f"[Orchestrator] Exported to {filepath}")


def create_crewai_crew() -> Crew:
    """
    Create a CrewAI crew for parallel agent execution.
    This provides an alternative to the sequential pipeline.
    """
    # Create agents
    scraper_agent = Agent(
        role="Lead Scraper",
        goal="Find potential clients from Google Maps and business directories",
        backstory="You are an expert at finding and collecting business leads from online sources.",
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    qualifier_agent = Agent(
        role="Lead Qualifier",
        goal="Filter and deduplicate leads based on quality criteria",
        backstory="You are an expert at evaluating and qualifying business leads for sales opportunities.",
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    auditor_agent = Agent(
        role="Website Auditor",
        goal="Analyze websites and identify improvement opportunities",
        backstory="You are an expert at auditing websites for performance, SEO, and user experience.",
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    scorer_agent = Agent(
        role="Lead Scorer",
        goal="Calculate opportunity scores for leads",
        backstory="You are an expert at scoring and prioritizing sales leads based on potential.",
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    # Create tasks
    scrape_task = Task(
        description="Scrape 50 leads from Google Maps in Pimpri-Chinchwad, Pune for restaurants, clinics, and shops",
        agent=scraper_agent,
        expected_output="JSON list of lead objects with business_name, category, phone, address, rating",
    )

    qualify_task = Task(
        description="Filter leads based on ICP: minimum 3 reviews, 3+ star rating, location in Pune area",
        agent=qualifier_agent,
        expected_output="Filtered list of qualified leads with tags",
        depends_on=[scrape_task],
    )

    audit_task = Task(
        description="Audit websites of qualified leads, check page speed, mobile, SEO, design quality",
        agent=auditor_agent,
        expected_output="Audit reports for each website with scores and recommendations",
        depends_on=[qualify_task],
    )

    score_task = Task(
        description="Score all leads based on audit results, business signals, and lead type",
        agent=scorer_agent,
        expected_output="Prioritized list of leads with scores and classifications",
        depends_on=[audit_task],
    )

    # Create crew
    crew = Crew(
        agents=[scraper_agent, qualifier_agent, auditor_agent, scorer_agent],
        tasks=[scrape_task, qualify_task, audit_task, score_task],
        process=Process.hierarchical,
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    return crew
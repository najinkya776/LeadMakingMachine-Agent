"""CrewAI crew definition for parallel agent execution."""

from crewai import Agent, Crew, Task, Process
from crewai.tools import BaseTool

from config.settings import CREWAI_SETTINGS


class ScrapingTool(BaseTool):
    """Tool for scraping leads."""
    name: str = "scrape_leads"
    description: str = "Scrapes leads from Google Maps and business directories"

    def _run(self, location: str, categories: list, count: int) -> str:
        """Run the scraping tool."""
        from agents.scraper_primary import ScraperPrimaryAgent

        agent = ScraperPrimaryAgent()
        leads = agent.run(location=location, categories=categories, count=count)

        return f"Scraped {len(leads)} leads from {location}"


class QualificationTool(BaseTool):
    """Tool for qualifying leads."""
    name: str = "qualify_leads"
    description: str = "Filters and deduplicates leads based on ICP"

    def _run(self, leads_data: str) -> str:
        """Run the qualification tool."""
        from agents.qualifier import QualifierAgent
        from models import Lead
        import json

        leads = [Lead.from_dict(json.loads(l)) for l in leads_data.split(";")]
        agent = QualifierAgent()
        qualified = agent.run(leads)

        return f"Qualified {len(qualified)} leads"


class AuditTool(BaseTool):
    """Tool for auditing websites."""
    name: str = "audit_website"
    description: str = "Performs comprehensive website audit"

    def _run(self, url: str, business_name: str) -> str:
        """Run the audit tool."""
        from agents.auditor import AuditorAgent
        from models import Lead

        lead = Lead(business_name=business_name, website_url=url)
        agent = AuditorAgent()
        audit = agent.run(lead)

        return f"Audit complete for {url}"


class ScoringTool(BaseTool):
    """Tool for scoring leads."""
    name: str = "score_lead"
    description: str = "Calculates opportunity score for a lead"

    def _run(self, lead_data: str, audit_data: str) -> str:
        """Run the scoring tool."""
        from agents.scorer import ScorerAgent
        from agents.social_analyzer import SocialAnalyzerAgent
        from models import Lead, Audit
        import json

        lead = Lead.from_dict(json.loads(lead_data))
        audit = Audit.from_dict(json.loads(audit_data)) if audit_data else None

        scorer = ScorerAgent()
        social_analyzer = SocialAnalyzerAgent()
        social = social_analyzer.run(lead)
        score = scorer.run(lead, audit, social)

        return f"Score: {score.total_score}/100 ({score.classification})"


class PitchTool(BaseTool):
    """Tool for generating pitches."""
    name: str = "generate_pitch"
    description: str = "Generates personalized sales pitch"

    def _run(self, lead_data: str, audit_data: str, score: str) -> str:
        """Run the pitch generation tool."""
        from agents.pitch_no_website import PitchNoWebsiteAgent
        from agents.pitch_has_website import PitchHasWebsiteAgent
        from models import Lead, Audit
        import json

        lead = Lead.from_dict(json.loads(lead_data))
        audit = Audit.from_dict(json.loads(audit_data)) if audit_data else None

        if not lead.website_url:
            agent = PitchNoWebsiteAgent()
            pitch = agent.run(lead)
        else:
            agent = PitchHasWebsiteAgent()
            pitch = agent.run(lead, audit)

        return pitch[:200] + "..."


class ReportTool(BaseTool):
    """Tool for generating reports."""
    name: str = "generate_report"
    description: str = "Generates PDF report and outreach message"

    def _run(self, lead_data: str, pitch: str, score: str) -> str:
        """Run the report generation tool."""
        from agents.reporter import ReporterAgent
        from models import Lead
        import json

        lead = Lead.from_dict(json.loads(lead_data))
        score_dict = json.loads(score)

        agent = ReporterAgent()
        report = agent.run(
            lead=lead,
            audit=None,
            score=score_dict.get("total_score", 0),
            classification=score_dict.get("classification", "low"),
            pitch=pitch,
            lead_type="no_website" if not lead.website_url else "has_website",
        )

        return f"Report generated: {report.pdf_path}"


def create_scraper_crew() -> Crew:
    """Create crew for scraping leads."""
    scraping_tool = ScrapingTool()

    scraper = Agent(
        role="Lead Scraper",
        goal="Find potential clients from Google Maps and social media",
        backstory="You are an expert at finding businesses that need website services.",
        tools=[scraping_tool],
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    task = Task(
        description="Scrape 50 leads from Google Maps in Pimpri-Chinchwad, Pune. "
                    "Focus on: restaurants, clinics, shops, salons, gyms. "
                    "Collect: business name, phone, address, rating, reviews, website.",
        agent=scraper,
        expected_output="List of 50 lead objects in JSON format",
    )

    return Crew(
        agents=[scraper],
        tasks=[task],
        process=Process.sequential,
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )


def create_qualifier_crew() -> Crew:
    """Create crew for qualifying leads."""
    qualification_tool = QualificationTool()

    qualifier = Agent(
        role="Lead Qualifier",
        goal="Filter leads based on quality and match to ICP",
        backstory="You are an expert at evaluating business leads for sales potential.",
        tools=[qualification_tool],
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    task = Task(
        description="Filter the scraped leads. Keep only those with: "
                    "3+ reviews, 3+ star rating, in target locations. "
                    "Remove duplicates and closed businesses.",
        agent=qualifier,
        expected_output="Filtered list of qualified leads with status tags",
    )

    return Crew(
        agents=[qualifier],
        tasks=[task],
        process=Process.sequential,
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )


def create_auditor_crew() -> Crew:
    """Create crew for auditing websites."""
    audit_tool = AuditTool()

    auditor = Agent(
        role="Website Auditor",
        goal="Analyze websites and identify improvement opportunities",
        backstory="You are an expert at technical website analysis and SEO.",
        tools=[audit_tool],
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    task = Task(
        description="Audit each website. Check: page speed, mobile friendly, "
                    "SEO score, broken links, design quality, tech stack. "
                    "Return audit scores and recommendations.",
        agent=auditor,
        expected_output="Audit reports with scores for each website",
    )

    return Crew(
        agents=[auditor],
        tasks=[task],
        process=Process.sequential,
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )


def create_pitch_crew() -> Crew:
    """Create crew for generating pitches."""
    pitch_tool = PitchTool()
    scoring_tool = ScoringTool()

    scorer = Agent(
        role="Lead Scorer",
        goal="Calculate opportunity scores for leads",
        backstory="You are an expert at scoring business potential.",
        tools=[scoring_tool],
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    pitcher = Agent(
        role="Pitch Generator",
        goal="Generate compelling sales pitches for leads",
        backstory="You are an expert at creating personalized sales messages.",
        tools=[pitch_tool],
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    score_task = Task(
        description="Score all qualified leads based on audit results and business signals.",
        agent=scorer,
        expected_output="Prioritized list with scores (high/medium/low)",
    )

    pitch_task = Task(
        description="Generate personalized pitch for each high and medium priority lead. "
                    "For no-website leads: emphasize online visibility. "
                    "For has-website leads: emphasize improvements.",
        agent=pitcher,
        expected_output="Pitch content for each lead in markdown format",
    )

    return Crew(
        agents=[scorer, pitcher],
        tasks=[score_task, pitch_task],
        process=Process.sequential,
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )


def create_full_pipeline_crew() -> Crew:
    """Create a complete pipeline crew with all roles."""

    # Create tools
    scraping_tool = ScrapingTool()
    qualification_tool = QualificationTool()
    audit_tool = AuditTool()
    scoring_tool = ScoringTool()
    pitch_tool = PitchTool()
    report_tool = ReportTool()

    # Create agents
    scraper = Agent(
        role="Lead Scraper",
        goal="Find potential clients from Google Maps and social media",
        backstory="Expert at finding businesses that need website services.",
        tools=[scraping_tool],
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    qualifier = Agent(
        role="Lead Qualifier",
        goal="Filter leads based on quality and match to ICP",
        backstory="Expert at evaluating business leads for sales potential.",
        tools=[qualification_tool],
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    auditor = Agent(
        role="Website Auditor",
        goal="Analyze websites and identify improvement opportunities",
        backstory="Expert at technical website analysis and SEO.",
        tools=[audit_tool],
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    scorer = Agent(
        role="Lead Scorer",
        goal="Calculate opportunity scores for leads",
        backstory="Expert at scoring business potential.",
        tools=[scoring_tool],
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    pitcher = Agent(
        role="Pitch Generator",
        goal="Generate compelling sales pitches for leads",
        backstory="Expert at creating personalized sales messages.",
        tools=[pitch_tool],
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    reporter = Agent(
        role="Report Generator",
        goal="Generate PDF reports and outreach messages",
        backstory="Expert at creating professional sales reports.",
        tools=[report_tool],
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    # Create tasks
    scrape_task = Task(
        description="Scrape 50 leads from Google Maps in Pimpri-Chinchwad, Pune. "
                    "Focus on: restaurants, clinics, shops, salons, gyms.",
        agent=scraper,
        expected_output="List of 50 lead objects",
    )

    qualify_task = Task(
        description="Filter leads based on ICP criteria",
        agent=qualifier,
        expected_output="Filtered qualified leads",
        depends_on=[scrape_task],
    )

    audit_task = Task(
        description="Audit websites and social media presence",
        agent=auditor,
        expected_output="Audit reports with scores",
        depends_on=[qualify_task],
    )

    score_task = Task(
        description="Score and prioritize all leads",
        agent=scorer,
        expected_output="Prioritized lead list with scores",
        depends_on=[audit_task],
    )

    pitch_task = Task(
        description="Generate personalized pitches for high/medium priority leads",
        agent=pitcher,
        expected_output="Pitch content in markdown",
        depends_on=[score_task],
    )

    report_task = Task(
        description="Generate final reports and outreach messages",
        agent=reporter,
        expected_output="PDF reports ready for sending",
        depends_on=[pitch_task],
    )

    # Create crew
    crew = Crew(
        agents=[scraper, qualifier, auditor, scorer, pitcher, reporter],
        tasks=[scrape_task, qualify_task, audit_task, score_task, pitch_task, report_task],
        process=Process.sequential,
        verbose=CREWAI_SETTINGS.get("verbose", True),
    )

    return crew


def run_crew_async(crew: Crew, inputs: dict):
    """Run crew asynchronously."""
    return crew.kickoff(inputs)


def run_crew_sync(crew: Crew, inputs: dict):
    """Run crew synchronously."""
    import asyncio
    return asyncio.run(run_crew_async(crew, inputs))
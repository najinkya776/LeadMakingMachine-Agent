"""LangGraph state machine for pipeline orchestration."""

from typing import TypedDict, List, Optional, Dict, Any
from enum import Enum

from langgraph.graph import StateGraph, END


class PipelineStep(str, Enum):
    """Pipeline execution steps."""
    IDLE = "idle"
    SCRAPE = "scrape"
    ENRICH_SOCIAL = "enrich_social"
    QUALIFY = "qualify"
    AUDIT = "audit"
    SEO_ANALYZE = "seo_analyze"
    SCORE = "score"
    PITCH = "pitch"
    REPORT = "report"
    COMPLETE = "complete"
    ERROR = "error"


class PipelineState(TypedDict):
    """State schema for the LangGraph pipeline."""
    # Configuration
    location: str
    categories: List[str]
    max_leads: int

    # Execution tracking
    current_step: PipelineStep
    completed_steps: List[PipelineStep]

    # Data
    raw_leads: List[Dict]
    leads: List[Dict]
    qualified_leads: List[Dict]
    audits: Dict[str, Dict]
    social_analyses: Dict[str, Dict]
    scores: Dict[str, Dict]
    pitches: Dict[str, str]
    reports: List[Dict]

    # Results
    errors: List[str]
    stats: Dict[str, int]


def create_pipeline_graph():
    """Create the LangGraph state machine for pipeline execution."""

    # Define the graph
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("scrape", scrape_node)
    graph.add_node("enrich_social", enrich_social_node)
    graph.add_node("qualify", qualify_node)
    graph.add_node("audit", audit_node)
    graph.add_node("seo_analyze", seo_analyze_node)
    graph.add_node("score", score_node)
    graph.add_node("pitch", pitch_node)
    graph.add_node("report", report_node)
    graph.add_node("complete", complete_node)
    graph.add_node("error", error_node)

    # Define edges
    graph.add_edge("scrape", "enrich_social")
    graph.add_edge("enrich_social", "qualify")
    graph.add_edge("qualify", "audit")
    graph.add_edge("audit", "seo_analyze")
    graph.add_edge("seo_analyze", "score")
    graph.add_edge("score", "pitch")
    graph.add_edge("pitch", "report")
    graph.add_edge("report", "complete")

    # Conditional routing for errors
    graph.add_conditional_edges(
        "scrape",
        lambda s: "error" if s.get("errors") else "enrich_social",
        {"error": "error", "enrich_social": "enrich_social"}
    )

    # Set entry point
    graph.set_entry_point("scrape")

    # Set finish point
    graph.add_edge("complete", END)
    graph.add_edge("error", END)

    return graph.compile()


async def scrape_node(state: PipelineState) -> PipelineState:
    """Scrape leads from Google Maps."""
    from agents.scraper_primary import ScraperPrimaryAgent

    print(f"[Graph] Scraping leads from {state['location']}")

    try:
        agent = ScraperPrimaryAgent()
        leads = agent.run(
            location=state["location"],
            categories=state["categories"],
            count=state["max_leads"],
        )

        state["raw_leads"] = [lead.to_dict() for lead in leads]
        state["leads"] = state["raw_leads"].copy()
        state["current_step"] = PipelineStep.SCRAPE
        state["completed_steps"].append(PipelineStep.SCRAPE)
        state["stats"]["scraped"] = len(leads)

        print(f"[Graph] Scraped {len(leads)} leads")

    except Exception as e:
        state["errors"].append(f"Scraping failed: {str(e)}")
        print(f"[Graph] Error in scraping: {e}")

    return state


async def enrich_social_node(state: PipelineState) -> PipelineState:
    """Enrich leads with social media data."""
    from agents.scraper_social import ScraperSocialAgent
    from models import Lead

    print(f"[Graph] Enriching with social media data")

    try:
        agent = ScraperSocialAgent()
        lead_objects = [Lead.from_dict(l) for l in state["leads"]]
        enriched = agent.run(lead_objects)

        state["leads"] = [lead.to_dict() for lead in enriched]
        state["current_step"] = PipelineStep.ENRICH_SOCIAL
        state["completed_steps"].append(PipelineStep.ENRICH_SOCIAL)

        print(f"[Graph] Social enrichment complete")

    except Exception as e:
        state["errors"].append(f"Social enrichment failed: {str(e)}")
        print(f"[Graph] Error in social enrichment: {e}")

    return state


async def qualify_node(state: PipelineState) -> PipelineState:
    """Qualify and filter leads."""
    from agents.qualifier import QualifierAgent
    from models import Lead

    print(f"[Graph] Qualifying leads")

    try:
        agent = QualifierAgent()
        lead_objects = [Lead.from_dict(l) for l in state["leads"]]
        qualified = agent.run(lead_objects)

        state["qualified_leads"] = [lead.to_dict() for lead in qualified]
        state["leads"] = state["qualified_leads"].copy()  # Update leads to qualified only
        state["current_step"] = PipelineStep.QUALIFY
        state["completed_steps"].append(PipelineStep.QUALIFY)
        state["stats"]["qualified"] = len(qualified)

        print(f"[Graph] Qualified {len(qualified)} leads")

    except Exception as e:
        state["errors"].append(f"Qualification failed: {str(e)}")
        print(f"[Graph] Error in qualification: {e}")

    return state


async def audit_node(state: PipelineState) -> PipelineState:
    """Audit websites of qualified leads."""
    from agents.auditor import AuditorAgent
    from models import Lead

    print(f"[Graph] Auditing websites")

    try:
        agent = AuditorAgent()
        audits = {}
        lead_objects = [Lead.from_dict(l) for l in state["qualified_leads"]]

        for lead in lead_objects:
            if lead.website_url:
                audit = agent.run(lead)
                if audit:
                    audits[lead.id] = audit.to_dict()

        state["audits"] = audits
        state["current_step"] = PipelineStep.AUDIT
        state["completed_steps"].append(PipelineStep.AUDIT)
        state["stats"]["audited"] = len(audits)

        print(f"[Graph] Completed {len(audits)} audits")

    except Exception as e:
        state["errors"].append(f"Audit failed: {str(e)}")
        print(f"[Graph] Error in audit: {e}")

    return state


async def seo_analyze_node(state: PipelineState) -> PipelineState:
    """Perform SEO analysis on audits."""
    from agents.seo_auditor import SEOAuditorAgent
    from models import Audit

    print(f"[Graph] SEO analysis")

    try:
        agent = SEOAuditorAgent()

        for lead_id, audit_dict in state["audits"].items():
            audit = Audit.from_dict(audit_dict)
            enhanced = agent.run(audit)
            state["audits"][lead_id] = enhanced.to_dict()

        state["current_step"] = PipelineStep.SEO_ANALYZE
        state["completed_steps"].append(PipelineStep.SEO_ANALYZE)

        print(f"[Graph] SEO analysis complete")

    except Exception as e:
        state["errors"].append(f"SEO analysis failed: {str(e)}")
        print(f"[Graph] Error in SEO analysis: {e}")

    return state


async def score_node(state: PipelineState) -> PipelineState:
    """Score leads based on all data."""
    from agents.scorer import ScorerAgent
    from agents.social_analyzer import SocialAnalyzerAgent
    from models import Lead, Audit

    print(f"[Graph] Scoring leads")

    try:
        scorer = ScorerAgent()
        social_analyzer = SocialAnalyzerAgent()
        scores = {}
        social_analyses = {}

        for lead_dict in state["qualified_leads"]:
            lead = Lead.from_dict(lead_dict)
            audit = Audit.from_dict(state["audits"].get(lead.id, {})) if lead.id in state["audits"] else None
            social_analysis = social_analyzer.run(lead)
            social_analyses[lead.id] = social_analysis

            score = scorer.run(lead, audit, social_analysis)
            scores[lead.id] = {
                "total_score": score.total_score,
                "classification": score.classification,
                "audit_score": score.audit_score,
                "seo_score": score.seo_score,
                "social_score": score.social_score,
                "business_score": score.business_score,
            }

        state["scores"] = scores
        state["social_analyses"] = social_analyses
        state["current_step"] = PipelineStep.SCORE
        state["completed_steps"].append(PipelineStep.SCORE)
        state["stats"]["scored"] = len(scores)

        print(f"[Graph] Scored {len(scores)} leads")

    except Exception as e:
        state["errors"].append(f"Scoring failed: {str(e)}")
        print(f"[Graph] Error in scoring: {e}")

    return state


async def pitch_node(state: PipelineState) -> PipelineState:
    """Generate pitches for leads."""
    from agents.pitch_no_website import PitchNoWebsiteAgent
    from agents.pitch_has_website import PitchHasWebsiteAgent
    from models import Lead, Audit

    print(f"[Graph] Generating pitches")

    try:
        pitch_no_web = PitchNoWebsiteAgent()
        pitch_has_web = PitchHasWebsiteAgent()
        pitches = {}

        for lead_dict in state["qualified_leads"]:
            lead = Lead.from_dict(lead_dict)
            score = state["scores"].get(lead.id, {})

            if score.get("total_score", 0) < 50:
                continue  # Skip low-scoring leads

            audit = Audit.from_dict(state["audits"].get(lead.id, {})) if lead.id in state["audits"] else None
            social = state["social_analyses"].get(lead.id)

            if not lead.website_url:
                pitch = pitch_no_web.run(lead, social)
            else:
                pitch = pitch_has_web.run(lead, audit)

            pitches[lead.id] = pitch

        state["pitches"] = pitches
        state["current_step"] = PipelineStep.PITCH
        state["completed_steps"].append(PipelineStep.PITCH)
        state["stats"]["pitched"] = len(pitches)

        print(f"[Graph] Generated {len(pitches)} pitches")

    except Exception as e:
        state["errors"].append(f"Pitch generation failed: {str(e)}")
        print(f"[Graph] Error in pitch generation: {e}")

    return state


async def report_node(state: PipelineState) -> PipelineState:
    """Generate reports for leads."""
    from agents.reporter import ReporterAgent
    from models import Lead, Audit

    print(f"[Graph] Generating reports")

    try:
        agent = ReporterAgent()
        reports = []

        for lead_dict in state["qualified_leads"]:
            lead = Lead.from_dict(lead_dict)
            score = state["scores"].get(lead.id, {})

            if score.get("total_score", 0) < 50:
                continue

            audit = Audit.from_dict(state["audits"].get(lead.id, {})) if lead.id in state["audits"] else None

            report = agent.run(
                lead=lead,
                audit=audit,
                score=score.get("total_score", 0),
                classification=score.get("classification", "low"),
                pitch=state["pitches"].get(lead.id, ""),
                lead_type="no_website" if not lead.website_url else "has_website",
            )

            reports.append(report.to_dict())

        state["reports"] = reports
        state["current_step"] = PipelineStep.REPORT
        state["completed_steps"].append(PipelineStep.REPORT)
        state["stats"]["reports"] = len(reports)

        print(f"[Graph] Generated {len(reports)} reports")

    except Exception as e:
        state["errors"].append(f"Report generation failed: {str(e)}")
        print(f"[Graph] Error in report generation: {e}")

    return state


async def complete_node(state: PipelineState) -> PipelineState:
    """Mark pipeline as complete."""
    state["current_step"] = PipelineStep.COMPLETE
    print(f"[Graph] Pipeline complete!")
    print(f"[Graph] Stats: {state['stats']}")
    return state


async def error_node(state: PipelineState) -> PipelineState:
    """Handle pipeline errors."""
    state["current_step"] = PipelineStep.ERROR
    print(f"[Graph] Pipeline error!")
    print(f"[Graph] Errors: {state['errors']}")
    return state


def create_initial_state(
    location: str = "Pimpri-Chinchwad, Pune, India",
    categories: Optional[List[str]] = None,
    max_leads: int = 50,
) -> PipelineState:
    """Create initial state for the pipeline."""
    from config.settings import ICP

    if categories is None:
        categories = ICP["industries"]

    return PipelineState(
        location=location,
        categories=categories,
        max_leads=max_leads,
        current_step=PipelineStep.IDLE,
        completed_steps=[],
        raw_leads=[],
        leads=[],
        qualified_leads=[],
        audits={},
        social_analyses={},
        scores={},
        pitches={},
        reports=[],
        errors=[],
        stats={
            "scraped": 0,
            "qualified": 0,
            "audited": 0,
            "scored": 0,
            "pitched": 0,
            "reports": 0,
        },
    )


async def run_pipeline_async(
    location: str = "Pimpri-Chinchwad, Pune, India",
    categories: Optional[List[str]] = None,
    max_leads: int = 50,
) -> PipelineState:
    """Run the pipeline asynchronously."""
    graph = create_pipeline_graph()
    initial_state = create_initial_state(location, categories, max_leads)

    result = await graph.ainvoke(initial_state)
    return result


def run_pipeline_sync(
    location: str = "Pimpri-Chinchwad, Pune, India",
    categories: Optional[List[str]] = None,
    max_leads: int = 50,
) -> PipelineState:
    """Run the pipeline synchronously."""
    import asyncio
    return asyncio.run(run_pipeline_async(location, categories, max_leads))
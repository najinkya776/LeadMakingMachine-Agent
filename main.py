#!/usr/bin/env python3
"""LeadMakingMachine - Multi-Agent Lead Generation & Web Audit System."""

import os
import sys
import click
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from config.settings import ICP
from agents.orchestrator import OrchestratorAgent
from pipelines.state_graph import run_pipeline_sync
from pipelines.crew_definition import create_full_pipeline_crew


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """LeadMakingMachine - Multi-Agent Lead Generation & Web Audit System"""
    pass


@cli.command()
@click.option("--location", default="Pimpri-Chinchwad, Pune, India", help="Target location")
@click.option("--count", default=50, help="Number of leads to scrape")
def scrape(location, count):
    """Scrape leads from Google Maps."""
    click.echo(f"Scraping {count} leads from {location}...")

    from agents.scraper_primary import ScraperPrimaryAgent
    agent = ScraperPrimaryAgent()
    leads = agent.run(location=location, count=count)

    click.echo(f"\nScraped {len(leads)} leads:")
    for lead in leads[:10]:
        click.echo(f"  - {lead.business_name} ({lead.category})")
    if len(leads) > 10:
        click.echo(f"  ... and {len(leads) - 10} more")


@cli.command()
@click.option("--location", default="Pimpri-Chinchwad, Pune, India", help="Target location")
@click.option("--count", default=50, help="Number of leads to process")
def run(location, count):
    """Run the full lead generation pipeline."""
    click.echo("=" * 60)
    click.echo("LeadMakingMachine - Full Pipeline")
    click.echo("=" * 60)

    start_time = datetime.now()

    try:
        orchestrator = OrchestratorAgent()
        state = orchestrator.run_full_pipeline(
            location=location,
            categories=ICP["industries"],
            count=count,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        click.echo("\n" + "=" * 60)
        click.echo("Pipeline Complete!")
        click.echo("=" * 60)
        click.echo(f"Total leads: {len(state.leads)}")
        click.echo(f"Qualified: {len(state.qualified_leads)}")
        click.echo(f"Reports: {len(state.reports)}")
        click.echo(f"Duration: {duration:.1f} seconds")
        click.echo(f"Errors: {len(state.errors)}")

        high_priority = orchestrator.get_high_priority_leads()
        if high_priority:
            click.echo(f"\nHigh Priority Leads ({len(high_priority)}):")
            for lead in high_priority[:5]:
                click.echo(f"  - {lead.business_name}")

        if click.confirm("\nExport leads to CSV?"):
            orchestrator.export_leads_csv()
            click.echo("Exported to output/leads_export.csv")

    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--location", default="Pimpri-Chinchwad, Pune, India", help="Target location")
@click.option("--count", default=50, help="Number of leads to process")
def run_langgraph(location, count):
    """Run pipeline using LangGraph state machine."""
    click.echo("Running with LangGraph...")
    state = run_pipeline_sync(location=location, max_leads=count)
    click.echo(f"Pipeline complete! Stats: {state.get('stats')}")


@cli.command()
@click.option("--count", default=50, help="Number of leads to process")
def run_crewai(count):
    """Run pipeline using CrewAI."""
    click.echo("Creating CrewAI crew...")
    crew = create_full_pipeline_crew()
    click.echo("Running crew...")
    result = crew.kickoff(inputs={"max_leads": count})
    click.echo(f"\nCrew result: {result}")


@cli.command()
@click.argument("url")
def audit(url):
    """Audit a single website."""
    click.echo(f"Auditing {url}...")

    from agents.auditor import AuditorAgent
    from models import Lead

    lead = Lead(business_name="Test Business", website_url=url)
    agent = AuditorAgent()
    audit_result = agent.run(lead)

    if audit_result:
        click.echo(f"\nAudit Results:")
        click.echo(f"  Page Speed: {audit_result.page_speed_score}/100")
        click.echo(f"  Mobile Score: {audit_result.mobile_score}/100")
        click.echo(f"  SEO Score: {audit_result.seo_score}/100")
        click.echo(f"  Broken Links: {audit_result.broken_links_count}")
        click.echo(f"  Tech Stack: {audit_result.tech_stack or 'Unknown'}")
        click.echo(f"  Design Quality: {audit_result.design_quality}")
    else:
        click.echo("Audit failed")


@cli.command()
def dashboard():
    """Start the web dashboard."""
    click.echo("Starting web dashboard...")

    try:
        from dashboard.server import app
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8001)
    except Exception as e:
        click.echo(f"Dashboard error: {e}")
        click.echo("Falling back to CLI dashboard...")
        import subprocess
        subprocess.run(["python", "cli_dashboard.py"])


@cli.command()
def apify_status():
    """Check Apify API status."""
    from lib.apify_client import ApifyClient
    client = ApifyClient()

    try:
        import httpx
        click.echo("Checking Apify token...")
        headers = {"Authorization": f"Bearer {client.token}"}
        response = httpx.get("https://api.apify.com/v2/user-info", headers=headers)
        if response.status_code == 200:
            data = response.json()
            click.echo(f"Apify status: OK")
            click.echo(f"User: {data.get('data', {}).get('username', 'Unknown')}")
        else:
            click.echo(f"Apify error: {response.status_code}")
    except Exception as e:
        click.echo(f"Apify check failed: {e}")


@cli.command()
def queue_status():
    """Check Redis queue status."""
    try:
        from db.redis_queue import get_queue
        queue = get_queue()
        stats = queue.get_queue_stats()
        click.echo("Queue Status:")
        for name, count in stats.items():
            click.echo(f"  {name}: {count}")
    except Exception as e:
        click.echo(f"Queue check failed: {e}")


@cli.command()
def reset():
    """Reset the pipeline state."""
    try:
        from db.redis_queue import get_queue
        queue = get_queue()
        queue.reset_counters()
        click.echo("Pipeline state reset")
    except Exception as e:
        click.echo(f"Reset failed: {e}")


@cli.command()
def config():
    """Show current configuration."""
    click.echo("LeadMakingMachine Configuration:")
    click.echo(f"\nICP Locations: {', '.join(ICP['locations'][:5])}...")
    click.echo(f"ICP Industries: {', '.join(ICP['industries'][:5])}...")
    click.echo(f"Min Reviews: {ICP['min_reviews']}")
    click.echo(f"Min Rating: {ICP['min_rating']}")
    click.echo(f"\nScoring Thresholds:")
    click.echo(f"  High: {ICP.get('SCORING', {}).get('high', 80)}+")
    click.echo(f"  Medium: {ICP.get('SCORING', {}).get('medium', 50)}+")


@cli.command()
def test():
    """Run a quick test of the pipeline."""
    click.echo("Running pipeline test...")

    orchestrator = OrchestratorAgent()
    state = orchestrator.run_full_pipeline(
        location="Pimpri-Chinchwad, Pune",
        categories=["restaurant", "clinic"],
        count=5,
    )

    click.echo("\nTest Results:")
    click.echo(f"  Leads scraped: {len(state.leads)}")
    click.echo(f"  Qualified: {len(state.qualified_leads)}")
    click.echo(f"  Reports: {len(state.reports)}")


if __name__ == "__main__":
    cli()
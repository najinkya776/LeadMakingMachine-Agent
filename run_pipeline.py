#!/usr/bin/env python3
"""Run the full Website Pitcher pipeline."""
import os
import sys

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os as _os
import sys as _sys
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

from config.settings import ICP
from agents.orchestrator import OrchestratorAgent
from pipelines.state_graph import run_pipeline_sync


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Website Pitcher - Run the lead generation pipeline"
    )
    parser.add_argument(
        "--location",
        default="Pimpri-Chinchwad, Pune, India",
        help="Target location for scraping"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of leads to process"
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=None,
        help="Business categories to target (default: all ICP categories)"
    )
    parser.add_argument(
        "--engine",
        choices=["orchestrator", "langgraph", "crewai"],
        default="orchestrator",
        help="Pipeline engine to use"
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=0,
        help="Minimum score for report generation"
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export results to CSV"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    return parser.parse_args()


def print_banner():
    """Print the pipeline banner."""
    banner = """
================================================================
   Website Pitcher - Lead Generation & Web Audit System
================================================================
    """
    print(banner)


def print_config(args):
    """Print configuration."""
    print("\n[CONFIG] Configuration:")
    print(f"   Location: {args.location}")
    print(f"   Count: {args.count}")
    print(f"   Categories: {args.categories or ICP['industries'][:3]}...")
    print(f"   Engine: {args.engine}")
    print(f"   Min Score: {args.min_score}")
    print()


def print_progress(step: str, message: str):
    """Print progress message."""
    icons = {
        "scrape": "[SCRAPE]",
        "social": "[SOCIAL]",
        "qualify": "[QUALIFY]",
        "audit": "[AUDIT]",
        "score": "[SCORE]",
        "pitch": "[PITCH]",
        "report": "[REPORT]",
        "complete": "[DONE]",
    }
    icon = icons.get(step, "[>]")
    print(f"   {icon} {message}")


def print_results(state):
    """Print pipeline results."""
    print("\n" + "=" * 70)
    print("[RESULTS] PIPELINE RESULTS")
    print("=" * 70)

    print("\n[STATS] Statistics:")
    print(f"   Total leads scraped:    {len(state.leads)}")
    print(f"   Leads qualified:        {len(state.qualified_leads)}")
    print(f"   Websites audited:       {len(state.audits)}")
    print(f"   Leads scored:           {len(state.scores)}")
    print(f"   Reports generated:      {len(state.reports)}")

    if state.errors:
        print(f"\n[WARNING]  Errors: {len(state.errors)}")
        for error in state.errors[:3]:
            print(f"   - {error}")

    # Classification breakdown
    if state.scores:
        high = sum(1 for s in state.scores.values() if s.classification == "high")
        medium = sum(1 for s in state.scores.values() if s.classification == "medium")
        low = sum(1 for s in state.scores.values() if s.classification == "low")

        print("\n[SCORES] Score Classification:")
        print(f"   High (80+):   {high} leads")
        print(f"   Medium (50-79): {medium} leads")
        print(f"   Low (0-49):    {low} leads")

        # Average score
        if state.scores:
            avg_score = sum(s.total_score for s in state.scores.values()) / len(state.scores)
            print(f"\n   Average Score: {avg_score:.1f}/100")

    print("\n" + "=" * 70)


def main():
    """Main entry point."""
    args = parse_args()

    print_banner()
    print_config(args)

    # Track timing
    start_time = datetime.now()
    print(f"[START] Starting pipeline at {start_time.strftime('%H:%M:%S')}\n")

    try:
        if args.engine == "orchestrator":
            print("[ENGINE] Using Orchestrator Agent...\n")
            orchestrator = OrchestratorAgent()
            state = orchestrator.run_full_pipeline(
                location=args.location,
                categories=args.categories,
                count=args.count,
            )

        elif args.engine == "langgraph":
            print("[ENGINE] Using LangGraph State Machine...\n")
            state = run_pipeline_sync(
                location=args.location,
                categories=args.categories,
                max_leads=args.count,
            )

        elif args.engine == "crewai":
            print("[ENGINE] Using CrewAI...\n")
            from pipelines.crew_definition import create_full_pipeline_crew

            crew = create_full_pipeline_crew()
            result = crew.kickoff(inputs={
                "location": args.location,
                "categories": args.categories,
                "count": args.count,
            })
            print(result)
            return

        # Print results
        print_results(state)

        # Export if requested
        if args.export and hasattr(state, 'leads'):
            orchestrator = OrchestratorAgent()
            orchestrator.state = state
            orchestrator.export_leads_csv("output/leads_export.csv")
            print("\n[EXPORT] Exported to output/leads_export.csv")

        # End timing
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"\n[TIME]  Completed in {duration:.1f} seconds")
        print(f"   Finished at {end_time.strftime('%H:%M:%S')}")

        # Show next steps
        high_priority = len([s for s in (state.scores or {}).values() if s.classification == "high"])
        if high_priority > 0:
            print(f"\n[TIP] Next: Review {high_priority} high-priority leads in output/reports/")

    except KeyboardInterrupt:
        print("\n\n[WARNING]  Pipeline interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
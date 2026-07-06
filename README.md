# LeadMakingMachine - Multi-Agent Lead Generation & Web Audit System

Automated pipeline for finding local businesses, auditing their digital presence, and generating personalized outreach reports with multi-agent AI orchestration.

## Features

- 10 specialized AI agents working in coordination
- Google Maps + social media scraping via Apify
- Website auditing with PageSpeed and SEO analysis
- AI-powered lead scoring and pitch generation
- PDF reports and email outreach automation
- Web dashboard for real-time monitoring
- SQLite + Redis for state management

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
copy .env.example .env
# Edit .env with your API keys

# Run the pipeline
python main.py run

# Or use batch file
run.bat
```

## Commands

```bash
# Full pipeline
python main.py run --count 50

# Scrape leads only
python main.py scrape --count 100

# Audit single website
python main.py audit https://example.com

# Start web dashboard
python main.py dashboard

# Test with 5 leads
python main.py test

# Show configuration
python main.py config
```

## Architecture

```
Orchestrator (CrewAI + LangGraph)
    ├── Scraper Agents (Primary + Social)
    ├── Qualifier Agent
    ├── Auditor Agents (Website + SEO + Social)
    ├── Scorer Agent
    ├── Pitch Agents (No-Website + Has-Website)
    └── Reporter Agent
```

## Configuration

Edit `config/settings.py` to customize:
- Target locations (default: Pimpri-Chinchwad, Pune)
- Business categories to target
- ICP (Ideal Customer Profile) filters
- Scoring thresholds

## Project Structure

```
LeadMakingMachine/
    agents/           # AI agent implementations
    config/           # Settings and configuration
    db/               # Database models (SQLite + Redis)
    dashboard/        # Web dashboard (FastAPI)
    lib/              # Utility libraries
    models/           # Pydantic data models
    pipelines/        # LangGraph state machines
    output/           # Generated reports
    main.py           # CLI entry point
    run.bat           # Quick run script
```

## License

MIT
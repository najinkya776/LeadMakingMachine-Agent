from typing import Optional

from pydantic import BaseModel


class PipelineStatus(BaseModel):
    is_running: bool = False
    current_step: Optional[str] = None
    leads_scraped: int = 0
    leads_qualified: int = 0
    leads_scored: int = 0
    reports_generated: int = 0
    errors: int = 0


class StatsResponse(BaseModel):
    total_leads: int = 0
    qualified_leads: int = 0
    high_priority: int = 0
    reports_generated: int = 0
    avg_score: float = 0.0
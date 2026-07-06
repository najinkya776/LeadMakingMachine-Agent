from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class RunResponse(BaseModel):
    id: int
    status: str
    location: str
    count: int
    leads_processed: int = 0
    current_step: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class RunListResponse(BaseModel):
    runs: List[RunResponse]
    total: int


class RunCreate(BaseModel):
    location: str
    count: int = Field(ge=1, le=100, default=50)
    categories: Optional[List[str]] = None
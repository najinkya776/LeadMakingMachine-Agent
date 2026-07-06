"""Pipeline runs API endpoints."""

from datetime import datetime
from typing import Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


router = APIRouter(prefix="/api/runs", tags=["runs"])


# =============================================================================
# Status Enums
# =============================================================================

class RunStatus(str, Enum):
    """Pipeline run status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# Request Schemas
# =============================================================================

class CreateRunRequest(BaseModel):
    """Request body for creating a new pipeline run."""
    location: str = Field(..., description="Target location for lead scraping")
    count: int = Field(default=50, ge=1, le=500, description="Number of leads to scrape")
    categories: list[str] = Field(
        default=["restaurant", "clinic", "salon", "gym", "shop"],
        description="Business categories to target"
    )


# =============================================================================
# Response Schemas
# =============================================================================

class PipelineRunResponse(BaseModel):
    """Pipeline run response schema."""
    id: str
    location: str
    categories: list[str]
    target_count: int
    status: str
    leads_scraped: int = 0
    leads_qualified: int = 0
    leads_processed: int = 0
    reports_generated: int = 0
    error_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None


class RunListResponse(BaseModel):
    """Paginated run list response."""
    runs: list[PipelineRunResponse]
    total: int
    limit: int
    offset: int


# =============================================================================
# Redis Queue Operations
# =============================================================================

def get_redis_connection():
    """Get Redis connection."""
    import redis
    from config.database import REDIS_CONFIG
    return redis.Redis(**REDIS_CONFIG)


def run_pipeline_in_background(run_id: str, location: str, count: int, categories: list[str]):
    """Execute pipeline run in background thread."""
    import threading
    import traceback

    def execute():
        try:
            r = get_redis_connection()

            # Update status to running
            r.hset(f"run:{run_id}", mapping={
                "status": "running",
                "started_at": datetime.utcnow().isoformat(),
            })

            # Import pipeline components
            from agents.orchestrator import OrchestratorAgent

            agent = OrchestratorAgent()
            state = agent.run_full_pipeline(
                location=location,
                categories=categories,
                count=count,
            )

            # Calculate duration
            started = r.hget(f"run:{run_id}", "started_at")
            duration = (datetime.utcnow() - datetime.fromisoformat(started)).total_seconds()

            # Update final results
            r.hset(f"run:{run_id}", mapping={
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "duration_seconds": duration,
                "leads_scraped": len(state.leads),
                "leads_qualified": len(state.qualified_leads),
                "reports_generated": len(state.reports),
                "error_count": len(state.errors),
            })

        except Exception as e:
            r.hset(f"run:{run_id}", mapping={
                "status": "failed",
                "completed_at": datetime.utcnow().isoformat(),
                "error_message": f"{type(e).__name__}: {str(e)}",
            })

    thread = threading.Thread(target=execute)
    thread.daemon = True
    thread.start()


# =============================================================================
# Database/Redis Helpers
# =============================================================================

def get_runs_from_redis(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
) -> tuple[list[dict], int]:
    """Fetch pipeline runs from Redis."""
    try:
        r = get_redis_connection()

        # Get all run keys
        run_keys = sorted(
            [k.decode() for k in r.keys("run:*") if not k.decode().endswith(":status")],
            reverse=True
        )

        # Filter by status if provided
        if status:
            run_keys = [k for k in run_keys if r.hget(k, "status").decode() == status]

        total = len(run_keys)

        # Apply pagination
        paginated_keys = run_keys[offset:offset + limit]

        runs = []
        for key in paginated_keys:
            data = r.hgetall(key)
            run_data = {k.decode(): v.decode() if v else None for k, v in data.items()}
            run_data["id"] = key.replace("run:", "")
            runs.append(run_data)

        return runs, total

    except Exception as e:
        return [], 0


def get_run_from_redis(run_id: str) -> Optional[dict]:
    """Get a single run from Redis."""
    try:
        r = get_redis_connection()
        data = r.hgetall(f"run:{run_id}")

        if not data:
            return None

        run_data = {k.decode(): v.decode() if v else None for k, v in data.items()}
        run_data["id"] = run_id

        # Calculate duration if completed
        if run_data.get("started_at") and run_data.get("completed_at"):
            started = datetime.fromisoformat(run_data["started_at"])
            completed = datetime.fromisoformat(run_data["completed_at"])
            run_data["duration_seconds"] = (completed - started).total_seconds()

        return run_data

    except Exception:
        return None


def create_run_in_redis(run_id: str, location: str, count: int, categories: list[str]) -> dict:
    """Create a new pipeline run in Redis."""
    r = get_redis_connection()

    r.hset(f"run:{run_id}", mapping={
        "id": run_id,
        "location": location,
        "categories": ",".join(categories),
        "target_count": count,
        "status": "pending",
        "leads_scraped": 0,
        "leads_qualified": 0,
        "leads_processed": 0,
        "reports_generated": 0,
        "error_count": 0,
        "created_at": datetime.utcnow().isoformat(),
    })

    return {
        "id": run_id,
        "location": location,
        "categories": categories,
        "target_count": count,
        "status": "pending",
    }


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=RunListResponse)
def list_runs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None, description="Filter by status"),
):
    """List all pipeline runs with pagination."""
    runs, total = get_runs_from_redis(limit=limit, offset=offset, status=status)

    return RunListResponse(
        runs=[
            PipelineRunResponse(
                id=run["id"],
                location=run.get("location", ""),
                categories=run.get("categories", "").split(",") if run.get("categories") else [],
                target_count=int(run.get("target_count", 0)),
                status=run.get("status", "unknown"),
                leads_scraped=int(run.get("leads_scraped", 0)),
                leads_qualified=int(run.get("leads_qualified", 0)),
                leads_processed=int(run.get("leads_processed", 0)),
                reports_generated=int(run.get("reports_generated", 0)),
                error_count=int(run.get("error_count", 0)),
                started_at=datetime.fromisoformat(run["started_at"]) if run.get("started_at") else None,
                completed_at=datetime.fromisoformat(run["completed_at"]) if run.get("completed_at") else None,
                duration_seconds=float(run["duration_seconds"]) if run.get("duration_seconds") else None,
                error_message=run.get("error_message"),
            )
            for run in runs
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=PipelineRunResponse, status_code=201)
def create_run(request: CreateRunRequest):
    """Start a new pipeline run."""
    import uuid

    run_id = str(uuid.uuid4())

    # Create run record
    run_data = create_run_in_redis(
        run_id=run_id,
        location=request.location,
        count=request.count,
        categories=request.categories,
    )

    # Start background execution
    run_pipeline_in_background(
        run_id=run_id,
        location=request.location,
        count=request.count,
        categories=request.categories,
    )

    return PipelineRunResponse(
        id=run_id,
        location=request.location,
        categories=request.categories,
        target_count=request.count,
        status="pending",
        leads_scraped=0,
        leads_qualified=0,
        leads_processed=0,
        reports_generated=0,
        error_count=0,
        started_at=None,
        completed_at=None,
        duration_seconds=None,
        error_message=None,
    )


@router.get("/{run_id}", response_model=PipelineRunResponse)
def get_run(run_id: str):
    """Get pipeline run status and details."""
    run_data = get_run_from_redis(run_id)

    if not run_data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return PipelineRunResponse(
        id=run_data["id"],
        location=run_data.get("location", ""),
        categories=run_data.get("categories", "").split(",") if run_data.get("categories") else [],
        target_count=int(run_data.get("target_count", 0)),
        status=run_data.get("status", "unknown"),
        leads_scraped=int(run_data.get("leads_scraped", 0)),
        leads_qualified=int(run_data.get("leads_qualified", 0)),
        leads_processed=int(run_data.get("leads_processed", 0)),
        reports_generated=int(run_data.get("reports_generated", 0)),
        error_count=int(run_data.get("error_count", 0)),
        started_at=datetime.fromisoformat(run_data["started_at"]) if run_data.get("started_at") else None,
        completed_at=datetime.fromisoformat(run_data["completed_at"]) if run_data.get("completed_at") else None,
        duration_seconds=float(run_data["duration_seconds"]) if run_data.get("duration_seconds") else None,
        error_message=run_data.get("error_message"),
    )


@router.post("/{run_id}/cancel", response_model=PipelineRunResponse)
def cancel_run(run_id: str):
    """Cancel a running pipeline run."""
    run_data = get_run_from_redis(run_id)

    if not run_data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if run_data.get("status") not in ["pending", "running"]:
        raise HTTPException(status_code=400, detail="Can only cancel pending or running runs")

    r = get_redis_connection()
    r.hset(f"run:{run_id}", mapping={
        "status": "cancelled",
        "completed_at": datetime.utcnow().isoformat(),
    })

    run_data["status"] = "cancelled"
    run_data["completed_at"] = datetime.utcnow()

    return PipelineRunResponse(
        id=run_data["id"],
        location=run_data.get("location", ""),
        categories=run_data.get("categories", "").split(",") if run_data.get("categories") else [],
        target_count=int(run_data.get("target_count", 0)),
        status="cancelled",
        leads_scraped=int(run_data.get("leads_scraped", 0)),
        leads_qualified=int(run_data.get("leads_qualified", 0)),
        leads_processed=int(run_data.get("leads_processed", 0)),
        reports_generated=int(run_data.get("reports_generated", 0)),
        error_count=int(run_data.get("error_count", 0)),
        started_at=datetime.fromisoformat(run_data["started_at"]) if run_data.get("started_at") else None,
        completed_at=datetime.fromisoformat(run_data["completed_at"]) if run_data.get("completed_at") else None,
        duration_seconds=float(run_data["duration_seconds"]) if run_data.get("duration_seconds") else None,
        error_message=run_data.get("error_message"),
    )
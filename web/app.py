#!/usr/bin/env python3
"""Lead Harvester Web UI.

A small, self-contained FastAPI app for harvesting no-website businesses by region
and downloading the result as Excel. Runs independently of the main pipeline
dashboard so it stays easy to manage.

Run:
    python -m web.app
    # or
    uvicorn web.app:app --port 8200

Then open http://localhost:8200
"""
import os
import sys
import threading
import uuid
from pathlib import Path

# Project root on path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config.settings import ICP
from config.regions import REGIONS, get_locations, list_regions_grouped
from harvest_no_website_leads import run_harvest, WEBSITE_FILTERS, FILTER_NO_WEBSITE

app = FastAPI(title="Lead Harvester")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# -----------------------------------------------------------------------------
# In-memory job store (single-process; fine for a local tool)
# -----------------------------------------------------------------------------
_jobs = {}
_jobs_lock = threading.Lock()


def _set_job(job_id, **fields):
    with _jobs_lock:
        job = _jobs.setdefault(job_id, {})
        job.update(fields)


def _get_job(job_id):
    with _jobs_lock:
        return dict(_jobs.get(job_id, {}))


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class HarvestRequest(BaseModel):
    region: str = Field(..., description="Region key from /api/regions")
    categories: list[str] = Field(default_factory=list)
    count: int = Field(default=80, ge=5, le=2000)
    guess_emails: bool = False
    website_filter: str = Field(default=FILTER_NO_WEBSITE)


# -----------------------------------------------------------------------------
# Background worker
# -----------------------------------------------------------------------------
def _run_job(job_id, region_key, categories, count, guess_emails, website_filter):
    region = REGIONS[region_key]
    locations = get_locations(region_key)

    def progress(p):
        _set_job(job_id, phase=p.get("phase"), message=p.get("message", ""))

    _set_job(job_id, status="running", phase="starting",
             message=f"Harvesting {region['label']} ({len(locations)} cities)...")
    try:
        summary = run_harvest(
            locations=locations,
            categories=categories or ICP["industries"],
            count=count,
            region_label=region["label"],
            guess_emails=guess_emails,
            output_path=None,
            website_filter=website_filter,
            progress=progress,
        )
        # Strip the heavy 'rows' payload but keep a small preview.
        preview = summary["rows"][:25]
        result = {k: v for k, v in summary.items() if k != "rows"}
        result["preview"] = preview
        result["filename"] = os.path.basename(summary["output_path"]) if summary["output_path"] else None
        _set_job(job_id, status="done", phase="done",
                 message="Harvest complete", result=result)
    except Exception as e:
        _set_job(job_id, status="error", phase="error", message=str(e))


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/regions")
def api_regions():
    return list_regions_grouped()


@app.get("/api/categories")
def api_categories():
    return {"categories": ICP["industries"]}


@app.post("/api/harvest")
def api_harvest(req: HarvestRequest):
    if req.region not in REGIONS:
        raise HTTPException(status_code=400, detail=f"Unknown region: {req.region}")
    if req.website_filter not in WEBSITE_FILTERS:
        raise HTTPException(status_code=400, detail=f"Unknown website_filter: {req.website_filter}")
    job_id = uuid.uuid4().hex[:12]
    _set_job(job_id, status="queued", phase="queued", message="Queued", result=None)
    t = threading.Thread(
        target=_run_job,
        args=(job_id, req.region, req.categories, req.count, req.guess_emails, req.website_filter),
        daemon=True,
    )
    t.start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def api_job(job_id):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    return job


@app.get("/api/download/{job_id}")
def api_download(job_id):
    job = _get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(status_code=404, detail="No file for this job")
    result = job.get("result") or {}
    filename = result.get("filename")
    if not filename:
        raise HTTPException(status_code=404, detail="No file produced (0 leads)")
    path = ROOT / "output" / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("HARVESTER_PORT", "8200"))
    print(f"\n  Lead Harvester UI  ->  http://localhost:{port}\n")
    uvicorn.run(app, host="127.0.0.1", port=port)

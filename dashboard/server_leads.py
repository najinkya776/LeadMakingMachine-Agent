"""Lead Tracking Dashboard API Server."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocket
import uvicorn

from dashboard.api.leads_tracking import router as leads_router
from dashboard.ws_manager import ws_manager

app = FastAPI(
    title="PrismaticWorks Lead Tracker",
    description="Track cold email leads through the entire pipeline",
    version="1.0.0"
)

# CORS for React dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:5174",
                  "http://127.0.0.1:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(leads_router)

@app.get("/")
async def root():
    return {
        "service": "PrismaticWorks Lead Tracker",
        "version": "1.0.0",
        "endpoints": {
            "leads": "/api/leads",
            "stats": "/api/leads/stats",
            "untouched": "/api/leads/untouched",
            "followup": "/api/leads/needs-followup",
            "search": "/api/leads/search"
        }
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, receive any client messages
            data = await websocket.receive_text()
            # Echo back as acknowledgment (optional)
            if data == "ping":
                await websocket.send_text("pong")
    except Exception:
        pass
    finally:
        ws_manager.disconnect(websocket)

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PrismaticWorks Lead Tracker API")
    print("  Server: http://localhost:8002")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8002)

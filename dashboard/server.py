from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import asyncio

from dashboard.websocket_manager import WebSocketManager, start_redis_subscriber

manager = WebSocketManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(start_redis_subscriber(manager))
    yield
    task.cancel()

app = FastAPI(title="Website Pitcher Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

from dashboard.api import leads, runs, stats, inbound, orders, webhooks, funnel, leads_tracking
app.include_router(leads.router)
app.include_router(runs.router)
app.include_router(stats.router)
app.include_router(inbound.router)
app.include_router(orders.router)
app.include_router(webhooks.router)
app.include_router(funnel.router)
app.include_router(leads_tracking.router)
app.include_router(leads_tracking.campaign_router)

@app.get("/")
async def root():
    return FileResponse("dashboard/static/index.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

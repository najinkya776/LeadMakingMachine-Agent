import redis.asyncio as aioredis
import json
from fastapi import WebSocket
from typing import List

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.redis_client = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(event)
            except:
                pass

async def start_redis_subscriber(manager: WebSocketManager):
    try:
        manager.redis_client = await aioredis.from_url("redis://localhost:6379")
        pubsub = manager.redis_client.pubsub()
        await pubsub.subscribe("website_pitcher_events")

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await manager.broadcast(data)
    except Exception as e:
        print(f"Redis subscriber error: {e}")

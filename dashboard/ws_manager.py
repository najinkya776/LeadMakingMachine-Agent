"""WebSocket manager for real-time lead updates."""

import json
import asyncio
from typing import Set
from fastapi import WebSocket


class WebSocketManager:
    """Manages WebSocket connections and broadcasts updates to all clients."""

    def __init__(self):
        """Initialize the manager with empty client set."""
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"WebSocket connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        print(f"WebSocket disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: dict):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return

        message = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        })

        # Send to all connected clients, removing any that fail
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Failed to send to client: {e}")
                disconnected.add(connection)

        # Clean up failed connections
        for conn in disconnected:
            self.active_connections.discard(conn)

    # Event-specific broadcast methods
    async def broadcast_lead_created(self, lead_id: int, lead_data: dict):
        """Broadcast when a new lead is created."""
        await self.broadcast("lead_created", {
            "lead_id": lead_id,
            "lead": lead_data
        })

    async def broadcast_lead_updated(self, lead_id: int, lead_data: dict):
        """Broadcast when a lead is updated (status change, etc.)."""
        await self.broadcast("lead_updated", {
            "lead_id": lead_id,
            "lead": lead_data
        })

    async def broadcast_lead_deleted(self, lead_id: int):
        """Broadcast when a lead is deleted."""
        await self.broadcast("lead_deleted", {"lead_id": lead_id})

    async def broadcast_email_sent(self, lead_id: int, email_data: dict):
        """Broadcast when an email is recorded as sent."""
        await self.broadcast("email_sent", {
            "lead_id": lead_id,
            "email": email_data
        })

    async def broadcast_response_recorded(self, lead_id: int, response_data: dict):
        """Broadcast when a response is recorded."""
        await self.broadcast("response_recorded", {
            "lead_id": lead_id,
            "response": response_data
        })

    async def broadcast_stats_updated(self, stats: dict):
        """Broadcast when stats are updated."""
        await self.broadcast("stats_updated", stats)


# Global WebSocket manager instance
ws_manager = WebSocketManager()

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import WebSocket


class WebSocketManager:
    """Manages WebSocket connections per user for real-time event broadcasting."""

    def __init__(self):
        # user_id -> list of active WebSocket connections
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        if user_id in self._connections:
            self._connections[user_id] = [
                ws for ws in self._connections[user_id] if ws != websocket
            ]
            if not self._connections[user_id]:
                del self._connections[user_id]

    async def send_to_user(self, user_id: str, event: dict) -> None:
        """Send an event to all connections of a specific user."""
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()

        if user_id in self._connections:
            payload = json.dumps(event)
            dead = []
            for ws in self._connections[user_id]:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.disconnect(user_id, ws)

    async def broadcast(self, event: dict, exclude_user: str | None = None) -> None:
        """Broadcast an event to all connected users."""
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()

        for user_id in list(self._connections.keys()):
            if user_id != exclude_user:
                await self.send_to_user(user_id, event)

    @property
    def connected_users(self) -> list[str]:
        return list(self._connections.keys())


# Singleton instance
websocket_manager = WebSocketManager()

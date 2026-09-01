"""WebSocket connection manager for streaming progress updates.

Room-based: each async operation (preview, analyze, export) gets a unique room ID.
Clients connect to /ws/progress/{room_id} and receive real-time progress events.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections grouped by room (operation) IDs."""

    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, room_id: str) -> None:
        """Accept and register a WebSocket connection in a room."""
        await ws.accept()
        async with self._lock:
            self._rooms.setdefault(room_id, set()).add(ws)
        logger.debug("WS connected: room=%s (total=%d)", room_id, len(self._rooms[room_id]))

    async def disconnect(self, ws: WebSocket, room_id: str) -> None:
        """Remove a WebSocket connection from a room."""
        async with self._lock:
            conns = self._rooms.get(room_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    del self._rooms[room_id]
        logger.debug("WS disconnected: room=%s", room_id)

    async def broadcast(self, room_id: str, message: dict[str, Any]) -> None:
        """Send a JSON message to all connections in a room.

        Dead connections are silently removed.
        """
        async with self._lock:
            conns = list(self._rooms.get(room_id, set()))
        if not conns:
            return
        payload = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        if dead:
            async with self._lock:
                room_conns = self._rooms.get(room_id)
                if room_conns:
                    for ws in dead:
                        room_conns.discard(ws)
                    if not room_conns:
                        del self._rooms[room_id]

    def cleanup_room(self, room_id: str) -> None:
        """Force-remove a room (e.g. after operation completes)."""
        self._rooms.pop(room_id, None)

    @property
    def active_rooms(self) -> list[str]:
        return list(self._rooms.keys())


# Singleton shared across the app.
manager = ConnectionManager()


def new_room_id() -> str:
    """Generate a unique room ID for an async operation."""
    return uuid.uuid4().hex[:12]


class ProgressReporter:
    """Callable helper that broadcasts progress events to a room.

    Usage inside an engine function::

        reporter = ProgressReporter(room_id, manager)
        reporter("loading", 10, "Reading tracks…")
        reporter("rendering", 60)
        reporter.done({"output_path": "/tmp/preview.wav"})
        # or on failure:
        reporter.error("File not found: kick.wav")
    """

    def __init__(self, room_id: str, mgr: ConnectionManager | None = None) -> None:
        self.room_id = room_id
        self._mgr = mgr or manager
        self._last_send = 0.0

    def __call__(
        self,
        stage: str,
        percent: int,
        detail: str = "",
        *,
        min_interval: float = 0.15,
    ) -> None:
        """Send a progress message, throttled to avoid flooding."""
        now = time.monotonic()
        if now - self._last_send < min_interval and percent < 100:
            return
        self._last_send = now
        msg: dict[str, Any] = {
            "type": "progress",
            "stage": stage,
            "percent": int(max(0, min(100, percent))),
        }
        if detail:
            msg["detail"] = detail
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._mgr.broadcast(self.room_id, msg))
        except RuntimeError:
            pass

    def done(self, result: dict[str, Any] | None = None) -> None:
        """Send a 'complete' message."""
        msg: dict[str, Any] = {"type": "complete"}
        if result:
            msg["result"] = result
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._mgr.broadcast(self.room_id, msg))
        except RuntimeError:
            pass

    def error(self, message: str) -> None:
        """Send an 'error' message."""
        msg: dict[str, Any] = {"type": "error", "message": message}
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._mgr.broadcast(self.room_id, msg))
        except RuntimeError:
            pass

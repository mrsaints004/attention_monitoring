from __future__ import annotations
import asyncio
import time
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.student_connections: dict[str, dict[str, WebSocket]] = {}
        self.instructor_connections: dict[str, list[WebSocket]] = {}
        self._last_broadcast: dict[str, float] = {}

    async def connect_student(self, session_id: str, student_id: str, ws: WebSocket):
        await ws.accept(subprotocol="attention")
        if session_id not in self.student_connections:
            self.student_connections[session_id] = {}
        previous = self.student_connections[session_id].get(student_id)
        self.student_connections[session_id][student_id] = ws
        if previous and previous is not ws:
            await previous.close(code=1000, reason="Rejoined on another connection")

    def disconnect_student(self, session_id: str, student_id: str):
        if session_id in self.student_connections:
            self.student_connections[session_id].pop(student_id, None)

    async def connect_instructor(self, session_id: str, ws: WebSocket):
        await ws.accept(subprotocol="attention")
        if session_id not in self.instructor_connections:
            self.instructor_connections[session_id] = []
        self.instructor_connections[session_id].append(ws)

    def disconnect_instructor(self, session_id: str, ws: WebSocket):
        if session_id in self.instructor_connections:
            try:
                self.instructor_connections[session_id].remove(ws)
            except ValueError:
                pass

    async def broadcast_to_instructors(self, session_id: str, data: dict, throttle_hz: int = 2):
        now = time.time()
        min_interval = 1.0 / throttle_hz
        last = self._last_broadcast.get(session_id, 0)
        if now - last < min_interval:
            return
        self._last_broadcast[session_id] = now

        connections = self.instructor_connections.get(session_id, [])
        dead = []
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_instructor(session_id, ws)

    async def close_session(self, session_id: str):
        connections = list(self.student_connections.get(session_id, {}).values())
        for ws in connections:
            try:
                await ws.close(code=1000, reason="Session ended")
            except RuntimeError:
                pass
        self.student_connections.pop(session_id, None)

    def get_student_count(self, session_id: str) -> int:
        return len(self.student_connections.get(session_id, {}))


manager = ConnectionManager()
"""
WebSocket live feed — pushes risk events to all connected dashboard clients.
Every 30 s a heartbeat is sent so connections survive idle proxies.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio, json, time

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        if len(self.active) >= 100:
            await ws.close(code=1008)  # Policy Violation — too many clients
            return
        await ws.accept()
        self.active.append(ws)
        # Send welcome handshake
        await ws.send_text(json.dumps({"type": "connected", "ts": int(time.time())}))

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        if "ts" not in data:
            data["ts"] = int(time.time())
        payload = json.dumps(data)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def _heartbeat(websocket: WebSocket):
    """Send periodic heartbeat frames so the connection stays alive."""
    while True:
        await asyncio.sleep(30)
        try:
            await websocket.send_text(json.dumps({"type": "heartbeat", "ts": int(time.time()), "clients": len(manager.active)}))
        except Exception:
            break


@router.websocket("/live")
async def websocket_live(websocket: WebSocket):
    """WebSocket endpoint — clients subscribe and receive live risk events."""
    await manager.connect(websocket)
    hb_task = asyncio.create_task(_heartbeat(websocket))
    try:
        while True:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=60)
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "ts": int(time.time())}))
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        hb_task.cancel()
        manager.disconnect(websocket)


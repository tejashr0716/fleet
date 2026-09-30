import asyncio
import time

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.ws.manager import Client

router = APIRouter()


async def writer(ws, hub, client):
    while True:
        if time.time() >= client.expires_at:
            await ws.close(code=1008, reason="Token expired; sign in again")
            return
        try:
            event = await asyncio.wait_for(client.queue.get(), timeout=2)
        except TimeoutError:
            event = {
                "type": "heartbeat",
                "data": {"realtime": "connected" if hub.connected else "unavailable"},
            }
        if client.dropped:
            await ws.send_json({"type": "gap", "data": {"dropped": client.dropped}})
            client.dropped = 0
        await ws.send_json(event)


@router.websocket("/ws/live")
async def live(ws: WebSocket):
    origin = ws.headers.get("origin")
    if origin and origin not in ws.app.state.settings.origins:
        await ws.close(code=1008)
        return
    await ws.accept()
    hub, client, task = ws.app.state.hub, None, None
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=5)
        if len(raw) > 4096:
            raise ValueError("Oversized authentication frame")
        import json

        message = json.loads(raw)
        if not isinstance(message, dict) or message.get("type") != "auth":
            raise ValueError("Authenticate in the first frame")
        claims = ws.app.state.auth.decode(message.get("token", ""))
        if claims["sub"] != ws.app.state.settings.admin_username:
            raise ValueError("Unknown account")
        client = Client(expires_at=claims["exp"])
        hub.clients.add(client)
        await ws.send_json(
            {
                "type": "ready",
                "data": {
                    "sample_data": True,
                    "realtime": "connected" if hub.connected else "unavailable",
                },
            }
        )
        task = asyncio.create_task(writer(ws, hub, client))
        while True:
            raw = await ws.receive_text()
            if len(raw) > 1024:
                raise ValueError("Oversized client frame")
            frame = json.loads(raw)
            if not isinstance(frame, dict):
                raise ValueError("Client frames must be objects")
            if frame.get("type") == "ping":
                hub.enqueue(client, {"type": "pong", "data": {}})
    except (ValueError, HTTPException, TimeoutError):
        await ws.close(code=1008, reason="Authentication or frame validation failed")
    except WebSocketDisconnect:
        pass
    finally:
        if client:
            hub.clients.discard(client)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

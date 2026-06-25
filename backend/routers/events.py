import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services import kafka_service

router = APIRouter()


@router.get("/events")
def get_events():
    """Last 50 CDC events, newest first."""
    return {"events": kafka_service.recent_events(50)}


@router.websocket("/events/stream")
async def stream(ws: WebSocket):
    """Push each new CDC event to the client as it arrives."""
    await ws.accept()
    last_seq = kafka_service.current_seq()
    try:
        while True:
            new_events = kafka_service.events_since(last_seq)
            if new_events:
                last_seq = new_events[-1]["_seq"]
                for event in new_events:
                    await ws.send_json(event)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
    except Exception:
        return

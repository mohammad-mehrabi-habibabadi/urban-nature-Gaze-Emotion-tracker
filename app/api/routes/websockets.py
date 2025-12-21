# File: app/api/routes/websockets.py
# Purpose: Handle real-time WebSocket connections for the dashboard.

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
from app.services.experiment_logic import experiment_logic

router = APIRouter()

@router.websocket("/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Check if we have new data?
            data = experiment_logic.latest_data
            
            if data:
                # Submit data to the researcher dashboard
                await websocket.send_json(data)
            else:
                # If there is no data, send an empty status to keep the connection alive.
                await websocket.send_json({"status": "waiting_for_data"})
            
            # Transmitting at 20 frames per second
            await asyncio.sleep(0.05)
            
    except WebSocketDisconnect:
        print("Researcher disconnected")
    except Exception as e:
        print(f"WebSocket Error: {e}")
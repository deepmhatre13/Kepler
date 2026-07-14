from fastapi import WebSocket
from typing import Dict, Set, Any
import json
import logging

logger = logging.getLogger("app")

class ConnectionManager:
    def __init__(self):
        
        self.active_subscriptions: Dict[str, Set[WebSocket]] = {
            "satellites": set(),
            "debris": set(),
            "collisions": set(),
            "alerts": set(),
            "agents": set(),
            "simulations": set()
        }

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        logger.info("New WebSocket connection established.")

    def disconnect(self, websocket: WebSocket):
        
        for channel, sockets in self.active_subscriptions.items():
            if websocket in sockets:
                sockets.remove(websocket)
        logger.info("WebSocket disconnected and cleaned up.")

    def subscribe(self, websocket: WebSocket, channel: str):
        if channel in self.active_subscriptions:
            self.active_subscriptions[channel].add(websocket)
            logger.info(f"WebSocket subscribed to channel: {channel}")
        else:
            logger.warning(f"Attempted subscription to invalid channel: {channel}")

    def unsubscribe(self, websocket: WebSocket, channel: str):
        if channel in self.active_subscriptions and websocket in self.active_subscriptions[channel]:
            self.active_subscriptions[channel].remove(websocket)
            logger.info(f"WebSocket unsubscribed from channel: {channel}")

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        if channel in self.active_subscriptions:
            target_sockets = self.active_subscriptions[channel]
            if not target_sockets:
                return
            
            payload = json.dumps({
                "channel": channel,
                "data": message
            })
            
            
            disconnected_sockets = set()
            for socket in target_sockets:
                try:
                    await socket.send_text(payload)
                except Exception:
                    disconnected_sockets.add(socket)
            
            
            for socket in disconnected_sockets:
                self.disconnect(socket)

manager = ConnectionManager()

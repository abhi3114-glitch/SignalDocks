"""
SignalDock WebSocket Handler

Manages WebSocket connections for real-time communication with the frontend.
"""
import asyncio
import json
from typing import Dict, Set, Optional, Any, Callable
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import logging

from signals.base import SignalEvent
from actions.base import ActionResult

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket client connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # channel -> {connection_ids}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept a new WebSocket connection"""
        await websocket.accept()
        async with self._lock:
            self.active_connections[client_id] = websocket
        logger.info(f"Client connected: {client_id}")
    
    async def disconnect(self, client_id: str) -> None:
        """Remove a WebSocket connection"""
        async with self._lock:
            if client_id in self.active_connections:
                del self.active_connections[client_id]
            
            # Remove from all subscriptions
            for channel in list(self.subscriptions.keys()):
                self.subscriptions[channel].discard(client_id)
                if not self.subscriptions[channel]:
                    del self.subscriptions[channel]
        
        logger.info(f"Client disconnected: {client_id}")
    
    async def subscribe(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a channel"""
        async with self._lock:
            if channel not in self.subscriptions:
                self.subscriptions[channel] = set()
            self.subscriptions[channel].add(client_id)
        logger.debug(f"Client {client_id} subscribed to {channel}")
    
    async def unsubscribe(self, client_id: str, channel: str) -> None:
        """Unsubscribe a client from a channel"""
        async with self._lock:
            if channel in self.subscriptions:
                self.subscriptions[channel].discard(client_id)
    
    async def send_personal(self, client_id: str, message: dict) -> bool:
        """Send a message to a specific client"""
        websocket = self.active_connections.get(client_id)
        if websocket:
            try:
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.error(f"Error sending to {client_id}: {e}")
                await self.disconnect(client_id)
        return False
    
    async def broadcast(self, message: dict, channel: Optional[str] = None) -> int:
        """
        Broadcast a message to all clients or to a specific channel.
        Returns number of clients that received the message.
        """
        sent_count = 0
        
        if channel:
            client_ids = self.subscriptions.get(channel, set()).copy()
        else:
            client_ids = set(self.active_connections.keys())
        
        for client_id in client_ids:
            if await self.send_personal(client_id, message):
                sent_count += 1
        
        return sent_count
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)


class WebSocketHandler:
    """
    Handles WebSocket message routing and event broadcasting.
    """
    
    # Message types
    MSG_EVENT = "event"
    MSG_ACTION = "action"
    MSG_STATUS = "status"
    MSG_PIPELINE = "pipeline"
    MSG_SUBSCRIBE = "subscribe"
    MSG_UNSUBSCRIBE = "unsubscribe"
    MSG_PING = "ping"
    MSG_PONG = "pong"
    MSG_ERROR = "error"
    
    # Channels
    CHANNEL_EVENTS = "events"
    CHANNEL_ACTIONS = "actions"
    CHANNEL_PIPELINES = "pipelines"
    CHANNEL_SYSTEM = "system"
    
    def __init__(self, connection_manager: Optional[ConnectionManager] = None):
        self.manager = connection_manager or ConnectionManager()
        self._message_handlers: Dict[str, Callable] = {}
        self._setup_handlers()
        self.logger = logging.getLogger(f"{__name__}.WebSocketHandler")
    
    def _setup_handlers(self):
        """Set up message type handlers"""
        self._message_handlers = {
            self.MSG_SUBSCRIBE: self._handle_subscribe,
            self.MSG_UNSUBSCRIBE: self._handle_unsubscribe,
            self.MSG_PING: self._handle_ping,
            self.MSG_PIPELINE: self._handle_pipeline_message,
        }
    
    async def handle_connection(self, websocket: WebSocket, client_id: str) -> None:
        """Main handler for a WebSocket connection"""
        await self.manager.connect(websocket, client_id)
        
        # Send welcome message
        await self.manager.send_personal(client_id, {
            "type": "welcome",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                
                # Process message
                await self._process_message(client_id, data)
                
        except WebSocketDisconnect:
            await self.manager.disconnect(client_id)
        except Exception as e:
            self.logger.error(f"WebSocket error for {client_id}: {e}")
            await self.manager.disconnect(client_id)
    
    async def _process_message(self, client_id: str, data: dict) -> None:
        """Process an incoming message"""
        msg_type = data.get("type", "")
        
        handler = self._message_handlers.get(msg_type)
        if handler:
            try:
                await handler(client_id, data)
            except Exception as e:
                self.logger.error(f"Error handling {msg_type}: {e}")
                await self.manager.send_personal(client_id, {
                    "type": self.MSG_ERROR,
                    "message": str(e)
                })
        else:
            self.logger.warning(f"Unknown message type: {msg_type}")
    
    async def _handle_subscribe(self, client_id: str, data: dict) -> None:
        """Handle subscription request"""
        channel = data.get("channel", "")
        if channel:
            await self.manager.subscribe(client_id, channel)
            await self.manager.send_personal(client_id, {
                "type": "subscribed",
                "channel": channel
            })
    
    async def _handle_unsubscribe(self, client_id: str, data: dict) -> None:
        """Handle unsubscription request"""
        channel = data.get("channel", "")
        if channel:
            await self.manager.unsubscribe(client_id, channel)
            await self.manager.send_personal(client_id, {
                "type": "unsubscribed",
                "channel": channel
            })
    
    async def _handle_ping(self, client_id: str, data: dict) -> None:
        """Handle ping message"""
        await self.manager.send_personal(client_id, {
            "type": self.MSG_PONG,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _handle_pipeline_message(self, client_id: str, data: dict) -> None:
        """Handle pipeline-related messages"""
        action = data.get("action", "")
        
        if action == "get_status":
            # This would be implemented to get pipeline status
            pass
        elif action == "toggle":
            # Toggle pipeline active state
            pass
    
    # Broadcasting methods
    
    async def broadcast_event(self, event: SignalEvent) -> None:
        """Broadcast a signal event to subscribed clients"""
        message = {
            "type": self.MSG_EVENT,
            "event": event.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.manager.broadcast(message, self.CHANNEL_EVENTS)
    
    async def broadcast_action(self, result: ActionResult, pipeline_id: int, node_id: str) -> None:
        """Broadcast an action result to subscribed clients"""
        message = {
            "type": self.MSG_ACTION,
            "result": result.to_dict(),
            "pipeline_id": pipeline_id,
            "node_id": node_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.manager.broadcast(message, self.CHANNEL_ACTIONS)
    
    async def broadcast_pipeline_update(self, pipeline_id: int, status: dict) -> None:
        """Broadcast pipeline status update"""
        message = {
            "type": self.MSG_PIPELINE,
            "pipeline_id": pipeline_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.manager.broadcast(message, self.CHANNEL_PIPELINES)
    
    async def broadcast_system_status(self, status: dict) -> None:
        """Broadcast system status to all clients"""
        message = {
            "type": self.MSG_STATUS,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.manager.broadcast(message, self.CHANNEL_SYSTEM)
    
    def register_message_handler(self, msg_type: str, handler: Callable) -> None:
        """Register a custom message handler"""
        self._message_handlers[msg_type] = handler

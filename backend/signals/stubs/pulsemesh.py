"""
SignalDock PulseMesh Integration Stub

This is a placeholder for integration with PulseMesh peer-to-peer network.
Replace this with actual PulseMesh client when available.
"""
import random
import uuid
from typing import Optional
from datetime import datetime

from ..base import SignalSource, SignalEvent, EventType


class PulseMeshSignalSource(SignalSource):
    """PulseMesh peer discovery integration (stub)"""
    
    display_name = "PulseMesh"
    description = "Peer events from PulseMesh network (integration stub)"
    requires_permission = False
    
    def __init__(self, 
                 name: str = "pulsemesh_monitor",
                 demo_mode: bool = True,
                 mesh_endpoint: Optional[str] = None):
        super().__init__(name)
        
        self.demo_mode = demo_mode
        self.mesh_endpoint = mesh_endpoint
        
        self._known_peers: dict[str, dict] = {}
        self._demo_peer_names = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
    
    def get_poll_interval(self) -> float:
        return 5.0  # Poll every 5 seconds
    
    def _simulate_peer_event(self) -> Optional[dict]:
        """Simulate peer discovery/loss events for demo mode"""
        # 30% chance of an event
        if random.random() > 0.3:
            return None
        
        # 70% chance of peer found, 30% chance of peer lost
        if random.random() > 0.3 or not self._known_peers:
            # Peer found
            peer_id = str(uuid.uuid4())[:8]
            peer_name = random.choice(self._demo_peer_names)
            
            peer_info = {
                "peer_id": peer_id,
                "peer_name": f"{peer_name}_{peer_id[:4]}",
                "ip_address": f"192.168.1.{random.randint(2, 254)}",
                "capabilities": random.sample(["file_transfer", "messaging", "screen_share"], k=random.randint(1, 3))
            }
            
            self._known_peers[peer_id] = peer_info
            
            return {
                "event": "peer_found",
                **peer_info
            }
        else:
            # Peer lost
            peer_id = random.choice(list(self._known_peers.keys()))
            peer_info = self._known_peers.pop(peer_id)
            
            return {
                "event": "peer_lost",
                **peer_info
            }
    
    async def _fetch_from_mesh(self) -> Optional[dict]:
        """Fetch peer events from PulseMesh"""
        if not self.mesh_endpoint:
            return None
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.mesh_endpoint}/peers/events") as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            self.logger.error(f"Error fetching from PulseMesh: {e}")
        
        return None
    
    async def _poll(self) -> Optional[SignalEvent]:
        """Poll for peer events"""
        try:
            if self.demo_mode:
                event_data = self._simulate_peer_event()
            else:
                event_data = await self._fetch_from_mesh()
            
            if event_data is None:
                return None
            
            # Update last value
            self._last_value = {
                "known_peers": len(self._known_peers),
                "last_event": event_data.get("event")
            }
            
            event_type = EventType.DETECTED
            if event_data.get("event") == "peer_found":
                event_type = EventType.CREATED
            elif event_data.get("event") == "peer_lost":
                event_type = EventType.DELETED
            
            return SignalEvent(
                event_type=event_type,
                data={
                    **event_data,
                    "total_known_peers": len(self._known_peers)
                },
                metadata={
                    "source": "demo" if self.demo_mode else "mesh",
                    "mesh_endpoint": self.mesh_endpoint
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error polling PulseMesh: {e}")
            return None
    
    def get_known_peers(self) -> list[dict]:
        """Get list of known peers"""
        return list(self._known_peers.values())
    
    def get_config_schema(self) -> dict:
        return {
            "demo_mode": {
                "type": "boolean",
                "description": "Use demo mode with simulated peers",
                "default": True
            },
            "mesh_endpoint": {
                "type": "string",
                "description": "PulseMesh API endpoint URL",
                "default": None
            },
            "poll_interval": {
                "type": "number",
                "description": "Polling interval in seconds",
                "default": 5.0,
                "min": 1,
                "max": 60
            }
        }

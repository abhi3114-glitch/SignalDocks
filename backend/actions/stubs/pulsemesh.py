"""
SignalDock PulseMesh Action Stub

This is a placeholder for integration with PulseMesh peer-to-peer network.
Replace this with actual PulseMesh client when available.
"""
from typing import Optional
import random
import uuid

from ..base import Action, ActionResult


class PulseMeshAction(Action):
    """Send pulses to PulseMesh peers (stub)"""
    
    display_name = "PulseMesh Send"
    description = "Send messages/pulses to PulseMesh peers (integration stub)"
    requires_permission = False
    
    def __init__(self, 
                 name: str = "pulsemesh_action",
                 params: Optional[dict] = None,
                 demo_mode: bool = True,
                 mesh_endpoint: Optional[str] = None):
        super().__init__(name, params)
        self.demo_mode = demo_mode
        self.mesh_endpoint = mesh_endpoint
    
    async def execute(self, context: dict) -> ActionResult:
        """Execute PulseMesh send"""
        params = context.get("params", {})
        event = context.get("event", {})
        
        peer_id = params.get("peer_id")  # None = broadcast
        message_type = params.get("message_type", "notification")
        payload = params.get("payload", {})
        
        # Template substitution for payload
        if event:
            event_data = event.get("data", {}) if isinstance(event, dict) else event.data
            payload = self._substitute_payload(payload, event_data)
        
        if self.demo_mode:
            return await self._demo_send(peer_id, message_type, payload)
        else:
            return await self._api_send(peer_id, message_type, payload)
    
    async def _demo_send(self, peer_id: Optional[str], message_type: str, payload: dict) -> ActionResult:
        """Simulate send in demo mode"""
        # Simulate random success/failure
        if random.random() > 0.05:  # 95% success rate
            message_id = str(uuid.uuid4())[:8]
            target = peer_id or "broadcast"
            
            return ActionResult.success(
                message=f"Pulse sent to {target} (demo)",
                data={
                    "message_id": message_id,
                    "peer_id": peer_id,
                    "target": target,
                    "message_type": message_type,
                    "payload": payload,
                    "demo_mode": True
                }
            )
        else:
            return ActionResult.failure(
                "Send failed (simulated failure)",
                message="Demo mode random failure"
            )
    
    async def _api_send(self, peer_id: Optional[str], message_type: str, payload: dict) -> ActionResult:
        """Send via PulseMesh API"""
        if not self.mesh_endpoint:
            return ActionResult.failure("PulseMesh endpoint not configured")
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                data = {
                    "peer_id": peer_id,
                    "message_type": message_type,
                    "payload": payload
                }
                
                async with session.post(
                    f"{self.mesh_endpoint}/send",
                    json=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return ActionResult.success(
                            message="Pulse sent via PulseMesh",
                            data=result
                        )
                    else:
                        error = await response.text()
                        return ActionResult.failure(f"Send failed: {error}")
                        
        except ImportError:
            return ActionResult.failure("aiohttp not available for API requests")
        except Exception as e:
            return ActionResult.failure(str(e))
    
    def _substitute_payload(self, payload: dict, event_data: dict) -> dict:
        """Substitute event data into payload values"""
        result = {}
        for key, value in payload.items():
            if isinstance(value, str):
                for event_key, event_value in event_data.items():
                    placeholder = "{" + event_key + "}"
                    if placeholder in value:
                        value = value.replace(placeholder, str(event_value))
            result[key] = value
        return result
    
    def validate_params(self, params: dict) -> tuple[bool, Optional[str]]:
        """Validate PulseMesh parameters"""
        message_type = params.get("message_type", "")
        valid_types = ["notification", "data", "command", "sync"]
        
        if message_type and message_type not in valid_types:
            return False, f"Invalid message_type. Must be one of: {valid_types}"
        
        return True, None
    
    def get_param_schema(self) -> dict:
        return {
            "peer_id": {
                "type": "string",
                "description": "Target peer ID (null for broadcast)",
                "default": None
            },
            "message_type": {
                "type": "string",
                "enum": ["notification", "data", "command", "sync"],
                "description": "Type of pulse message",
                "default": "notification"
            },
            "payload": {
                "type": "object",
                "description": "Message payload (supports {event_field} templates)",
                "default": {}
            }
        }

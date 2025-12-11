"""
SignalDock SensoryNet Integration Stub

This is a placeholder for integration with SensoryNet ambient sensing system.
Replace this with actual SensoryNet API client when available.
"""
import random
from typing import Optional
from datetime import datetime

from ..base import SignalSource, SignalEvent, EventType


class SensoryNetSignalSource(SignalSource):
    """SensoryNet ambient score integration (stub)"""
    
    display_name = "SensoryNet"
    description = "Ambient environment scores from SensoryNet (integration stub)"
    requires_permission = False
    
    def __init__(self, 
                 name: str = "sensorynet_monitor",
                 demo_mode: bool = True,
                 api_endpoint: Optional[str] = None):
        super().__init__(name)
        
        self.demo_mode = demo_mode
        self.api_endpoint = api_endpoint
        
        self._last_ambient_score: Optional[float] = None
    
    def get_poll_interval(self) -> float:
        return 10.0  # Poll every 10 seconds
    
    def _get_demo_ambient_score(self) -> dict:
        """Generate demo ambient scores"""
        return {
            "ambient_score": round(random.uniform(0, 100), 1),
            "noise_level": round(random.uniform(20, 80), 1),
            "light_level": round(random.uniform(0, 1000), 1),
            "temperature": round(random.uniform(18, 28), 1),
            "humidity": round(random.uniform(30, 70), 1),
            "air_quality_index": random.randint(0, 150)
        }
    
    async def _fetch_from_api(self) -> Optional[dict]:
        """Fetch ambient data from SensoryNet API"""
        if not self.api_endpoint:
            return None
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_endpoint}/ambient") as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            self.logger.error(f"Error fetching from SensoryNet API: {e}")
        
        return None
    
    async def _poll(self) -> Optional[SignalEvent]:
        """Poll for ambient data"""
        try:
            if self.demo_mode:
                data = self._get_demo_ambient_score()
            else:
                data = await self._fetch_from_api()
                if data is None:
                    return None
            
            ambient_score = data.get("ambient_score", 0)
            
            # Update last value
            self._last_value = data
            
            # Check for significant change (10+ points)
            if self._last_ambient_score is None or abs(ambient_score - self._last_ambient_score) >= 10:
                previous_score = self._last_ambient_score
                self._last_ambient_score = ambient_score
                
                return SignalEvent(
                    event_type=EventType.VALUE_CHANGED,
                    data={
                        **data,
                        "previous_ambient_score": previous_score
                    },
                    metadata={
                        "source": "demo" if self.demo_mode else "api",
                        "api_endpoint": self.api_endpoint
                    }
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error polling SensoryNet: {e}")
            return None
    
    def get_config_schema(self) -> dict:
        return {
            "demo_mode": {
                "type": "boolean",
                "description": "Use demo mode with simulated data",
                "default": True
            },
            "api_endpoint": {
                "type": "string",
                "description": "SensoryNet API endpoint URL",
                "default": None
            },
            "poll_interval": {
                "type": "number",
                "description": "Polling interval in seconds",
                "default": 10.0,
                "min": 5,
                "max": 300
            }
        }

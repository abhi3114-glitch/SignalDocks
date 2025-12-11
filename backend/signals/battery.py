"""
SignalDock Battery Signal Source
"""
import psutil
from typing import Optional
from datetime import datetime

from .base import SignalSource, SignalEvent, EventType, ThresholdMixin
from config import get_config


class BatterySignalSource(SignalSource, ThresholdMixin):
    """Battery level and charging status monitoring"""
    
    display_name = "Battery"
    description = "Monitors battery level and charging status"
    requires_permission = False
    
    def __init__(self, name: str = "battery_monitor"):
        SignalSource.__init__(self, name)
        ThresholdMixin.__init__(self)
        
        config = get_config()
        
        # Set up thresholds
        self.set_threshold("battery", 
                          config.signals.battery_critical_threshold, 
                          100)  # High threshold not used for battery
        
        # Track state
        self._last_percent: Optional[float] = None
        self._last_plugged: Optional[bool] = None
        self._battery_available = self._check_battery_available()
    
    def _check_battery_available(self) -> bool:
        """Check if battery is available on this system"""
        try:
            battery = psutil.sensors_battery()
            return battery is not None
        except Exception:
            return False
    
    def get_poll_interval(self) -> float:
        return get_config().signals.battery_poll_interval
    
    async def _poll(self) -> Optional[SignalEvent]:
        """Poll battery status"""
        if not self._battery_available:
            return None
        
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return None
            
            percent = battery.percent
            plugged = battery.power_plugged
            time_left = battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None
            
            changes = []
            event_type = EventType.VALUE_CHANGED
            
            # Check for charging state change
            if self._last_plugged is not None and plugged != self._last_plugged:
                changes.append({
                    "type": "charging_state",
                    "previous": "plugged" if self._last_plugged else "unplugged",
                    "current": "plugged" if plugged else "unplugged"
                })
                event_type = EventType.STATE_CHANGED
            
            # Check for significant level change (1% or more) or threshold crossing
            if self._last_percent is None or abs(percent - self._last_percent) >= 1:
                threshold_state = self.check_threshold("battery", percent)
                changes.append({
                    "type": "level",
                    "previous": self._last_percent,
                    "current": percent,
                    "threshold_state": threshold_state
                })
                if threshold_state:
                    event_type = EventType.THRESHOLD_CROSSED
            
            # Update tracking
            self._last_percent = percent
            self._last_plugged = plugged
            self._last_value = {
                "percent": percent,
                "plugged": plugged,
                "time_left_minutes": round(time_left / 60) if time_left else None
            }
            
            if changes:
                return SignalEvent(
                    event_type=event_type,
                    data={
                        "percent": percent,
                        "plugged": plugged,
                        "time_left_seconds": time_left,
                        "time_left_minutes": round(time_left / 60) if time_left else None,
                        "changes": changes
                    },
                    metadata={
                        "battery_available": True
                    }
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error polling battery: {e}")
            return None
    
    def get_current_values(self) -> dict:
        """Get current battery values immediately"""
        if not self._battery_available:
            return {"battery_available": False}
        
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return {"battery_available": False}
            
            time_left = battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None
            
            return {
                "battery_available": True,
                "percent": battery.percent,
                "plugged": battery.power_plugged,
                "time_left_minutes": round(time_left / 60) if time_left else None
            }
        except Exception:
            return {"battery_available": False}
    
    def get_config_schema(self) -> dict:
        return {
            "poll_interval": {
                "type": "number",
                "description": "Polling interval in seconds",
                "default": 10.0,
                "min": 5,
                "max": 300
            },
            "low_threshold": {
                "type": "number",
                "description": "Low battery threshold (%)",
                "default": 20,
                "min": 5,
                "max": 50
            },
            "critical_threshold": {
                "type": "number",
                "description": "Critical battery threshold (%)",
                "default": 10,
                "min": 1,
                "max": 20
            }
        }

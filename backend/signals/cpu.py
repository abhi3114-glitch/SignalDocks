"""
SignalDock CPU/RAM Signal Source
"""
import psutil
from typing import Optional
from datetime import datetime

from .base import SignalSource, SignalEvent, EventType, ThresholdMixin
from config import get_config


class CPUSignalSource(SignalSource, ThresholdMixin):
    """CPU and RAM monitoring signal source"""
    
    display_name = "CPU & Memory"
    description = "Monitors CPU usage percentage and RAM utilization"
    requires_permission = False
    
    def __init__(self, name: str = "cpu_ram_monitor"):
        SignalSource.__init__(self, name)
        ThresholdMixin.__init__(self)
        
        config = get_config()
        
        # Set up thresholds
        self.set_threshold("cpu", config.signals.cpu_low_threshold, config.signals.cpu_high_threshold)
        self.set_threshold("ram", 0, config.signals.ram_high_threshold)
        
        # Track last values for change detection
        self._last_cpu: Optional[float] = None
        self._last_ram: Optional[float] = None
        self._significant_change_threshold = 5.0  # 5% change is significant
    
    def get_poll_interval(self) -> float:
        return get_config().signals.cpu_poll_interval
    
    async def _poll(self) -> Optional[SignalEvent]:
        """Poll CPU and RAM metrics"""
        try:
            # Get current values
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            ram_percent = memory.percent
            
            events_data = []
            
            # Check for significant CPU change
            if self._last_cpu is None or abs(cpu_percent - self._last_cpu) >= self._significant_change_threshold:
                cpu_threshold_state = self.check_threshold("cpu", cpu_percent)
                events_data.append({
                    "metric": "cpu",
                    "value": cpu_percent,
                    "previous": self._last_cpu,
                    "threshold_state": cpu_threshold_state
                })
                self._last_cpu = cpu_percent
            
            # Check for significant RAM change
            if self._last_ram is None or abs(ram_percent - self._last_ram) >= self._significant_change_threshold:
                ram_threshold_state = self.check_threshold("ram", ram_percent)
                events_data.append({
                    "metric": "ram",
                    "value": ram_percent,
                    "previous": self._last_ram,
                    "threshold_state": ram_threshold_state,
                    "used_gb": round(memory.used / (1024**3), 2),
                    "total_gb": round(memory.total / (1024**3), 2)
                })
                self._last_ram = ram_percent
            
            # Update last value for status
            self._last_value = {
                "cpu_percent": cpu_percent,
                "ram_percent": ram_percent,
                "ram_used_gb": round(memory.used / (1024**3), 2),
                "ram_total_gb": round(memory.total / (1024**3), 2)
            }
            
            # Return event if changes occurred
            if events_data:
                # Determine event type
                has_threshold_crossing = any(e.get("threshold_state") for e in events_data)
                event_type = EventType.THRESHOLD_CROSSED if has_threshold_crossing else EventType.VALUE_CHANGED
                
                return SignalEvent(
                    event_type=event_type,
                    data={
                        "cpu_percent": cpu_percent,
                        "ram_percent": ram_percent,
                        "ram_used_gb": round(memory.used / (1024**3), 2),
                        "ram_total_gb": round(memory.total / (1024**3), 2),
                        "changes": events_data
                    },
                    metadata={
                        "cpu_count": psutil.cpu_count(),
                        "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
                    }
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error polling CPU/RAM: {e}")
            return None
    
    def get_current_values(self) -> dict:
        """Get current CPU and RAM values immediately"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        return {
            "cpu_percent": cpu_percent,
            "ram_percent": memory.percent,
            "ram_used_gb": round(memory.used / (1024**3), 2),
            "ram_total_gb": round(memory.total / (1024**3), 2),
            "cpu_count": psutil.cpu_count()
        }
    
    def get_config_schema(self) -> dict:
        return {
            "poll_interval": {
                "type": "number",
                "description": "Polling interval in seconds",
                "default": 2.0,
                "min": 0.5,
                "max": 60
            },
            "cpu_high_threshold": {
                "type": "number", 
                "description": "CPU high usage threshold (%)",
                "default": 80,
                "min": 0,
                "max": 100
            },
            "cpu_low_threshold": {
                "type": "number",
                "description": "CPU low usage threshold (%)",
                "default": 20,
                "min": 0,
                "max": 100
            },
            "ram_high_threshold": {
                "type": "number",
                "description": "RAM high usage threshold (%)",
                "default": 85,
                "min": 0,
                "max": 100
            },
            "significant_change": {
                "type": "number",
                "description": "Minimum change to trigger event (%)",
                "default": 5,
                "min": 1,
                "max": 50
            }
        }

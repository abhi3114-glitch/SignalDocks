"""
SignalDock Network Signal Source
"""
import psutil
from typing import Optional
from datetime import datetime

from .base import SignalSource, SignalEvent, EventType
from config import get_config


class NetworkSignalSource(SignalSource):
    """Network connectivity and bandwidth monitoring"""
    
    display_name = "Network"
    description = "Monitors network connectivity, upload/download speeds"
    requires_permission = False
    
    def __init__(self, name: str = "network_monitor"):
        super().__init__(name)
        
        # Track previous values for rate calculation
        self._last_bytes_sent: Optional[int] = None
        self._last_bytes_recv: Optional[int] = None
        self._last_connected: Optional[bool] = None
        self._last_poll_time: Optional[datetime] = None
        
        # Thresholds for significant changes (bytes per second)
        self._significant_rate_change = 1024 * 100  # 100 KB/s
    
    def get_poll_interval(self) -> float:
        return get_config().signals.network_poll_interval
    
    def _check_connectivity(self) -> bool:
        """Check if network is connected"""
        try:
            stats = psutil.net_if_stats()
            for iface, stat in stats.items():
                if stat.isup and iface != 'lo':  # Ignore loopback
                    return True
            return False
        except Exception:
            return False
    
    async def _poll(self) -> Optional[SignalEvent]:
        """Poll network statistics"""
        try:
            now = datetime.utcnow()
            counters = psutil.net_io_counters()
            connected = self._check_connectivity()
            
            bytes_sent = counters.bytes_sent
            bytes_recv = counters.bytes_recv
            
            changes = []
            event_type = EventType.VALUE_CHANGED
            
            # Check connectivity change
            if self._last_connected is not None and connected != self._last_connected:
                changes.append({
                    "type": "connectivity",
                    "previous": "connected" if self._last_connected else "disconnected",
                    "current": "connected" if connected else "disconnected"
                })
                event_type = EventType.STATE_CHANGED
            
            # Calculate rates
            upload_rate = 0.0
            download_rate = 0.0
            
            if self._last_bytes_sent is not None and self._last_poll_time is not None:
                elapsed = (now - self._last_poll_time).total_seconds()
                if elapsed > 0:
                    upload_rate = (bytes_sent - self._last_bytes_sent) / elapsed
                    download_rate = (bytes_recv - self._last_bytes_recv) / elapsed
            
            # Update last value for status
            self._last_value = {
                "connected": connected,
                "upload_rate_mbps": round(upload_rate / (1024 * 1024), 2),
                "download_rate_mbps": round(download_rate / (1024 * 1024), 2),
                "total_sent_gb": round(bytes_sent / (1024**3), 2),
                "total_recv_gb": round(bytes_recv / (1024**3), 2)
            }
            
            # Track state
            self._last_bytes_sent = bytes_sent
            self._last_bytes_recv = bytes_recv
            self._last_connected = connected
            self._last_poll_time = now
            
            # Return event if there are changes or on first poll
            if changes or self._last_poll_time is None:
                return SignalEvent(
                    event_type=event_type,
                    data={
                        "connected": connected,
                        "upload_rate_bytes": upload_rate,
                        "download_rate_bytes": download_rate,
                        "upload_rate_mbps": round(upload_rate / (1024 * 1024), 2),
                        "download_rate_mbps": round(download_rate / (1024 * 1024), 2),
                        "total_bytes_sent": bytes_sent,
                        "total_bytes_recv": bytes_recv,
                        "changes": changes
                    },
                    metadata={
                        "packets_sent": counters.packets_sent,
                        "packets_recv": counters.packets_recv,
                        "errin": counters.errin,
                        "errout": counters.errout
                    }
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error polling network: {e}")
            return None
    
    def get_current_values(self) -> dict:
        """Get current network values immediately"""
        try:
            counters = psutil.net_io_counters()
            connected = self._check_connectivity()
            
            return {
                "connected": connected,
                "total_sent_gb": round(counters.bytes_sent / (1024**3), 2),
                "total_recv_gb": round(counters.bytes_recv / (1024**3), 2),
                "packets_sent": counters.packets_sent,
                "packets_recv": counters.packets_recv
            }
        except Exception:
            return {"connected": False}
    
    def get_interfaces(self) -> list[dict]:
        """Get list of network interfaces"""
        interfaces = []
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
            
            for iface, stat in stats.items():
                iface_info = {
                    "name": iface,
                    "is_up": stat.isup,
                    "speed_mbps": stat.speed,
                    "mtu": stat.mtu,
                    "addresses": []
                }
                
                if iface in addrs:
                    for addr in addrs[iface]:
                        iface_info["addresses"].append({
                            "family": str(addr.family),
                            "address": addr.address
                        })
                
                interfaces.append(iface_info)
        except Exception as e:
            self.logger.error(f"Error getting interfaces: {e}")
        
        return interfaces
    
    def get_config_schema(self) -> dict:
        return {
            "poll_interval": {
                "type": "number",
                "description": "Polling interval in seconds",
                "default": 5.0,
                "min": 1,
                "max": 60
            },
            "track_per_interface": {
                "type": "boolean",
                "description": "Track statistics per network interface",
                "default": False
            }
        }

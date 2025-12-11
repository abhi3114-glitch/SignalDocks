"""
SignalDock Window Focus Signal Source
"""
import platform
from typing import Optional
from datetime import datetime

from .base import SignalSource, SignalEvent, EventType
from config import get_config


class WindowFocusSignalSource(SignalSource):
    """Window focus change monitoring"""
    
    display_name = "Window Focus"
    description = "Monitors active window and focus changes"
    requires_permission = False
    
    def __init__(self, name: str = "window_focus_monitor"):
        super().__init__(name)
        
        self._last_window_title: Optional[str] = None
        self._last_process_name: Optional[str] = None
        self._platform = platform.system()
    
    def get_poll_interval(self) -> float:
        return get_config().signals.window_poll_interval
    
    def _get_active_window_windows(self) -> tuple[Optional[str], Optional[str]]:
        """Get active window on Windows"""
        try:
            import win32gui
            import win32process
            import psutil
            
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    process = psutil.Process(pid)
                    process_name = process.name()
                except:
                    process_name = None
                return title, process_name
        except ImportError:
            self.logger.warning("pywin32 not available for window monitoring")
        except Exception as e:
            self.logger.error(f"Error getting active window: {e}")
        
        return None, None
    
    def _get_active_window_linux(self) -> tuple[Optional[str], Optional[str]]:
        """Get active window on Linux using xprop"""
        try:
            import subprocess
            
            # Get active window ID
            result = subprocess.run(
                ['xprop', '-root', '_NET_ACTIVE_WINDOW'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            if result.returncode != 0:
                return None, None
            
            # Parse window ID
            output = result.stdout.strip()
            if 'window id #' not in output:
                return None, None
            
            window_id = output.split('window id # ')[-1].split(',')[0].strip()
            
            # Get window name
            result = subprocess.run(
                ['xprop', '-id', window_id, 'WM_NAME'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            title = None
            if result.returncode == 0:
                output = result.stdout.strip()
                if '=' in output:
                    title = output.split('=', 1)[1].strip().strip('"')
            
            # Get process name
            result = subprocess.run(
                ['xprop', '-id', window_id, 'WM_CLASS'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            process_name = None
            if result.returncode == 0:
                output = result.stdout.strip()
                if '=' in output:
                    parts = output.split('=', 1)[1].strip().split(',')
                    if parts:
                        process_name = parts[-1].strip().strip('"')
            
            return title, process_name
            
        except Exception as e:
            self.logger.error(f"Error getting active window on Linux: {e}")
        
        return None, None
    
    def _get_active_window(self) -> tuple[Optional[str], Optional[str]]:
        """Get active window info based on platform"""
        if self._platform == "Windows":
            return self._get_active_window_windows()
        elif self._platform == "Linux":
            return self._get_active_window_linux()
        else:
            self.logger.warning(f"Window monitoring not fully supported on {self._platform}")
            return None, None
    
    async def _poll(self) -> Optional[SignalEvent]:
        """Poll for window focus changes"""
        try:
            title, process_name = self._get_active_window()
            
            # Check for change
            if title != self._last_window_title or process_name != self._last_process_name:
                previous_title = self._last_window_title
                previous_process = self._last_process_name
                
                self._last_window_title = title
                self._last_process_name = process_name
                
                self._last_value = {
                    "window_title": title,
                    "process_name": process_name
                }
                
                return SignalEvent(
                    event_type=EventType.STATE_CHANGED,
                    data={
                        "window_title": title,
                        "process_name": process_name,
                        "previous_title": previous_title,
                        "previous_process": previous_process
                    },
                    metadata={
                        "platform": self._platform
                    }
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error polling window focus: {e}")
            return None
    
    def get_current_values(self) -> dict:
        """Get current active window info"""
        title, process_name = self._get_active_window()
        return {
            "window_title": title,
            "process_name": process_name,
            "platform": self._platform
        }
    
    def get_config_schema(self) -> dict:
        return {
            "poll_interval": {
                "type": "number",
                "description": "Polling interval in seconds",
                "default": 0.5,
                "min": 0.1,
                "max": 5
            }
        }

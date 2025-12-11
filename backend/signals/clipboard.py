"""
SignalDock Clipboard Signal Source
"""
import platform
from typing import Optional
from datetime import datetime

from .base import SignalSource, SignalEvent, EventType
from config import get_config


class ClipboardSignalSource(SignalSource):
    """Clipboard content monitoring"""
    
    display_name = "Clipboard"
    description = "Monitors clipboard content changes (requires permission)"
    requires_permission = True
    
    def __init__(self, name: str = "clipboard_monitor"):
        super().__init__(name)
        
        self._last_content: Optional[str] = None
        self._last_content_hash: Optional[int] = None
        self._platform = platform.system()
    
    def get_poll_interval(self) -> float:
        return get_config().signals.clipboard_poll_interval
    
    def _get_clipboard_windows(self) -> Optional[str]:
        """Get clipboard content on Windows"""
        try:
            import win32clipboard
            
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                    return data
            finally:
                win32clipboard.CloseClipboard()
        except ImportError:
            # Fall back to pyperclip
            try:
                import pyperclip
                return pyperclip.paste()
            except:
                pass
        except Exception as e:
            self.logger.error(f"Error reading clipboard: {e}")
        
        return None
    
    def _get_clipboard_linux(self) -> Optional[str]:
        """Get clipboard content on Linux"""
        try:
            import subprocess
            
            # Try xclip first
            try:
                result = subprocess.run(
                    ['xclip', '-selection', 'clipboard', '-o'],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                if result.returncode == 0:
                    return result.stdout
            except FileNotFoundError:
                pass
            
            # Try xsel
            try:
                result = subprocess.run(
                    ['xsel', '--clipboard', '--output'],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                if result.returncode == 0:
                    return result.stdout
            except FileNotFoundError:
                pass
            
        except Exception as e:
            self.logger.error(f"Error reading clipboard on Linux: {e}")
        
        return None
    
    def _get_clipboard(self) -> Optional[str]:
        """Get clipboard content based on platform"""
        if self._platform == "Windows":
            return self._get_clipboard_windows()
        elif self._platform == "Linux":
            return self._get_clipboard_linux()
        else:
            # Try pyperclip as fallback
            try:
                import pyperclip
                return pyperclip.paste()
            except:
                pass
        
        return None
    
    async def _poll(self) -> Optional[SignalEvent]:
        """Poll for clipboard changes"""
        # Check if clipboard monitoring is enabled
        config = get_config()
        if not config.permissions.clipboard_enabled:
            return None
        
        try:
            content = self._get_clipboard()
            
            if content is None:
                return None
            
            # Use hash for comparison (content could be large)
            content_hash = hash(content)
            
            if content_hash != self._last_content_hash:
                previous_content = self._last_content
                self._last_content = content
                self._last_content_hash = content_hash
                
                # Truncate for display/logging
                content_preview = content[:100] + "..." if len(content) > 100 else content
                
                self._last_value = {
                    "content_length": len(content),
                    "content_preview": content_preview
                }
                
                return SignalEvent(
                    event_type=EventType.VALUE_CHANGED,
                    data={
                        "content": content,
                        "content_length": len(content),
                        "content_preview": content_preview,
                        "previous_length": len(previous_content) if previous_content else 0
                    },
                    metadata={
                        "platform": self._platform
                    }
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error polling clipboard: {e}")
            return None
    
    def get_current_values(self) -> dict:
        """Get current clipboard content"""
        content = self._get_clipboard()
        if content:
            return {
                "content_length": len(content),
                "content_preview": content[:100] + "..." if len(content) > 100 else content
            }
        return {"content_length": 0, "content_preview": ""}
    
    def get_config_schema(self) -> dict:
        return {
            "poll_interval": {
                "type": "number",
                "description": "Polling interval in seconds",
                "default": 1.0,
                "min": 0.5,
                "max": 10
            },
            "enabled": {
                "type": "boolean",
                "description": "Enable clipboard monitoring (privacy-sensitive)",
                "default": False
            }
        }

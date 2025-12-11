import platform
import logging
from typing import Optional

from .base import Action, ActionResult

logger = logging.getLogger(__name__)


class NotificationAction(Action):
    """Show system notification"""
    
    display_name = "Notification"
    description = "Show a system notification"
    requires_permission = False
    
    def __init__(self, name: str = "notification_action", params: Optional[dict] = None):
        super().__init__(name, params)
        self._platform = platform.system()
    
    async def execute(self, context: dict) -> ActionResult:
        """Execute notification action"""
        logger.info(f"Executing notification action with context keys: {list(context.keys())}")
        
        params = context.get("params", {})
        event = context.get("event", {})
        
        # Get notification parameters
        title = params.get("title", "SignalDock Alert")
        message = params.get("message", "")
        timeout = params.get("timeout", 10)
        
        # Template substitution from event data
        if event:
            event_data = event.get("data", {}) if isinstance(event, dict) else event.data
            logger.info(f"Template substitution using event data keys: {list(event_data.keys()) if isinstance(event_data, dict) else 'Not a dict'}")
            title = self._substitute_template(title, event_data)
            message = self._substitute_template(message, event_data)
        
        logger.info(f"Notification content: title='{title}', message='{message}'")
        
        try:
            # Use plyer for cross-platform notifications
            from plyer import notification as plyer_notify
            
            logger.info("Attempting to send notification via plyer...")
            plyer_notify.notify(
                title=title,
                message=message,
                timeout=timeout,
                app_name="SignalDock"
            )
            logger.info("Plyer notification sent.")
            
            return ActionResult.success(
                message=f"Notification shown: {title}",
                data={
                    "title": title,
                    "message": message,
                    "timeout": timeout
                }
            )
            
        except ImportError:
            logger.warning("Plyer not found, trying fallback...")
            # Fallback for Windows
            if self._platform == "Windows":
                return await self._windows_notification(title, message, timeout)
            else:
                return ActionResult.failure(
                    "plyer not available for notifications",
                    message="Install plyer: pip install plyer"
                )
        except Exception as e:
            logger.error(f"Error executing notification: {e}")
            return ActionResult.failure(str(e))
    
    async def _windows_notification(self, title: str, message: str, timeout: int) -> ActionResult:
        """Windows-specific notification using win10toast"""
        try:
            from win10toast import ToastNotifier
            
            toaster = ToastNotifier()
            toaster.show_toast(
                title,
                message,
                duration=timeout,
                threaded=True
            )
            
            return ActionResult.success(
                message=f"Notification shown: {title}",
                data={"title": title, "message": message}
            )
        except ImportError:
            # Last resort: use ctypes
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
                return ActionResult.success(message="Notification shown via MessageBox")
            except:
                return ActionResult.failure("No notification method available on Windows")
        except Exception as e:
            return ActionResult.failure(str(e))
    
    def _substitute_template(self, template: str, data: dict) -> str:
        """Substitute {key} placeholders with data values"""
        result = template
        for key, value in data.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result
    
    def validate_params(self, params: dict) -> tuple[bool, Optional[str]]:
        """Validate notification parameters"""
        title = params.get("title", "")
        message = params.get("message", "")
        
        if not title and not message:
            return False, "At least one of 'title' or 'message' is required"
        
        timeout = params.get("timeout", 10)
        if not isinstance(timeout, (int, float)) or timeout < 1:
            return False, "Timeout must be a positive number"
        
        return True, None
    
    def get_param_schema(self) -> dict:
        return {
            "title": {
                "type": "string",
                "description": "Notification title (supports {event_field} templates)",
                "default": "SignalDock Alert"
            },
            "message": {
                "type": "string",
                "description": "Notification message (supports {event_field} templates)",
                "default": ""
            },
            "timeout": {
                "type": "integer",
                "description": "Notification display duration in seconds",
                "default": 10,
                "min": 1,
                "max": 60
            }
        }

"""
SignalDock Actions Package
"""
from .base import Action, ActionResult, ActionStatus
from .notification import NotificationAction
from .shell import ShellAction
from .file_ops import FileOperationAction
from .process import ProcessControlAction
from .network import NetworkControlAction

__all__ = [
    "Action",
    "ActionResult",
    "ActionStatus",
    "NotificationAction",
    "ShellAction",
    "FileOperationAction",
    "ProcessControlAction",
    "NetworkControlAction"
]


# Registry of available actions
ACTIONS = {
    "notification": NotificationAction,
    "shell": ShellAction,
    "file_operation": FileOperationAction,
    "process_control": ProcessControlAction,
    "network_control": NetworkControlAction,
}


def get_action(action_type: str) -> type:
    """Get action class by type name"""
    if action_type not in ACTIONS:
        raise ValueError(f"Unknown action type: {action_type}")
    return ACTIONS[action_type]


def list_actions() -> list[dict]:
    """List all available actions with metadata"""
    actions = []
    for name, cls in ACTIONS.items():
        actions.append({
            "type": name,
            "name": cls.display_name if hasattr(cls, 'display_name') else name,
            "description": cls.description if hasattr(cls, 'description') else "",
            "requires_permission": cls.requires_permission if hasattr(cls, 'requires_permission') else False,
        })
    return actions

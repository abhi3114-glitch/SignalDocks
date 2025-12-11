"""
SignalDock Base Action
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)


class ActionStatus(str, Enum):
    """Action execution status"""
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    PENDING = "pending"
    PERMISSION_DENIED = "permission_denied"


@dataclass
class ActionResult:
    """Result of an action execution"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: ActionStatus = ActionStatus.PENDING
    message: str = ""
    data: dict = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "message": self.message,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def success(cls, message: str = "", data: dict = None) -> "ActionResult":
        return cls(
            status=ActionStatus.SUCCESS,
            message=message,
            data=data or {}
        )
    
    @classmethod
    def failure(cls, error: str, message: str = "") -> "ActionResult":
        return cls(
            status=ActionStatus.FAILURE,
            message=message,
            error=error
        )
    
    @classmethod
    def skipped(cls, reason: str) -> "ActionResult":
        return cls(
            status=ActionStatus.SKIPPED,
            message=reason
        )
    
    @classmethod
    def permission_denied(cls, required_permission: str) -> "ActionResult":
        return cls(
            status=ActionStatus.PERMISSION_DENIED,
            message=f"Permission required: {required_permission}",
            error=f"Action requires '{required_permission}' permission"
        )


class Action(ABC):
    """Abstract base class for actions"""
    
    # Class-level metadata (override in subclasses)
    display_name: str = "Action"
    description: str = "Base action"
    requires_permission: bool = False
    permission_type: Optional[str] = None
    
    def __init__(self, name: Optional[str] = None, params: Optional[dict] = None):
        self.name = name or self.__class__.__name__
        self.params = params or {}
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
    
    @property
    def action_type(self) -> str:
        """Get action type identifier"""
        return self.__class__.__name__.lower().replace("action", "")
    
    @abstractmethod
    async def execute(self, context: dict) -> ActionResult:
        """
        Execute the action.
        
        Args:
            context: Dictionary containing:
                - event: The triggering SignalEvent
                - pipeline_id: ID of the executing pipeline
                - node_id: ID of the action node
                - params: Action parameters from the node
        
        Returns:
            ActionResult with execution status and details
        """
        pass
    
    def validate_params(self, params: dict) -> tuple[bool, Optional[str]]:
        """
        Validate action parameters.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None
    
    def get_param_schema(self) -> dict:
        """Get JSON schema for action parameters (override in subclasses)"""
        return {}
    
    def check_permission(self) -> bool:
        """Check if required permission is granted"""
        if not self.requires_permission:
            return True
        
        from config import get_config
        config = get_config()
        
        if self.permission_type == "shell_execution":
            return config.permissions.shell_execution_enabled
        elif self.permission_type == "file_operations":
            return config.permissions.file_operations_enabled
        elif self.permission_type == "process_control":
            return config.permissions.process_control_enabled
        elif self.permission_type == "network_control":
            return config.permissions.network_control_enabled
        
        return False
    
    async def safe_execute(self, context: dict) -> ActionResult:
        """Execute with permission checking and error handling"""
        import time
        
        start_time = time.time()
        
        try:
            # Check permission
            if self.requires_permission and not self.check_permission():
                return ActionResult.permission_denied(self.permission_type or "unknown")
            
            # Validate parameters
            is_valid, error = self.validate_params(context.get("params", {}))
            if not is_valid:
                return ActionResult.failure(error or "Invalid parameters")
            
            # Execute
            result = await self.execute(context)
            
            # Record execution time
            result.execution_time_ms = (time.time() - start_time) * 1000
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing action: {e}")
            result = ActionResult.failure(str(e))
            result.execution_time_ms = (time.time() - start_time) * 1000
            return result

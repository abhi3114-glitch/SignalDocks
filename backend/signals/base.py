"""
SignalDock Base Signal Source
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
from enum import Enum
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Standard event types"""
    VALUE_CHANGED = "value_changed"
    THRESHOLD_CROSSED = "threshold_crossed"
    STATE_CHANGED = "state_changed"
    DETECTED = "detected"
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


@dataclass
class SignalEvent:
    """Normalized signal event structure"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_type: str = ""
    source_name: str = ""
    event_type: EventType = EventType.VALUE_CHANGED
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "event_type": self.event_type.value if isinstance(self.event_type, EventType) else self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SignalEvent":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            source_type=data.get("source_type", ""),
            source_name=data.get("source_name", ""),
            event_type=EventType(data.get("event_type", "value_changed")),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.utcnow(),
            data=data.get("data", {}),
            metadata=data.get("metadata", {})
        )


class SignalSource(ABC):
    """Abstract base class for signal sources"""
    
    # Class-level metadata (override in subclasses)
    display_name: str = "Signal Source"
    description: str = "Base signal source"
    requires_permission: bool = False
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._subscribers: list[Callable[[SignalEvent], Any]] = []
        self._last_value: Any = None
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
    
    @property
    def source_type(self) -> str:
        """Get source type identifier"""
        return self.__class__.__name__.lower().replace("signalsource", "")
    
    @abstractmethod
    async def _poll(self) -> Optional[SignalEvent]:
        """
        Poll for signal changes. 
        Return SignalEvent if an event occurred, None otherwise.
        Must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    def get_poll_interval(self) -> float:
        """Get the polling interval in seconds"""
        pass
    
    def subscribe(self, callback: Callable[[SignalEvent], Any]) -> None:
        """Subscribe to events from this source"""
        if callback not in self._subscribers:
            self._subscribers.append(callback)
            self.logger.debug(f"Subscriber added. Total subscribers: {len(self._subscribers)}")
    
    def unsubscribe(self, callback: Callable[[SignalEvent], Any]) -> None:
        """Unsubscribe from events"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            self.logger.debug(f"Subscriber removed. Total subscribers: {len(self._subscribers)}")
    
    async def _notify_subscribers(self, event: SignalEvent) -> None:
        """Notify all subscribers of an event"""
        for callback in self._subscribers:
            try:
                result = callback(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                self.logger.error(f"Error notifying subscriber: {e}")
    
    async def _run_loop(self) -> None:
        """Main polling loop"""
        self.logger.info(f"Starting signal source: {self.name}")
        while self._running:
            try:
                event = await self._poll()
                if event:
                    event.source_type = self.source_type
                    event.source_name = self.name
                    await self._notify_subscribers(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in polling loop: {e}")
            
            await asyncio.sleep(self.get_poll_interval())
        
        self.logger.info(f"Signal source stopped: {self.name}")
    
    async def start(self) -> None:
        """Start the signal source"""
        if self._running:
            self.logger.warning(f"Signal source already running: {self.name}")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
    
    async def stop(self) -> None:
        """Stop the signal source"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
    
    def is_running(self) -> bool:
        """Check if the source is running"""
        return self._running
    
    def get_status(self) -> dict:
        """Get current status of the signal source"""
        return {
            "name": self.name,
            "type": self.source_type,
            "running": self._running,
            "subscribers": len(self._subscribers),
            "last_value": self._last_value
        }
    
    def get_config_schema(self) -> dict:
        """Get configuration schema for this source (override in subclasses)"""
        return {}


class ThresholdMixin:
    """Mixin for threshold-based signal sources"""
    
    def __init__(self):
        self._thresholds: dict[str, tuple[float, float]] = {}  # name -> (low, high)
        self._threshold_states: dict[str, str] = {}  # name -> "normal", "low", "high"
    
    def set_threshold(self, name: str, low: float, high: float) -> None:
        """Set threshold values"""
        self._thresholds[name] = (low, high)
        self._threshold_states[name] = "normal"
    
    def check_threshold(self, name: str, value: float) -> Optional[str]:
        """
        Check if value crosses a threshold.
        Returns: "low", "high", or None if no crossing occurred
        """
        if name not in self._thresholds:
            return None
        
        low, high = self._thresholds[name]
        current_state = self._threshold_states.get(name, "normal")
        new_state = "normal"
        
        if value <= low:
            new_state = "low"
        elif value >= high:
            new_state = "high"
        
        if new_state != current_state:
            self._threshold_states[name] = new_state
            return new_state
        
        return None

"""
SignalDock Execution Policies
"""
from abc import ABC, abstractmethod
from typing import Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
import logging

logger = logging.getLogger(__name__)


class ExecutionPolicy(ABC):
    """Abstract base class for execution policies"""
    
    policy_type: str = "base"
    
    def __init__(self, params: Optional[dict] = None):
        self.params = params or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def should_execute(self, action_id: str, context: dict) -> bool:
        """
        Determine if action should execute based on policy.
        
        Args:
            action_id: Unique identifier for the action instance
            context: Execution context with event and params
        
        Returns:
            True if action should execute, False to skip
        """
        pass
    
    @abstractmethod
    async def on_execute(self, action_id: str, context: dict) -> None:
        """Called after action execution to update policy state"""
        pass
    
    @classmethod
    def from_config(cls, config: dict) -> "ExecutionPolicy":
        """Create policy from configuration dict"""
        policy_type = config.get("type", "none")
        params = config.get("params", {})
        
        if policy_type == "debounce":
            return DebouncePolicy(params)
        elif policy_type == "rate_limit":
            return RateLimitPolicy(params)
        elif policy_type == "conditional":
            return ConditionalPolicy(params)
        elif policy_type == "cooldown":
            return CooldownPolicy(params)
        elif policy_type == "none":
            return NoPolicy(params)
        else:
            raise ValueError(f"Unknown policy type: {policy_type}")


class NoPolicy(ExecutionPolicy):
    """No execution policy - always execute"""
    
    policy_type = "none"
    
    async def should_execute(self, action_id: str, context: dict) -> bool:
        return True
    
    async def on_execute(self, action_id: str, context: dict) -> None:
        pass


class DebouncePolicy(ExecutionPolicy):
    """
    Debounce policy - delays execution and resets timer on new events.
    Only executes after a quiet period with no new events.
    """
    
    policy_type = "debounce"
    
    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        self.delay_seconds = self.params.get("delay_seconds", 1.0)
        self._pending_tasks: dict[str, asyncio.Task] = {}
        self._execution_callbacks: dict[str, Any] = {}
    
    async def should_execute(self, action_id: str, context: dict) -> bool:
        """Debounce always returns False - execution is scheduled via callback"""
        # Cancel any pending execution
        if action_id in self._pending_tasks:
            self._pending_tasks[action_id].cancel()
        
        # Schedule new execution
        callback = context.get("_execute_callback")
        if callback:
            self._execution_callbacks[action_id] = callback
            self._pending_tasks[action_id] = asyncio.create_task(
                self._delayed_execute(action_id, context)
            )
        
        # Don't execute immediately
        return False
    
    async def _delayed_execute(self, action_id: str, context: dict) -> None:
        """Execute after delay"""
        try:
            await asyncio.sleep(self.delay_seconds)
            
            callback = self._execution_callbacks.get(action_id)
            if callback:
                await callback(context)
                
        except asyncio.CancelledError:
            # Debounced - new event came in
            pass
        finally:
            self._pending_tasks.pop(action_id, None)
            self._execution_callbacks.pop(action_id, None)
    
    async def on_execute(self, action_id: str, context: dict) -> None:
        pass


class RateLimitPolicy(ExecutionPolicy):
    """
    Rate limit policy - limits executions to N per time window.
    """
    
    policy_type = "rate_limit"
    
    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        self.max_executions = self.params.get("max_executions", 5)
        self.window_seconds = self.params.get("window_seconds", 60)
        self._execution_times: dict[str, list[datetime]] = defaultdict(list)
    
    async def should_execute(self, action_id: str, context: dict) -> bool:
        """Check if within rate limit"""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        # Clean old entries
        self._execution_times[action_id] = [
            t for t in self._execution_times[action_id]
            if t > window_start
        ]
        
        # Check limit
        if len(self._execution_times[action_id]) >= self.max_executions:
            self.logger.debug(f"Rate limit exceeded for {action_id}")
            return False
        
        return True
    
    async def on_execute(self, action_id: str, context: dict) -> None:
        """Record execution time"""
        self._execution_times[action_id].append(datetime.utcnow())


class CooldownPolicy(ExecutionPolicy):
    """
    Cooldown policy - enforces minimum time between executions.
    """
    
    policy_type = "cooldown"
    
    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        self.cooldown_seconds = self.params.get("cooldown_seconds", 10)
        self._last_execution: dict[str, datetime] = {}
    
    async def should_execute(self, action_id: str, context: dict) -> bool:
        """Check if cooldown has passed"""
        now = datetime.utcnow()
        
        last_exec = self._last_execution.get(action_id)
        if last_exec:
            elapsed = (now - last_exec).total_seconds()
            if elapsed < self.cooldown_seconds:
                self.logger.debug(f"Cooldown active for {action_id}, {self.cooldown_seconds - elapsed:.1f}s remaining")
                return False
        
        return True
    
    async def on_execute(self, action_id: str, context: dict) -> None:
        """Update last execution time"""
        self._last_execution[action_id] = datetime.utcnow()


class ConditionalPolicy(ExecutionPolicy):
    """
    Conditional policy - executes only if a condition is met.
    Uses a simple expression evaluator on the event data.
    """
    
    policy_type = "conditional"
    
    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        self.condition = self.params.get("condition", {})  # Filter-like condition
    
    async def should_execute(self, action_id: str, context: dict) -> bool:
        """Evaluate condition"""
        from .filters import Filter
        
        try:
            if not self.condition:
                return True
            
            event = context.get("event", {})
            event_data = event.get("data", {}) if isinstance(event, dict) else getattr(event, "data", {})
            
            # Create filter from condition and evaluate
            filter_obj = Filter.from_config(self.condition)
            return filter_obj.evaluate(event_data)
            
        except Exception as e:
            self.logger.error(f"Error evaluating condition: {e}")
            return True  # Default to execute on error
    
    async def on_execute(self, action_id: str, context: dict) -> None:
        pass


class CompositePolicy(ExecutionPolicy):
    """Combine multiple policies with AND/OR logic"""
    
    policy_type = "composite"
    
    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        self.operator = self.params.get("operator", "and")  # "and" or "or"
        self.policies: list[ExecutionPolicy] = []
        
        policy_configs = self.params.get("policies", [])
        for config in policy_configs:
            self.policies.append(ExecutionPolicy.from_config(config))
    
    async def should_execute(self, action_id: str, context: dict) -> bool:
        """Evaluate all policies"""
        if not self.policies:
            return True
        
        results = []
        for policy in self.policies:
            result = await policy.should_execute(action_id, context)
            results.append(result)
        
        if self.operator == "and":
            return all(results)
        elif self.operator == "or":
            return any(results)
        else:
            return all(results)
    
    async def on_execute(self, action_id: str, context: dict) -> None:
        """Notify all policies of execution"""
        for policy in self.policies:
            await policy.on_execute(action_id, context)


# Policy registry
POLICY_TYPES = {
    "none": NoPolicy,
    "debounce": DebouncePolicy,
    "rate_limit": RateLimitPolicy,
    "cooldown": CooldownPolicy,
    "conditional": ConditionalPolicy,
    "composite": CompositePolicy,
}


def create_policy(config: dict) -> ExecutionPolicy:
    """Factory function to create policies from config"""
    return ExecutionPolicy.from_config(config)

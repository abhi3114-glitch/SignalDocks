"""
SignalDock Pipeline Filters
"""
from abc import ABC, abstractmethod
from typing import Any, Optional, List
from datetime import datetime, time
import re
import logging

logger = logging.getLogger(__name__)


class Filter(ABC):
    """Abstract base class for pipeline filters"""
    
    filter_type: str = "base"
    
    def __init__(self, params: Optional[dict] = None):
        self.params = params or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def evaluate(self, event_data: dict) -> bool:
        """
        Evaluate if the event passes the filter.
        
        Args:
            event_data: Event data dictionary
        
        Returns:
            True if event passes filter, False otherwise
        """
        pass
    
    @classmethod
    def from_config(cls, config: dict) -> "Filter":
        """Create filter from configuration dict"""
        filter_type = config.get("type", "boolean")
        params = config.get("params", {})
        
        if filter_type == "boolean":
            return BooleanFilter(params)
        elif filter_type == "time_window":
            return TimeWindowFilter(params)
        elif filter_type == "composite":
            return CompositeFilter(params)
        else:
            raise ValueError(f"Unknown filter type: {filter_type}")


class BooleanFilter(Filter):
    """Boolean condition filter"""
    
    filter_type = "boolean"
    
    OPERATORS = {
        "equals": lambda a, b: a == b,
        "==": lambda a, b: a == b,
        "not_equals": lambda a, b: a != b,
        "!=": lambda a, b: a != b,
        "greater_than": lambda a, b: float(a) > float(b),
        ">": lambda a, b: float(a) > float(b),
        "less_than": lambda a, b: float(a) < float(b),
        "<": lambda a, b: float(a) < float(b),
        "greater_equal": lambda a, b: float(a) >= float(b),
        ">=": lambda a, b: float(a) >= float(b),
        "less_equal": lambda a, b: float(a) <= float(b),
        "<=": lambda a, b: float(a) <= float(b),
        "contains": lambda a, b: str(b) in str(a),
        "not_contains": lambda a, b: str(b) not in str(a),
        "starts_with": lambda a, b: str(a).startswith(str(b)),
        "ends_with": lambda a, b: str(a).endswith(str(b)),
        "matches": lambda a, b: bool(re.match(str(b), str(a))),
        "is_true": lambda a, b: bool(a),
        "is_false": lambda a, b: not bool(a),
        "is_null": lambda a, b: a is None,
        "is_not_null": lambda a, b: a is not None,
    }
    
    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        self.field = self.params.get("field", "")
        self.operator = self.params.get("operator", "equals")
        self.value = self.params.get("value")
    
    def evaluate(self, event_data: dict) -> bool:
        """Evaluate boolean condition"""
        try:
            # Get field value using dot notation
            field_value = self._get_nested_value(event_data, self.field)
            
            # debug log
            self.logger.info(f"Evaluating filter: field='{self.field}' value='{field_value}' ({type(field_value)}) operator='{self.operator}' target='{self.value}' ({type(self.value)})")
            
            # Get operator function
            op_func = self.OPERATORS.get(self.operator)
            if not op_func:
                self.logger.warning(f"Unknown operator: {self.operator}")
                return False
            
            # Safety checks for None values
            # Skip value check for operators that don't need it
            unary_ops = ["is_null", "is_not_null", "is_true", "is_false"]
            
            if self.operator not in unary_ops:
                if self.value is None:
                    self.logger.warning("Filter value is None")
                    return False
                if field_value is None:
                    self.logger.warning(f"Field value for '{self.field}' is None")
                    return False
            
            result = op_func(field_value, self.value)
            self.logger.info(f"Filter result: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error evaluating filter: {e}")
            return False
    
    def _get_nested_value(self, data: dict, field_path: str) -> Any:
        """Get value from nested dict using dot notation with fallback to data key"""
        # Try finding field directly
        value = self._resolve_path(data, field_path)
        
        # If not found, and 'data' exists (SignalEvent structure), try inside 'data'
        if value is None and "data" in data and isinstance(data["data"], dict):
            value = self._resolve_path(data["data"], field_path)
            
        return value

    def _resolve_path(self, data: dict, field_path: str) -> Any:
        """Helper to resolve dot notation path"""
        keys = field_path.split(".")
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        
        return value


class TimeWindowFilter(Filter):
    """Time-based filter for scheduling"""
    
    filter_type = "time_window"
    
    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        self.start_time = self.params.get("start_time")  # "HH:MM"
        self.end_time = self.params.get("end_time")  # "HH:MM"
        self.days_of_week = self.params.get("days_of_week")  # [0-6], 0=Monday
        self.timezone = self.params.get("timezone", "local")
    
    def evaluate(self, event_data: dict) -> bool:
        """Evaluate if current time is within window"""
        try:
            now = datetime.now()
            current_time = now.time()
            current_day = now.weekday()
            
            # Check day of week
            if self.days_of_week is not None:
                if current_day not in self.days_of_week:
                    return False
            
            # Check time window
            if self.start_time and self.end_time:
                start = self._parse_time(self.start_time)
                end = self._parse_time(self.end_time)
                
                if start <= end:
                    # Normal window (e.g., 09:00 to 17:00)
                    if not (start <= current_time <= end):
                        return False
                else:
                    # Overnight window (e.g., 22:00 to 06:00)
                    if not (current_time >= start or current_time <= end):
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error evaluating time filter: {e}")
            return False
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object"""
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))


class CompositeFilter(Filter):
    """Composite filter combining multiple filters"""
    
    filter_type = "composite"
    
    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        self.operator = self.params.get("operator", "and")  # "and", "or", "not"
        self.filters: List[Filter] = []
        
        # Create child filters from config
        filter_configs = self.params.get("filters", [])
        for config in filter_configs:
            self.filters.append(Filter.from_config(config))
    
    def evaluate(self, event_data: dict) -> bool:
        """Evaluate composite condition"""
        if not self.filters:
            return True
        
        try:
            if self.operator == "and":
                return all(f.evaluate(event_data) for f in self.filters)
            elif self.operator == "or":
                return any(f.evaluate(event_data) for f in self.filters)
            elif self.operator == "not":
                # NOT only applies to first filter
                return not self.filters[0].evaluate(event_data)
            else:
                self.logger.warning(f"Unknown composite operator: {self.operator}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error evaluating composite filter: {e}")
            return False
    
    def add_filter(self, filter_obj: Filter) -> None:
        """Add a filter to the composite"""
        self.filters.append(filter_obj)


# Filter registry
FILTER_TYPES = {
    "boolean": BooleanFilter,
    "time_window": TimeWindowFilter,
    "composite": CompositeFilter,
}


def create_filter(config: dict) -> Filter:
    """Factory function to create filters from config"""
    return Filter.from_config(config)

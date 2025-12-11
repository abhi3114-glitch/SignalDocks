"""
SignalDock Pipeline Transformers
"""
from abc import ABC, abstractmethod
from typing import Any, Optional
import re
import json
import logging

logger = logging.getLogger(__name__)


class Transformer(ABC):
    """Abstract base class for data transformers"""
    
    transformer_type: str = "base"
    
    def __init__(self, params: Optional[dict] = None):
        self.params = params or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def transform(self, event_data: dict) -> dict:
        """
        Transform event data.
        
        Args:
            event_data: Event data dictionary
        
        Returns:
            Transformed event data dictionary
        """
        pass
    
    @classmethod
    def from_config(cls, config: dict) -> "Transformer":
        """Create transformer from configuration dict"""
        transformer_type = config.get("type", "passthrough")
        params = config.get("params", {})
        
        if transformer_type == "extract_field":
            return ExtractFieldTransformer(params)
        elif transformer_type == "format_string":
            return FormatStringTransformer(params)
        elif transformer_type == "math":
            return MathTransformer(params)
        elif transformer_type == "json_path":
            return JsonPathTransformer(params)
        elif transformer_type == "passthrough":
            return PassthroughTransformer(params)
        else:
            raise ValueError(f"Unknown transformer type: {transformer_type}")


class PassthroughTransformer(Transformer):
    """Pass data through unchanged"""
    
    transformer_type = "passthrough"
    
    def transform(self, event_data: dict) -> dict:
        return event_data


class ExtractFieldTransformer(Transformer):
    """Extract specific fields from event data"""
    
    transformer_type = "extract_field"
    
    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        self.fields = self.params.get("fields", [])  # List of field paths
        self.output_key = self.params.get("output_key", "extracted")
        self.flatten = self.params.get("flatten", False)
    
    def transform(self, event_data: dict) -> dict:
        """Extract specified fields"""
        try:
            result = event_data.copy()
            extracted = {}
            
            for field_path in self.fields:
                value = self._get_nested_value(event_data, field_path)
                
                if self.flatten:
                    # Use last part of path as key
                    key = field_path.split(".")[-1]
                else:
                    key = field_path
                
                extracted[key] = value
            
            result[self.output_key] = extracted
            return result
            
        except Exception as e:
            self.logger.error(f"Error extracting fields: {e}")
            return event_data
    
    def _get_nested_value(self, data: dict, field_path: str) -> Any:
        """Get value from nested dict using dot notation"""
        keys = field_path.split(".")
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                idx = int(key)
                value = value[idx] if idx < len(value) else None
            else:
                return None
        
        return value


class FormatStringTransformer(Transformer):
    """Format string template with event data"""
    
    transformer_type = "format_string"
    
    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        self.template = self.params.get("template", "")
        self.output_key = self.params.get("output_key", "formatted")
    
    def transform(self, event_data: dict) -> dict:
        """Format string template"""
        try:
            result = event_data.copy()
            formatted = self.template
            
            # Replace {field.path} placeholders
            pattern = r'\{([^}]+)\}'
            matches = re.findall(pattern, self.template)
            
            for match in matches:
                value = self._get_nested_value(event_data, match)
                placeholder = "{" + match + "}"
                formatted = formatted.replace(placeholder, str(value) if value is not None else "")
            
            result[self.output_key] = formatted
            return result
            
        except Exception as e:
            self.logger.error(f"Error formatting string: {e}")
            return event_data
    
    def _get_nested_value(self, data: dict, field_path: str) -> Any:
        """Get value from nested dict using dot notation"""
        keys = field_path.split(".")
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        
        return value


class MathTransformer(Transformer):
    """Perform mathematical operations"""
    
    transformer_type = "math"
    
    OPERATIONS = {
        "add": lambda a, b: a + b,
        "subtract": lambda a, b: a - b,
        "multiply": lambda a, b: a * b,
        "divide": lambda a, b: a / b if b != 0 else 0,
        "modulo": lambda a, b: a % b if b != 0 else 0,
        "power": lambda a, b: a ** b,
        "min": min,
        "max": max,
        "abs": lambda a, b=None: abs(a),
        "round": lambda a, b=0: round(a, int(b)) if b else round(a),
    }
    
    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        self.field = self.params.get("field", "")
        self.operation = self.params.get("operation", "add")
        self.operand = self.params.get("operand", 0)
        self.output_key = self.params.get("output_key", "result")
    
    def transform(self, event_data: dict) -> dict:
        """Perform math operation"""
        try:
            result = event_data.copy()
            value = self._get_nested_value(event_data, self.field)
            
            if value is None:
                return event_data
            
            op_func = self.OPERATIONS.get(self.operation)
            if not op_func:
                self.logger.warning(f"Unknown operation: {self.operation}")
                return event_data
            
            calculated = op_func(float(value), float(self.operand))
            result[self.output_key] = calculated
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in math transform: {e}")
            return event_data
    
    def _get_nested_value(self, data: dict, field_path: str) -> Any:
        """Get value from nested dict using dot notation"""
        keys = field_path.split(".")
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        
        return value


class JsonPathTransformer(Transformer):
    """Extract data using JSONPath-like expressions"""
    
    transformer_type = "json_path"
    
    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        self.path = self.params.get("path", "$")
        self.output_key = self.params.get("output_key", "json_result")
    
    def transform(self, event_data: dict) -> dict:
        """Extract using JSONPath"""
        try:
            result = event_data.copy()
            
            # Simple JSONPath implementation
            # Supports: $.field, $.field.subfield, $[0], $.field[0]
            path = self.path
            if path.startswith("$"):
                path = path[1:]
            if path.startswith("."):
                path = path[1:]
            
            value = self._eval_path(event_data, path)
            result[self.output_key] = value
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in JSONPath transform: {e}")
            return event_data
    
    def _eval_path(self, data: Any, path: str) -> Any:
        """Evaluate a simple JSONPath expression"""
        if not path:
            return data
        
        # Handle array index
        match = re.match(r'^([^\[\]]+)?\[(\d+)\](.*)$', path)
        if match:
            field, idx, rest = match.groups()
            if field:
                data = data.get(field) if isinstance(data, dict) else None
            if data is not None and isinstance(data, list):
                data = data[int(idx)] if int(idx) < len(data) else None
            return self._eval_path(data, rest.lstrip('.'))
        
        # Handle field access
        parts = path.split(".", 1)
        field = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        
        if isinstance(data, dict):
            data = data.get(field)
        else:
            return None
        
        return self._eval_path(data, rest)


# Transformer registry
TRANSFORMER_TYPES = {
    "passthrough": PassthroughTransformer,
    "extract_field": ExtractFieldTransformer,
    "format_string": FormatStringTransformer,
    "math": MathTransformer,
    "json_path": JsonPathTransformer,
}


def create_transformer(config: dict) -> Transformer:
    """Factory function to create transformers from config"""
    return Transformer.from_config(config)

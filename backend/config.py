"""
SignalDock Configuration Management
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
from typing import Optional
import json


class SignalConfig(BaseSettings):
    """Signal source configuration"""
    cpu_poll_interval: float = Field(default=2.0, description="CPU polling interval in seconds")
    ram_poll_interval: float = Field(default=2.0, description="RAM polling interval in seconds")
    battery_poll_interval: float = Field(default=10.0, description="Battery polling interval in seconds")
    network_poll_interval: float = Field(default=5.0, description="Network polling interval in seconds")
    clipboard_poll_interval: float = Field(default=1.0, description="Clipboard polling interval in seconds")
    window_poll_interval: float = Field(default=0.5, description="Window focus polling interval in seconds")
    
    # Thresholds
    cpu_high_threshold: float = Field(default=80.0, description="CPU high usage threshold percentage")
    cpu_low_threshold: float = Field(default=20.0, description="CPU low usage threshold percentage")
    ram_high_threshold: float = Field(default=85.0, description="RAM high usage threshold percentage")
    battery_low_threshold: float = Field(default=20.0, description="Battery low threshold percentage")
    battery_critical_threshold: float = Field(default=10.0, description="Battery critical threshold percentage")


class PermissionConfig(BaseSettings):
    """Permission settings for sensitive features"""
    clipboard_enabled: bool = Field(default=True, description="Enable clipboard monitoring")
    microphone_enabled: bool = Field(default=True, description="Enable microphone monitoring")
    shell_execution_enabled: bool = Field(default=True, description="Enable shell script execution")
    file_operations_enabled: bool = Field(default=True, description="Enable file move/copy operations")
    process_control_enabled: bool = Field(default=True, description="Enable process pause/resume")
    network_control_enabled: bool = Field(default=True, description="Enable network toggle")


class DatabaseConfig(BaseSettings):
    """Database configuration"""
    database_path: Path = Field(default=Path("signaldock.db"), description="SQLite database path")
    
    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.database_path}"


class WebSocketConfig(BaseSettings):
    """WebSocket configuration"""
    host: str = Field(default="127.0.0.1", description="WebSocket host")
    port: int = Field(default=8765, description="WebSocket port")
    heartbeat_interval: float = Field(default=30.0, description="Heartbeat interval in seconds")
    reconnect_delay: float = Field(default=5.0, description="Reconnect delay in seconds")


class AppConfig(BaseSettings):
    """Main application configuration"""
    app_name: str = "SignalDock"
    version: str = "1.0.0"
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Sub-configurations
    signals: SignalConfig = Field(default_factory=SignalConfig)
    permissions: PermissionConfig = Field(default_factory=PermissionConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    
    # Paths
    templates_dir: Path = Field(default=Path("templates"), description="Pipeline templates directory")
    config_file: Optional[Path] = Field(default=None, description="External config file path")
    
    class Config:
        env_prefix = "SIGNALDOCK_"
        env_nested_delimiter = "__"
    
    def save_to_file(self, path: Path) -> None:
        """Save configuration to JSON file"""
        with open(path, 'w') as f:
            json.dump(self.model_dump(), f, indent=2, default=str)
    
    @classmethod
    def load_from_file(cls, path: Path) -> "AppConfig":
        """Load configuration from JSON file"""
        with open(path, 'r') as f:
            data = json.load(f)
        return cls(**data)


# Global configuration instance
config = AppConfig()


def get_config() -> AppConfig:
    """Get the global configuration instance"""
    return config


def reload_config(path: Optional[Path] = None) -> AppConfig:
    """Reload configuration from file"""
    global config
    if path and path.exists():
        config = AppConfig.load_from_file(path)
    else:
        config = AppConfig()
    return config

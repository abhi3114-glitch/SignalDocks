"""
SignalDock Signal Sources Package
"""
from .base import SignalSource, SignalEvent
from .cpu import CPUSignalSource
from .battery import BatterySignalSource
from .network import NetworkSignalSource
from .filesystem import FilesystemSignalSource
from .window import WindowFocusSignalSource
from .clipboard import ClipboardSignalSource

__all__ = [
    "SignalSource",
    "SignalEvent",
    "CPUSignalSource",
    "BatterySignalSource",
    "NetworkSignalSource",
    "FilesystemSignalSource",
    "WindowFocusSignalSource",
    "ClipboardSignalSource"
]


# Registry of available signal sources
SIGNAL_SOURCES = {
    "cpu": CPUSignalSource,
    "battery": BatterySignalSource,
    "network": NetworkSignalSource,
    "filesystem": FilesystemSignalSource,
    "window_focus": WindowFocusSignalSource,
    "clipboard": ClipboardSignalSource,
}


def get_signal_source(source_type: str) -> type:
    """Get signal source class by type name"""
    if source_type not in SIGNAL_SOURCES:
        raise ValueError(f"Unknown signal source type: {source_type}")
    return SIGNAL_SOURCES[source_type]


def list_signal_sources() -> list[dict]:
    """List all available signal sources with metadata"""
    sources = []
    for name, cls in SIGNAL_SOURCES.items():
        sources.append({
            "type": name,
            "name": cls.display_name if hasattr(cls, 'display_name') else name,
            "description": cls.description if hasattr(cls, 'description') else "",
            "requires_permission": cls.requires_permission if hasattr(cls, 'requires_permission') else False,
        })
    return sources

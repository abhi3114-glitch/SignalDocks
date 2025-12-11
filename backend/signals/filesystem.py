"""
SignalDock Filesystem Signal Source
"""
import asyncio
from pathlib import Path
from typing import Optional, Set
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .base import SignalSource, SignalEvent, EventType


class FilesystemEventHandler(FileSystemEventHandler):
    """Handler for watchdog filesystem events"""
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.patterns: Set[str] = set()  # File patterns to watch (empty = all)
        self.ignore_patterns: Set[str] = set()  # Patterns to ignore
    
    def _should_process(self, path: str) -> bool:
        """Check if path matches filter patterns"""
        path_obj = Path(path)
        
        # Check ignore patterns
        for pattern in self.ignore_patterns:
            if path_obj.match(pattern):
                return False
        
        # If no patterns set, process all
        if not self.patterns:
            return True
        
        # Check include patterns
        for pattern in self.patterns:
            if path_obj.match(pattern):
                return True
        
        return False
    
    def _create_event(self, event_type: EventType, event: FileSystemEvent) -> SignalEvent:
        """Create a SignalEvent from a watchdog event"""
        path = Path(event.src_path)
        
        data = {
            "path": str(path),
            "filename": path.name,
            "extension": path.suffix,
            "is_directory": event.is_directory,
        }
        
        # Add destination for move events
        if hasattr(event, 'dest_path'):
            dest = Path(event.dest_path)
            data["dest_path"] = str(dest)
            data["dest_filename"] = dest.name
        
        return SignalEvent(
            event_type=event_type,
            data=data,
            metadata={
                "event_class": event.__class__.__name__
            }
        )
    
    def on_created(self, event: FileSystemEvent):
        if self._should_process(event.src_path):
            signal_event = self._create_event(EventType.CREATED, event)
            self.callback(signal_event)
    
    def on_modified(self, event: FileSystemEvent):
        if self._should_process(event.src_path):
            signal_event = self._create_event(EventType.MODIFIED, event)
            self.callback(signal_event)
    
    def on_deleted(self, event: FileSystemEvent):
        if self._should_process(event.src_path):
            signal_event = self._create_event(EventType.DELETED, event)
            self.callback(signal_event)
    
    def on_moved(self, event: FileSystemEvent):
        if self._should_process(event.src_path):
            signal_event = self._create_event(EventType.MOVED, event)
            self.callback(signal_event)


class FilesystemSignalSource(SignalSource):
    """Filesystem events monitoring using watchdog"""
    
    display_name = "Filesystem"
    description = "Monitors file creation, modification, deletion, and moves"
    requires_permission = False
    
    def __init__(self, 
                 name: str = "filesystem_monitor",
                 watch_paths: Optional[list[str]] = None,
                 patterns: Optional[list[str]] = None,
                 ignore_patterns: Optional[list[str]] = None,
                 recursive: bool = True):
        super().__init__(name)
        
        self.watch_paths = watch_paths or []
        self.patterns = set(patterns or [])
        self.ignore_patterns = set(ignore_patterns or ["*.tmp", "*.swp", "~*", ".git/*"])
        self.recursive = recursive
        
        self._observer: Optional[Observer] = None
        self._event_handler: Optional[FilesystemEventHandler] = None
        self._pending_events: asyncio.Queue = asyncio.Queue()
    
    def get_poll_interval(self) -> float:
        return 0.1  # Fast polling for queued events
    
    def _on_fs_event(self, event: SignalEvent):
        """Callback for filesystem events (runs in watchdog thread)"""
        try:
            # Use thread-safe method to queue event
            asyncio.get_event_loop().call_soon_threadsafe(
                lambda: self._pending_events.put_nowait(event)
            )
        except RuntimeError:
            # No event loop running, queue directly
            try:
                self._pending_events.put_nowait(event)
            except:
                pass
    
    async def _poll(self) -> Optional[SignalEvent]:
        """Check for pending filesystem events"""
        try:
            event = self._pending_events.get_nowait()
            event.source_type = self.source_type
            event.source_name = self.name
            return event
        except asyncio.QueueEmpty:
            return None
    
    async def start(self) -> None:
        """Start the filesystem observer"""
        if self._running:
            return
        
        if not self.watch_paths:
            self.logger.warning("No watch paths configured")
            return
        
        # Create event handler
        self._event_handler = FilesystemEventHandler(self._on_fs_event)
        self._event_handler.patterns = self.patterns
        self._event_handler.ignore_patterns = self.ignore_patterns
        
        # Create and start observer
        self._observer = Observer()
        
        for path in self.watch_paths:
            path_obj = Path(path)
            if path_obj.exists():
                self._observer.schedule(
                    self._event_handler,
                    str(path_obj),
                    recursive=self.recursive
                )
                self.logger.info(f"Watching: {path}")
            else:
                self.logger.warning(f"Watch path does not exist: {path}")
        
        self._observer.start()
        
        # Start the base polling loop
        await super().start()
    
    async def stop(self) -> None:
        """Stop the filesystem observer"""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        
        await super().stop()
    
    def add_watch_path(self, path: str) -> bool:
        """Add a new path to watch"""
        path_obj = Path(path)
        if not path_obj.exists():
            return False
        
        if path not in self.watch_paths:
            self.watch_paths.append(path)
            
            if self._observer and self._event_handler:
                self._observer.schedule(
                    self._event_handler,
                    str(path_obj),
                    recursive=self.recursive
                )
        
        return True
    
    def get_config_schema(self) -> dict:
        return {
            "watch_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Paths to watch for file events",
                "default": []
            },
            "patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "File patterns to include (e.g., *.txt, *.docx)",
                "default": []
            },
            "ignore_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "File patterns to ignore",
                "default": ["*.tmp", "*.swp", "~*", ".git/*"]
            },
            "recursive": {
                "type": "boolean",
                "description": "Watch subdirectories recursively",
                "default": True
            }
        }

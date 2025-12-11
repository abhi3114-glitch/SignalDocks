"""
SignalDock File Operations Action
"""
import shutil
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from .base import Action, ActionResult


class FileOperationAction(Action):
    """File move/copy/archive operations"""
    
    display_name = "File Operation"
    description = "Move, copy, or archive files (requires permission)"
    requires_permission = True
    permission_type = "file_operations"
    
    OPERATIONS = ["move", "copy", "delete", "archive", "rename", "create_file", "create_dir"]
    
    def __init__(self, name: str = "file_operation_action", params: Optional[dict] = None):
        super().__init__(name, params)
    
    async def execute(self, context: dict) -> ActionResult:
        """Execute file operation"""
        params = context.get("params", {})
        event = context.get("event", {})
        
        operation = params.get("operation", "copy")
        source = params.get("source", "")
        destination = params.get("destination", "")
        create_dirs = params.get("create_dirs", True)
        overwrite = params.get("overwrite", False)
        
        # Get source from event if not specified
        if not source and event:
            event_data = event.get("data", {}) if isinstance(event, dict) else event.data
            source = event_data.get("path", "")
        
        # Template substitution
        if event:
            event_data = event.get("data", {}) if isinstance(event, dict) else event.data
            source = self._substitute_template(source, event_data)
            destination = self._substitute_template(destination, event_data)
        
        if not source:
            return ActionResult.failure("No source file specified")
        
        source_path = Path(source)
        if not source_path.exists() and operation not in ["archive", "create_file", "create_dir"]:
            return ActionResult.failure(f"Source file does not exist: {source}")
        
        try:
            if operation == "move":
                return await self._move_file(source_path, destination, create_dirs, overwrite)
            elif operation == "copy":
                return await self._copy_file(source_path, destination, create_dirs, overwrite)
            elif operation == "delete":
                return await self._delete_file(source_path)
            elif operation == "archive":
                return await self._archive_file(source_path, destination)
            elif operation == "rename":
                return await self._rename_file(source_path, destination)
            elif operation == "create_file":
                # For create_file, source represents the target path
                content = params.get("content", "")
                # Template substitution for content
                if event:
                     event_data = event.get("data", {}) if isinstance(event, dict) else event.data
                     content = self._substitute_template(content, event_data)
                return await self._create_file(source_path, content, overwrite)
            elif operation == "create_dir":
                return await self._create_dir(source_path)
            else:
                return ActionResult.failure(f"Unknown operation: {operation}")
                
        except Exception as e:
            return ActionResult.failure(str(e))
    
    async def _move_file(self, source: Path, destination: str, create_dirs: bool, overwrite: bool) -> ActionResult:
        """Move file to destination"""
        if not destination:
            return ActionResult.failure("Destination required for move operation")
        
        dest_path = Path(destination)
        
        if create_dirs:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        if dest_path.exists() and not overwrite:
            return ActionResult.failure(f"Destination already exists: {destination}")
        
        shutil.move(str(source), str(dest_path))
        
        return ActionResult.success(
            message=f"File moved to {destination}",
            data={"source": str(source), "destination": str(dest_path)}
        )
    
    async def _copy_file(self, source: Path, destination: str, create_dirs: bool, overwrite: bool) -> ActionResult:
        """Copy file to destination"""
        if not destination:
            return ActionResult.failure("Destination required for copy operation")
        
        dest_path = Path(destination)
        
        if create_dirs:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        if dest_path.exists() and not overwrite:
            return ActionResult.failure(f"Destination already exists: {destination}")
        
        if source.is_dir():
            shutil.copytree(str(source), str(dest_path), dirs_exist_ok=overwrite)
        else:
            shutil.copy2(str(source), str(dest_path))
        
        return ActionResult.success(
            message=f"File copied to {destination}",
            data={"source": str(source), "destination": str(dest_path)}
        )
    
    async def _delete_file(self, source: Path) -> ActionResult:
        """Delete file or directory"""
        if source.is_dir():
            shutil.rmtree(str(source))
        else:
            source.unlink()
        
        return ActionResult.success(
            message=f"File deleted: {source}",
            data={"deleted": str(source)}
        )
    
    async def _archive_file(self, source: Path, destination: str) -> ActionResult:
        """Create archive from file or directory"""
        if not destination:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = f"{source.stem}_{timestamp}.zip"
        
        dest_path = Path(destination)
        
        # Determine archive format from extension
        archive_format = "zip"
        if dest_path.suffix in [".tar", ".gz", ".bz2"]:
            archive_format = "tar"
        elif dest_path.suffix == ".zip":
            archive_format = "zip"
        
        archive_path = shutil.make_archive(
            str(dest_path.with_suffix("")),
            archive_format,
            str(source.parent),
            str(source.name)
        )
        
        return ActionResult.success(
            message=f"Archive created: {archive_path}",
            data={"source": str(source), "archive": archive_path}
        )
    
    async def _rename_file(self, source: Path, new_name: str) -> ActionResult:
        """Rename file"""
        if not new_name:
            return ActionResult.failure("New name required for rename operation")
        
        new_path = source.parent / new_name
        
        if new_path.exists():
            return ActionResult.failure(f"File already exists: {new_path}")
        
        source.rename(new_path)
        
        return ActionResult.success(
            message=f"File renamed to {new_name}",
            data={"source": str(source), "new_name": str(new_path)}
        )
    
    async def _create_file(self, path: Path, content: str, overwrite: bool) -> ActionResult:
        """Create new file with content"""
        if path.exists() and not overwrite:
            return ActionResult.failure(f"File already exists: {path}")
            
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            return ActionResult.success(
                message=f"File created: {path}",
                data={"path": str(path), "size": len(content)}
            )
        except Exception as e:
            return ActionResult.failure(f"Failed to create file: {e}")

    async def _create_dir(self, path: Path) -> ActionResult:
        """Create directory"""
        try:
            path.mkdir(parents=True, exist_ok=True)
            return ActionResult.success(
                message=f"Directory created: {path}",
                data={"path": str(path)}
            )
        except Exception as e:
            return ActionResult.failure(f"Failed to create directory: {e}")

    def _substitute_template(self, template: str, data: dict) -> str:
        """Substitute {key} placeholders with data values"""
        result = template
        
        # Add timestamp helpers
        now = datetime.now()
        data["_timestamp"] = now.strftime("%Y%m%d_%H%M%S")
        data["_date"] = now.strftime("%Y-%m-%d")
        data["_time"] = now.strftime("%H%M%S")
        
        for key, value in data.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result
    
    def validate_params(self, params: dict) -> tuple[bool, Optional[str]]:
        """Validate file operation parameters"""
        operation = params.get("operation", "copy")
        
        if operation not in self.OPERATIONS:
            return False, f"Invalid operation: {operation}. Must be one of: {self.OPERATIONS}"
        
        # Source validation
        source = params.get("source", "")
        if not source and operation != "archive":
            return False, "Source path is required"
        
        # Destination validation for operations that require it
        if operation in ["move", "copy", "rename"]:
            destination = params.get("destination", "")
            if not destination:
                return False, f"Destination is required for {operation} operation"
        
        return True, None
    
    def get_param_schema(self) -> dict:
        return {
            "operation": {
                "type": "string",
                "enum": self.OPERATIONS,
                "description": "File operation type",
                "default": "copy"
            },
            "source": {
                "type": "string",
                "description": "Source file path (or use event's path)",
                "default": ""
            },
            "destination": {
                "type": "string",
                "description": "Destination path (supports templates like {filename}, {_timestamp})",
                "default": ""
            },
            "create_dirs": {
                "type": "boolean",
                "description": "Create destination directories if needed",
                "default": True
            },
            "overwrite": {
                "type": "boolean",
                "description": "Overwrite existing files",
                "default": False
            }
        }

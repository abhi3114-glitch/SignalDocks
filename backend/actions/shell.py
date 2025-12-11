"""
SignalDock Shell Script Action
"""
import asyncio
import subprocess
import shlex
import platform
from typing import Optional

from .base import Action, ActionResult


class ShellAction(Action):
    """Run shell commands/scripts"""
    
    display_name = "Shell Command"
    description = "Execute shell commands (requires permission)"
    requires_permission = True
    permission_type = "shell_execution"
    
    def __init__(self, name: str = "shell_action", params: Optional[dict] = None):
        super().__init__(name, params)
        self._platform = platform.system()
    
    async def execute(self, context: dict) -> ActionResult:
        """Execute shell command"""
        params = context.get("params", {})
        event = context.get("event", {})
        
        command = params.get("command", "")
        timeout = params.get("timeout", 30)
        working_dir = params.get("working_dir")
        shell = params.get("shell", True)
        capture_output = params.get("capture_output", True)
        
        if not command:
            return ActionResult.failure("No command specified")
        
        # Template substitution
        if event:
            event_data = event.get("data", {}) if isinstance(event, dict) else event.data
            command = self._substitute_template(command, event_data)
        
        try:
            # Prepare command
            if shell:
                cmd = command
            else:
                cmd = shlex.split(command)
            
            # Run command
            process = await asyncio.create_subprocess_shell(
                cmd if shell else subprocess.list2cmdline(cmd),
                stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
                stderr=subprocess.PIPE if capture_output else subprocess.DEVNULL,
                cwd=working_dir
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ActionResult.failure(
                    f"Command timed out after {timeout} seconds",
                    message="Process was killed due to timeout"
                )
            
            # Decode output
            stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
            stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""
            
            if process.returncode == 0:
                return ActionResult.success(
                    message=f"Command executed successfully",
                    data={
                        "command": command,
                        "return_code": process.returncode,
                        "stdout": stdout_str[:1000],  # Limit output size
                        "stderr": stderr_str[:1000]
                    }
                )
            else:
                return ActionResult.failure(
                    f"Command failed with return code {process.returncode}",
                    message=stderr_str[:500] if stderr_str else "Unknown error"
                )
            
        except Exception as e:
            return ActionResult.failure(str(e))
    
    def _substitute_template(self, template: str, data: dict) -> str:
        """Substitute {key} placeholders with data values"""
        result = template
        for key, value in data.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                # Escape value for shell safety
                safe_value = str(value).replace('"', '\\"').replace("'", "\\'")
                result = result.replace(placeholder, safe_value)
        return result
    
    def validate_params(self, params: dict) -> tuple[bool, Optional[str]]:
        """Validate shell parameters"""
        command = params.get("command", "")
        if not command:
            return False, "Command is required"
        
        timeout = params.get("timeout", 30)
        if not isinstance(timeout, (int, float)) or timeout < 1:
            return False, "Timeout must be a positive number"
        
        # Basic safety checks
        dangerous_patterns = ["rm -rf /", "format c:", "del /s /q c:\\"]
        for pattern in dangerous_patterns:
            if pattern.lower() in command.lower():
                return False, f"Potentially dangerous command pattern detected: {pattern}"
        
        return True, None
    
    def get_param_schema(self) -> dict:
        return {
            "command": {
                "type": "string",
                "description": "Shell command to execute (supports {event_field} templates)",
                "required": True
            },
            "timeout": {
                "type": "integer",
                "description": "Command timeout in seconds",
                "default": 30,
                "min": 1,
                "max": 300
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory for the command",
                "default": None
            },
            "shell": {
                "type": "boolean",
                "description": "Execute through shell interpreter",
                "default": True
            },
            "capture_output": {
                "type": "boolean",
                "description": "Capture stdout and stderr",
                "default": True
            }
        }

"""
SignalDock Network Control Action
"""
import platform
import subprocess
from typing import Optional

from .base import Action, ActionResult


class NetworkControlAction(Action):
    """Control network adapters (enable/disable)"""
    
    display_name = "Network Control"
    description = "Enable or disable network adapters (requires permission)"
    requires_permission = True
    permission_type = "network_control"
    
    OPERATIONS = ["enable", "disable", "status"]
    
    def __init__(self, name: str = "network_control_action", params: Optional[dict] = None):
        super().__init__(name, params)
        self._platform = platform.system()
    
    async def execute(self, context: dict) -> ActionResult:
        """Execute network control operation"""
        self.logger.info(f"Executing network control with context keys: {list(context.keys())}")
        
        params = context.get("params", {})
        operation = params.get("operation", "status")
        adapter_name = params.get("adapter_name")
        
        self.logger.info(f"Network operation: {operation}, adapter: {adapter_name}")
        
        try:
            if self._platform == "Windows":
                return await self._windows_network_control(operation, adapter_name)
            elif self._platform == "Linux":
                return await self._linux_network_control(operation, adapter_name)
            else:
                return ActionResult.failure(f"Network control not supported on {self._platform}")
                
        except Exception as e:
            self.logger.error(f"Error executing network control: {e}")
            return ActionResult.failure(str(e))
    
    async def _windows_network_control(self, operation: str, adapter_name: Optional[str]) -> ActionResult:
        """Windows network control using netsh"""
        self.logger.info(f"Starting Windows network control: op={operation} adapter={adapter_name}")
        
        if operation == "status":
            return await self._get_network_status_windows()
        
        if not adapter_name:
            return ActionResult.failure("Adapter name required for enable/disable")

        # Idempotency check: Check if already in desired state
        try:
            status_result = await self._get_network_status_windows()
            if status_result.status == "success":
                adapters = status_result.data.get("adapters", [])
                # Case-insensitive match for adapter name
                target_adapter = next((a for a in adapters if a["name"].lower() == adapter_name.lower()), None)
                
                if target_adapter:
                    # state is usually "Enabled" or "Disabled"
                    current_state = target_adapter.get("admin_state", "").lower()
                    
                    if operation == "enable" and current_state == "enabled":
                        self.logger.info(f"Adapter '{adapter_name}' is already enabled. Skipping action.")
                        return ActionResult.success(
                            message=f"Adapter '{adapter_name}' is already enabled",
                            data={"adapter": adapter_name, "operation": operation, "skipped": True}
                        )
                    
                    if operation == "disable" and current_state == "disabled":
                        self.logger.info(f"Adapter '{adapter_name}' is already disabled. Skipping action.")
                        return ActionResult.success(
                            message=f"Adapter '{adapter_name}' is already disabled",
                            data={"adapter": adapter_name, "operation": operation, "skipped": True}
                        )
        except Exception as e:
            self.logger.warning(f"Failed to check current status for idempotency: {e}")
        
        # Use netsh to control adapter
        if operation == "enable":
            cmd = f'netsh interface set interface "{adapter_name}" enable'
            # Also try Disable-NetAdapter via PowerShell as fallback? No, netsh is standard.
        elif operation == "disable":
            cmd = f'netsh interface set interface "{adapter_name}" disable'
        else:
            return ActionResult.failure(f"Unknown operation: {operation}")
            
        self.logger.info(f"Running command: {cmd}")
        
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            self.logger.info(f"Command return code: {result.returncode}")
            if result.stdout:
                self.logger.info(f"Command stdout: {result.stdout}")
            if result.stderr:
                self.logger.warning(f"Command stderr: {result.stderr}")
            
            if result.returncode == 0:
                return ActionResult.success(
                    message=f"Adapter '{adapter_name}' {operation}d",
                    data={"adapter": adapter_name, "operation": operation}
                )
            else:
                self.logger.warning(f"Standard command failed (code {result.returncode}), trying elevated privileges...")
                
                # Fallback: Try running as Administrator via PowerShell
                # We assume failure was due to permissions
                try:
                    # Construct arguments for netsh
                    # Original: netsh interface set interface "Adapter Name" disable
                    args = f'interface set interface "{adapter_name}" {operation}'
                    
                    # Escape quotes for PowerShell string interpolation if needed, 
                    # but simple quotes usually work if wrapped in single quotes
                    ps_cmd = f"Start-Process netsh -ArgumentList '{args}' -Verb RunAs -WindowStyle Hidden -Wait"
                    
                    self.logger.info(f"Running elevated command: {ps_cmd}")
                    
                    elevated_result = subprocess.run(
                        ["powershell", "-Command", ps_cmd],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if elevated_result.returncode == 0:
                        return ActionResult.success(
                            message=f"Available Admin prompt triggered for '{adapter_name}' {operation}",
                            data={"adapter": adapter_name, "operation": operation, "mode": "elevated"}
                        )
                    else:
                        return ActionResult.failure(
                            f"Elevated execution failed: {elevated_result.stderr}",
                            message="Admin prompt failed or was denied"
                        )
                except Exception as e:
                    self.logger.error(f"Elevation error: {e}")
                    return ActionResult.failure(
                        result.stderr or "Failed to control network adapter",
                        message="Check adapter name and admin privileges"
                    )
        except subprocess.TimeoutExpired:
            return ActionResult.failure("Network control command timed out")
    
    async def _get_network_status_windows(self) -> ActionResult:
        """Get network adapter status on Windows"""
        try:
            result = subprocess.run(
                'netsh interface show interface',
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            adapters = []
            lines = result.stdout.strip().split('\n')
            
            for line in lines[3:]:  # Skip header lines
                parts = line.split()
                if len(parts) >= 4:
                    adapters.append({
                        "admin_state": parts[0],
                        "state": parts[1],
                        "type": parts[2],
                        "name": " ".join(parts[3:])
                    })
            
            return ActionResult.success(
                message=f"Found {len(adapters)} network adapters",
                data={"adapters": adapters}
            )
        except Exception as e:
            return ActionResult.failure(str(e))
    
    async def _linux_network_control(self, operation: str, adapter_name: Optional[str]) -> ActionResult:
        """Linux network control using ip command"""
        if operation == "status":
            return await self._get_network_status_linux()
        
        if not adapter_name:
            return ActionResult.failure("Adapter name required for enable/disable")
        
        # Use ip command (requires sudo/root)
        if operation == "enable":
            cmd = f'ip link set {adapter_name} up'
        elif operation == "disable":
            cmd = f'ip link set {adapter_name} down'
        else:
            return ActionResult.failure(f"Unknown operation: {operation}")
        
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return ActionResult.success(
                    message=f"Adapter '{adapter_name}' {operation}d",
                    data={"adapter": adapter_name, "operation": operation}
                )
            else:
                return ActionResult.failure(
                    result.stderr or "Failed to control network adapter",
                    message="Check adapter name and root privileges"
                )
        except subprocess.TimeoutExpired:
            return ActionResult.failure("Network control command timed out")
    
    async def _get_network_status_linux(self) -> ActionResult:
        """Get network adapter status on Linux"""
        try:
            result = subprocess.run(
                'ip -brief link show',
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            adapters = []
            for line in result.stdout.strip().split('\n'):
                parts = line.split()
                if len(parts) >= 2:
                    adapters.append({
                        "name": parts[0],
                        "state": parts[1],
                        "mac": parts[2] if len(parts) > 2 else None
                    })
            
            return ActionResult.success(
                message=f"Found {len(adapters)} network adapters",
                data={"adapters": adapters}
            )
        except Exception as e:
            return ActionResult.failure(str(e))
    
    def validate_params(self, params: dict) -> tuple[bool, Optional[str]]:
        """Validate network control parameters"""
        operation = params.get("operation", "status")
        
        if operation not in self.OPERATIONS:
            return False, f"Invalid operation: {operation}. Must be one of: {self.OPERATIONS}"
        
        if operation in ["enable", "disable"]:
            if not params.get("adapter_name"):
                return False, "Adapter name is required for enable/disable operations"
        
        return True, None
    
    def get_param_schema(self) -> dict:
        return {
            "operation": {
                "type": "string",
                "enum": self.OPERATIONS,
                "description": "Network control operation",
                "default": "status"
            },
            "adapter_name": {
                "type": "string",
                "description": "Network adapter name",
                "default": None
            }
        }

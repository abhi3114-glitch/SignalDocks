"""
SignalDock Process Control Action
"""
import psutil
import platform
from typing import Optional, List

from .base import Action, ActionResult


class ProcessControlAction(Action):
    """Control system processes (suspend/resume/terminate)"""
    
    display_name = "Process Control"
    description = "Suspend, resume, or terminate processes (requires permission)"
    requires_permission = True
    permission_type = "process_control"
    
    OPERATIONS = ["suspend", "resume", "terminate", "kill", "check"]
    
    def __init__(self, name: str = "process_control_action", params: Optional[dict] = None):
        super().__init__(name, params)
        self._platform = platform.system()
    
    async def execute(self, context: dict) -> ActionResult:
        """Execute process control operation"""
        params = context.get("params", {})
        
        operation = params.get("operation", "suspend")
        process_name = params.get("process_name")
        process_pid = params.get("pid")
        match_all = params.get("match_all", False)
        
        if not process_name and not process_pid:
            return ActionResult.failure("Either process_name or pid is required")
        
        try:
            processes = self._find_processes(process_name, process_pid)
            
            if not processes:
                # specific message for check operation
                if operation == "check":
                    return ActionResult.success(
                        message=f"Process not found: {process_name or process_pid}",
                        data={"found": False, "running": False}
                    )
                return ActionResult.failure(f"No process found matching: {process_name or process_pid}")
            
            results = []
            for proc in processes if match_all else [processes[0]]:
                result = await self._control_process(proc, operation)
                results.append(result)
                
                if not match_all:
                    break
            
            success_count = sum(1 for r in results if r["success"])
            
            # Special case for check
            if operation == "check":
                 return ActionResult.success(
                    message=f"Process found: {process_name or process_pid}",
                    data={"found": True, "running": True, "details": results}
                )

            if success_count == 0:
                return ActionResult.failure(
                    "No processes were controlled successfully",
                    message=str(results)
                )
            
            return ActionResult.success(
                message=f"Controlled {success_count} process(es)",
                data={
                    "operation": operation,
                    "results": results
                }
            )
            
        except Exception as e:
            return ActionResult.failure(str(e))
    
    def _find_processes(self, name: Optional[str], pid: Optional[int]) -> List[psutil.Process]:
        """Find processes by name or PID"""
        processes = []
        
        if pid:
            try:
                proc = psutil.Process(pid)
                if proc.is_running():
                    processes.append(proc)
            except psutil.NoSuchProcess:
                pass
        elif name:
            name_lower = name.lower()
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if name_lower in proc.info['name'].lower():
                        processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        return processes
    
    async def _control_process(self, process: psutil.Process, operation: str) -> dict:
        """Control a single process"""
        try:
            pid = process.pid
            name = process.name()
            
            if operation == "suspend":
                process.suspend()
                status = "suspended"
            elif operation == "resume":
                process.resume()
                status = "resumed"
            elif operation == "terminate":
                process.terminate()
                status = "terminated"
            elif operation == "kill":
                process.kill()
                status = "killed"
            elif operation == "check":
                status = "running"
            else:
                return {"success": False, "pid": pid, "name": name, "error": f"Unknown operation: {operation}"}
            
            return {"success": True, "pid": pid, "name": name, "status": status}
            
        except psutil.NoSuchProcess:
            return {"success": False, "pid": process.pid, "error": "Process no longer exists"}
        except psutil.AccessDenied:
            return {"success": False, "pid": process.pid, "error": "Access denied"}
        except Exception as e:
            return {"success": False, "pid": process.pid, "error": str(e)}
    
    def validate_params(self, params: dict) -> tuple[bool, Optional[str]]:
        """Validate process control parameters"""
        operation = params.get("operation", "suspend")
        
        if operation not in self.OPERATIONS:
            return False, f"Invalid operation: {operation}. Must be one of: {self.OPERATIONS}"
        
        process_name = params.get("process_name")
        pid = params.get("pid")
        
        if not process_name and not pid:
            return False, "Either process_name or pid is required"
        
        if pid and not isinstance(pid, int):
            return False, "PID must be an integer"
        
        return True, None
    
    def get_param_schema(self) -> dict:
        return {
            "operation": {
                "type": "string",
                "enum": self.OPERATIONS,
                "description": "Process control operation",
                "default": "suspend"
            },
            "process_name": {
                "type": "string",
                "description": "Name of process to control (partial match)",
                "default": None
            },
            "pid": {
                "type": "integer",
                "description": "Process ID to control",
                "default": None
            },
            "match_all": {
                "type": "boolean",
                "description": "Apply to all matching processes",
                "default": False
            }
        }
    
    @staticmethod
    def list_processes(filter_name: Optional[str] = None) -> List[dict]:
        """List running processes for UI selection"""
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                if filter_name and filter_name.lower() not in info['name'].lower():
                    continue
                    
                processes.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "cpu_percent": info['cpu_percent'],
                    "memory_percent": round(info['memory_percent'], 2) if info['memory_percent'] else 0
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return sorted(processes, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:50]

import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from actions.file_ops import FileOperationAction
from actions.process import ProcessControlAction
from actions.shell import ShellAction
from actions.network import NetworkControlAction
from config import PermissionConfig

async def test_all_features():
    print("🚀 Starting SignalDock Feature Integration Test...\n")
    
    results = {}
    
    # 1. Test File Creation (Persistent Proof)
    print("Testing File Operations...")
    file_action = FileOperationAction()
    test_file = Path("verified_features.log")
    
    # Create
    content = "SignalDock Verified Features:\n✅ File Operations Working\n✅ System permissions active"
    res_create = await file_action.execute({
        "params": {
            "operation": "create_file",
            "source": str(test_file),
            "content": content,
            "overwrite": True
        }
    })
    
    if res_create.success and test_file.exists():
        print(f"✅ File Creation: SUCCESS ({test_file} created)")
        results["File Ops"] = True
    else:
        print(f"❌ File Creation: FAILED - {res_create.error}")
        results["File Ops"] = False

    print("-" * 30)

    # 2. Test Shell Command
    print("Testing Shell Execution...")
    shell_action = ShellAction()
    res_shell = await shell_action.execute({
        "params": {
            "command": "echo 'SignalDock Shell Test'",
            "shell": True,
            "capture_output": True
        }
    })
    
    if res_shell.success and "SignalDock Shell Test" in res_shell.data.get("stdout", ""):
        print(f"✅ Shell Echo: SUCCESS (Output received)")
        results["Shell"] = True
    else:
        print(f"❌ Shell Echo: FAILED - {res_shell.error}")
        results["Shell"] = False

    print("-" * 30)

    # 3. Test Process Control (Check Status of Self)
    print("Testing Process Control...")
    process_action = ProcessControlAction()
    my_pid = os.getpid()
    
    res_proc = await process_action.execute({
        "params": {
            "operation": "check",
            "pid": my_pid
        }
    })
    
    if res_proc.success and res_proc.data.get("found") is True:
        print(f"✅ Process Check (Self PID {my_pid}): SUCCESS")
        results["Process"] = True
    else:
        print(f"❌ Process Check: FAILED - {res_proc.error}")
        results["Process"] = False

    print("-" * 30)

    # 4. Test Network Control (Status Only - Safe)
    print("Testing Network Control...")
    network_action = NetworkControlAction()
    
    res_net = await network_action.execute({
        "params": {"operation": "status"}
    })
    
    if res_net.success and "adapters" in res_net.data:
        adapter_count = len(res_net.data["adapters"])
        print(f"✅ Network Status: SUCCESS (Found {adapter_count} adapters)")
        results["Network"] = True
    else:
        print(f"❌ Network Status: FAILED - {res_net.error}")
        results["Network"] = False

    print("\n" + "=" * 30)
    print("TEST SUMMARY")
    print("=" * 30)
    
    all_passed = True
    for feature, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"{feature:>15}: {status}")
        if not passed:
            all_passed = False
            
    if all_passed:
        print("\n✨ ALL SYSTEMS OPERATIONAL ✨")
    else:
        print("\n⚠️ SOME CHECKS FAILED")

if __name__ == "__main__":
    try:
        asyncio.run(test_all_features())
    except ImportError as e:
        print(f"Import Error: {e}. Make sure you are running from 'backend' folder.")
    except Exception as e:
        print(f"Unexpected Error: {e}")

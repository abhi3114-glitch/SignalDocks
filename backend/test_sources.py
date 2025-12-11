import asyncio
import os
import sys
import logging

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from signals.clipboard import ClipboardSignalSource
from signals.window import WindowFocusSignalSource
from signals.cpu import CPUSignalSource
from signals.battery import BatterySignalSource
from signals.network import NetworkSignalSource
from signals.filesystem import FilesystemSignalSource
from signals.microphone import MicrophoneSignalSource

# Configure logging to show only our print statements clearly
logging.getLogger().setLevel(logging.ERROR)

async def test_all_sources_interactive():
    print("🕵️  SignalDock ULTIMATE Source Test")
    print("========================================")
    print("Listening for 15 seconds...")
    print("\nACTIONS TO TRY:")
    print("1. [ ] Copy text (Clipboard)")
    print("2. [ ] Switch windows (Window)")
    print("3. [ ] Create a file in 'C:/Temp' (Filesystem - if configured)")
    print("4. [ ] Watch CPU/Net stats stream")
    print("\nStarting Sensors...\n")
    
    # Instantiate all sources
    sources = {
        "Clipboard": ClipboardSignalSource(),
        "Window": WindowFocusSignalSource(),
        "CPU": CPUSignalSource(),
        "Battery": BatterySignalSource(),
        "Network": NetworkSignalSource(),
        "Mic": MicrophoneSignalSource(),
    }

    start_time = asyncio.get_event_loop().time()
    
    try:
        while (asyncio.get_event_loop().time() - start_time) < 15:
            # Poll all sources concurrently
            for name, source in sources.items():
                try:
                    event = await source._poll()
                    if event:
                        # Format output based on source
                        if name == "Clipboard":
                            print(f"📋 {name}: {event.data.get('content_preview')}")
                        elif name == "Window":
                            print(f"👀 {name}: {event.data.get('window_title')}")
                        elif name == "CPU":
                            cpu = event.data.get('cpu_percent')
                            ram = event.data.get('ram_percent')
                            print(f"💻 {name}: CPU {cpu}% | RAM {ram}%")
                        elif name == "Network":
                            sent = event.data.get('upload_rate_bytes', 0) / 1024
                            recv = event.data.get('download_rate_bytes', 0) / 1024
                            print(f"🌐 {name}: ↑{sent:.1f}KB/s ↓{recv:.1f}KB/s")
                        elif name == "Battery":
                            plugged = "🔌" if event.data.get('power_plugged') else "🔋"
                            print(f"{plugged} {name}: {event.data.get('percent')}%")
                        elif name == "Mic":
                            if event.data.get('threshold_exceeded'):
                                print(f"🎤 {name}: PEAK LEVEL {event.data.get('peak_level')}")
                except Exception as e:
                    # Ignore poll errors
                    pass
            
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        pass
        
    print("\n\n✅ Ultimate Test Complete.")

if __name__ == "__main__":
    try:
        asyncio.run(test_all_sources_interactive())
    except Exception as e:
        print(f"Error: {e}")

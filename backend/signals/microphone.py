"""
SignalDock Microphone Signal Source
"""
from typing import Optional
import asyncio
import threading
import queue

from .base import SignalSource, SignalEvent, EventType
from config import get_config


class MicrophoneSignalSource(SignalSource):
    """Microphone peak level monitoring"""
    
    display_name = "Microphone"
    description = "Monitors microphone audio levels (requires permission)"
    requires_permission = True
    
    def __init__(self, 
                 name: str = "microphone_monitor",
                 threshold: float = 0.5,
                 chunk_size: int = 1024,
                 sample_rate: int = 44100):
        super().__init__(name)
        
        self.threshold = threshold
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate
        
        self._audio_stream = None
        self._audio_thread: Optional[threading.Thread] = None
        self._peak_queue: queue.Queue = queue.Queue()
        self._audio_available = False
        
        # Check if pyaudio is available
        try:
            import pyaudio
            self._audio_available = True
        except ImportError:
            self.logger.warning("pyaudio not available - microphone monitoring disabled")
    
    def get_poll_interval(self) -> float:
        return 0.1  # Fast polling for audio events
    
    def _calculate_rms(self, data: bytes) -> float:
        """Calculate RMS (root mean square) of audio data"""
        import struct
        
        count = len(data) // 2
        format_str = f"{count}h"
        shorts = struct.unpack(format_str, data)
        
        sum_squares = sum(s * s for s in shorts)
        rms = (sum_squares / count) ** 0.5
        
        # Normalize to 0-1 range (assuming 16-bit audio)
        return rms / 32768
    
    def _audio_capture_loop(self):
        """Audio capture loop running in separate thread"""
        try:
            import pyaudio
            
            p = pyaudio.PyAudio()
            
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            self._audio_stream = stream
            
            while self._running:
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    rms = self._calculate_rms(data)
                    
                    # Queue peak levels
                    try:
                        self._peak_queue.put_nowait(rms)
                    except queue.Full:
                        pass
                        
                except Exception as e:
                    self.logger.error(f"Error reading audio: {e}")
                    break
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            self.logger.error(f"Error in audio capture: {e}")
    
    async def _poll(self) -> Optional[SignalEvent]:
        """Poll for audio peak events"""
        config = get_config()
        if not config.permissions.microphone_enabled:
            return None
        
        if not self._audio_available:
            return None
        
        try:
            # Get latest peak from queue
            peak = None
            while not self._peak_queue.empty():
                try:
                    peak = self._peak_queue.get_nowait()
                except queue.Empty:
                    break
            
            if peak is not None:
                self._last_value = {
                    "peak_level": round(peak, 3),
                    "threshold_exceeded": peak >= self.threshold
                }
                
                # Only emit event if threshold exceeded
                if peak >= self.threshold:
                    return SignalEvent(
                        event_type=EventType.THRESHOLD_CROSSED,
                        data={
                            "peak_level": round(peak, 3),
                            "threshold": self.threshold
                        },
                        metadata={
                            "sample_rate": self.sample_rate,
                            "chunk_size": self.chunk_size
                        }
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error polling microphone: {e}")
            return None
    
    async def start(self) -> None:
        """Start microphone monitoring"""
        if not self._audio_available:
            self.logger.error("pyaudio not available")
            return
        
        if self._running:
            return
        
        self._running = True
        
        # Start audio capture thread
        self._audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
        self._audio_thread.start()
        
        # Start polling task
        self._task = asyncio.create_task(self._run_loop())
    
    async def stop(self) -> None:
        """Stop microphone monitoring"""
        self._running = False
        
        if self._audio_thread:
            self._audio_thread.join(timeout=2)
            self._audio_thread = None
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
    
    def get_config_schema(self) -> dict:
        return {
            "threshold": {
                "type": "number",
                "description": "Peak level threshold (0-1) to trigger events",
                "default": 0.5,
                "min": 0.01,
                "max": 1.0
            },
            "sample_rate": {
                "type": "integer",
                "description": "Audio sample rate in Hz",
                "default": 44100
            },
            "enabled": {
                "type": "boolean",
                "description": "Enable microphone monitoring (privacy-sensitive)",
                "default": False
            }
        }

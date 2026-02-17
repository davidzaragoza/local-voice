"""Audio recorder module using SoundDevice for high-quality audio capture."""

import threading
import queue
import time
from typing import Callable, Optional
from dataclasses import dataclass
from enum import Enum, auto

import numpy as np
import sounddevice as sd


class RecorderState(Enum):
    IDLE = auto()
    RECORDING = auto()
    STOPPING = auto()


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1
    dtype: str = "float32"
    block_size: int = 1024
    silence_threshold: float = 0.01
    silence_duration: float = 1.5


class AudioRecorder:
    def __init__(self, config: Optional[AudioConfig] = None):
        self.config = config or AudioConfig()
        self._state = RecorderState.IDLE
        self._audio_buffer: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: Optional[sd.InputStream] = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._silence_start: Optional[float] = None
        self._voice_detected = False
        self._on_vad_callback: Optional[Callable[[bool], None]] = None
        self._on_audio_callback: Optional[Callable[[np.ndarray], None]] = None
        
    @property
    def state(self) -> RecorderState:
        return self._state
    
    @property
    def is_recording(self) -> bool:
        return self._state == RecorderState.RECORDING
    
    def set_vad_callback(self, callback: Callable[[bool], None]):
        self._on_vad_callback = callback
    
    def set_audio_callback(self, callback: Callable[[np.ndarray], None]):
        self._on_audio_callback = callback
    
    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            print(f"Audio callback status: {status}")
        
        if self._state != RecorderState.RECORDING:
            return
        
        audio_chunk = indata.copy()
        
        with self._lock:
            self._audio_buffer.append(audio_chunk)
        
        if self._on_audio_callback:
            self._on_audio_callback(audio_chunk)
        
        self._detect_voice_activity(audio_chunk)
    
    def _detect_voice_activity(self, audio_chunk: np.ndarray):
        rms = np.sqrt(np.mean(audio_chunk ** 2))
        is_voice = rms > self.config.silence_threshold
        
        if is_voice:
            self._voice_detected = True
            self._silence_start = None
            if self._on_vad_callback:
                self._on_vad_callback(True)
        else:
            if self._on_vad_callback and self._voice_detected:
                self._on_vad_callback(False)
    
    def get_audio_data(self) -> Optional[np.ndarray]:
        with self._lock:
            if not self._audio_buffer:
                return None
            audio_data = np.concatenate(self._audio_buffer, axis=0)
            return audio_data
    
    def get_audio_bytes(self) -> Optional[bytes]:
        audio_data = self.get_audio_data()
        if audio_data is None:
            return None
        return (audio_data * 32767).astype(np.int16).tobytes()
    
    def clear_buffer(self):
        with self._lock:
            self._audio_buffer.clear()
            self._voice_detected = False
            self._silence_start = None
    
    def start_recording(self) -> bool:
        if self._state == RecorderState.RECORDING:
            return True
        
        try:
            self.clear_buffer()
            self._state = RecorderState.RECORDING
            
            self._stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=self.config.dtype,
                blocksize=self.config.block_size,
                callback=self._audio_callback
            )
            self._stream.start()
            return True
        except Exception as e:
            print(f"Failed to start recording: {e}")
            self._state = RecorderState.IDLE
            return False
    
    def stop_recording(self) -> Optional[np.ndarray]:
        if self._state != RecorderState.RECORDING:
            return None
        
        self._state = RecorderState.STOPPING
        
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        
        audio_data = self.get_audio_data()
        self._state = RecorderState.IDLE
        
        return audio_data
    
    def get_input_devices(self) -> list[dict]:
        devices = []
        for i, device in enumerate(sd.query_devices()):
            if device['max_input_channels'] > 0:
                devices.append({
                    'id': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                    'default_samplerate': device['default_samplerate']
                })
        return devices
    
    def set_input_device(self, device_id: int):
        sd.default.device[0] = device_id
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_recording()
        return False

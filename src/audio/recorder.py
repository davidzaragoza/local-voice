"""Audio recorder module using SoundDevice for high-quality audio capture."""

import threading
import logging
from typing import Callable, Optional
from dataclasses import dataclass
from enum import Enum, auto

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


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
        self._silence_start: Optional[float] = None
        self._voice_detected = False
        self._on_vad_callback: Optional[Callable[[bool], None]] = None
        self._on_audio_callback: Optional[Callable[[np.ndarray], None]] = None
        self._max_abs_level: float = 0.0
        self._active_sample_rate: int = self.config.sample_rate
        self._input_device_id: Optional[int] = None
        
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
            logger.warning(f"Audio callback status: {status}")
        
        if self._state != RecorderState.RECORDING:
            return
        
        audio_chunk = indata.copy()
        chunk_max_abs = float(np.max(np.abs(audio_chunk))) if audio_chunk.size else 0.0
        if chunk_max_abs > self._max_abs_level:
            self._max_abs_level = chunk_max_abs
        
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
            self._max_abs_level = 0.0
    
    def start_recording(self) -> bool:
        if self._state == RecorderState.RECORDING:
            return True
        
        try:
            self.clear_buffer()
            self._state = RecorderState.RECORDING
            input_device_id = None
            try:
                input_device_id = sd.default.device[0]
            except Exception:
                pass
            self._input_device_id = input_device_id

            selected_sample_rate = self.config.sample_rate
            device_default_rate = None
            if input_device_id is not None:
                try:
                    device_info = sd.query_devices(input_device_id)
                    device_default_rate = int(float(device_info.get("default_samplerate", self.config.sample_rate)))
                    logger.info(
                        "Using input device id=%s name='%s' default_samplerate=%s",
                        input_device_id,
                        device_info.get("name"),
                        device_info.get("default_samplerate"),
                    )
                except Exception as e:
                    logger.warning("Could not query selected input device (%s): %s", input_device_id, e)
            else:
                logger.info("Using default input device (system-selected)")

            # Probe for a stable/valid stream configuration; some macOS devices crash with unsupported rates.
            candidate_rates = [self.config.sample_rate]
            if device_default_rate and device_default_rate not in candidate_rates:
                candidate_rates.append(device_default_rate)
            for rate in candidate_rates:
                try:
                    sd.check_input_settings(
                        device=input_device_id,
                        channels=self.config.channels,
                        dtype=self.config.dtype,
                        samplerate=rate,
                    )
                    selected_sample_rate = rate
                    break
                except Exception as e:
                    logger.warning("Input settings rejected for samplerate=%s: %s", rate, e)

            self._active_sample_rate = selected_sample_rate
            logger.info("Opening input stream at samplerate=%s", self._active_sample_rate)
            
            self._stream = sd.InputStream(
                device=input_device_id,
                samplerate=self._active_sample_rate,
                channels=self.config.channels,
                dtype=self.config.dtype,
                blocksize=self.config.block_size,
                callback=self._audio_callback
            )
            self._stream.start()
            return True
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
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
        
        if audio_data is not None and audio_data.size > 0:
            rms = float(np.sqrt(np.mean(audio_data ** 2)))
            peak = float(np.max(np.abs(audio_data)))
            logger.info(
                "Captured audio stats: samples=%s rms=%.6f peak=%.6f chunk_peak=%.6f",
                audio_data.shape[0],
                rms,
                peak,
                self._max_abs_level,
            )
            if peak < 0.001:
                logger.warning(
                    "Audio signal is near-silent. Check microphone permission for LocalVoice and selected input device."
                )

        if (
            audio_data is not None
            and audio_data.size > 0
            and self._active_sample_rate != self.config.sample_rate
        ):
            source_rate = int(self._active_sample_rate)
            target_rate = int(self.config.sample_rate)
            logger.info("Resampling audio from %s Hz to %s Hz", source_rate, target_rate)
            audio_data = self._resample_audio(audio_data, source_rate, target_rate)
        
        return audio_data

    def _resample_audio(self, audio_data: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
        if source_rate == target_rate:
            return audio_data

        if audio_data.ndim == 1:
            audio_data = audio_data.reshape(-1, 1)

        in_samples = audio_data.shape[0]
        if in_samples < 2:
            return audio_data

        out_samples = max(1, int(round(in_samples * (target_rate / float(source_rate)))))
        x_old = np.linspace(0, in_samples - 1, num=in_samples, dtype=np.float64)
        x_new = np.linspace(0, in_samples - 1, num=out_samples, dtype=np.float64)

        channels = audio_data.shape[1]
        resampled = np.empty((out_samples, channels), dtype=np.float32)
        for ch in range(channels):
            resampled[:, ch] = np.interp(x_new, x_old, audio_data[:, ch]).astype(np.float32)
        return resampled
    
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

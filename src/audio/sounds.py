"""Audio feedback sounds module for LocalVoice."""

import threading
from pathlib import Path
from typing import Optional

import sounddevice as sd
import soundfile as sf


class SoundManager:
    _instance: Optional['SoundManager'] = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._enabled = False
                    instance._sound_file = Path(__file__).parent.parent.parent / "assets" / "bip.wav"
                    instance._sound_data: Optional[tuple] = None
                    instance._load_sound()
                    cls._instance = instance
        return cls._instance
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
    
    def _load_sound(self):
        if self._sound_file.exists():
            try:
                data, sample_rate = sf.read(self._sound_file, dtype='float32')
                if data.ndim > 1:
                    data = data[:, 0]
                self._sound_data = (data, sample_rate)
            except Exception:
                self._sound_data = None
    
    def _play_sound(self):
        if self._sound_data is None:
            return
        try:
            data, sample_rate = self._sound_data
            # sd.play is already non-blocking; no extra thread needed.
            sd.play(data, sample_rate)
        except Exception:
            pass

    def play_start_sound(self):
        if not self._enabled:
            return
        self._play_sound()

    def play_stop_sound(self):
        if not self._enabled:
            return
        self._play_sound()


def get_sound_manager() -> SoundManager:
    return SoundManager()

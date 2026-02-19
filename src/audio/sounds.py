"""Audio feedback sounds module for LocalVoice."""

import threading
from pathlib import Path
from typing import Optional

import sounddevice as sd
import soundfile as sf


class SoundManager:
    _instance: Optional['SoundManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._enabled = False
            cls._instance._sound_file = Path(__file__).parent.parent.parent / "assets" / "bip.wav"
            cls._instance._sound_data: Optional[tuple] = None
            cls._instance._load_sound()
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
            sd.play(data, sample_rate)
        except Exception:
            pass
    
    def play_start_sound(self):
        if not self._enabled:
            return
        thread = threading.Thread(target=self._play_sound, daemon=True)
        thread.start()
    
    def play_stop_sound(self):
        if not self._enabled:
            return
        thread = threading.Thread(target=self._play_sound, daemon=True)
        thread.start()


def get_sound_manager() -> SoundManager:
    return SoundManager()

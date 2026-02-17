"""Transcription engine using faster-whisper for offline STT."""

import os
import threading
from pathlib import Path
from typing import Optional, Callable, Generator
from dataclasses import dataclass
from enum import Enum

import numpy as np
from faster_whisper import WhisperModel


class ModelSize(Enum):
    TINY = "tiny"
    TINY_EN = "tiny.en"
    BASE = "base"
    BASE_EN = "base.en"
    SMALL = "small"
    SMALL_EN = "small.en"
    MEDIUM = "medium"
    MEDIUM_EN = "medium.en"
    LARGE = "large"
    LARGE_V2 = "large-v2"
    LARGE_V3 = "large-v3"


@dataclass
class TranscriptionResult:
    text: str
    language: str
    language_probability: float
    segments: list[dict]
    duration: float


@dataclass
class TranscriptionConfig:
    model_size: ModelSize = ModelSize.BASE
    language: Optional[str] = None
    device: str = "auto"
    compute_type: str = "default"
    beam_size: int = 5
    best_of: int = 5
    temperature: float = 0.0
    vad_filter: bool = True
    model_dir: Optional[str] = None


class TranscriptionEngine:
    _instance: Optional['TranscriptionEngine'] = None
    _model: Optional[WhisperModel] = None
    _model_lock = threading.Lock()
    _current_config: Optional[TranscriptionConfig] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._current_config is None:
            self._current_config = TranscriptionConfig()
    
    @property
    def model_dir(self) -> Path:
        if self._current_config and self._current_config.model_dir:
            return Path(self._current_config.model_dir)
        home = Path.home()
        model_dir = home / ".localvoice" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        return model_dir
    
    @property
    def is_model_loaded(self) -> bool:
        return self._model is not None
    
    def get_model_path(self, model_size: ModelSize) -> Path:
        return self.model_dir / model_size.value
    
    def is_model_downloaded(self, model_size: ModelSize) -> bool:
        model_path = self.get_model_path(model_size)
        return model_path.exists() and any(model_path.iterdir())
    
    def load_model(
        self, 
        config: Optional[TranscriptionConfig] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> bool:
        config = config or TranscriptionConfig()
        
        with self._model_lock:
            if self._model is not None and self._current_config == config:
                return True
            
            try:
                if progress_callback:
                    progress_callback(0.1)
                
                device = config.device
                if device == "auto":
                    try:
                        import torch
                        device = "cuda" if torch.cuda.is_available() else "cpu"
                        if device == "cuda":
                            compute_type = "float16"
                        else:
                            compute_type = "int8"
                    except ImportError:
                        device = "cpu"
                        compute_type = "int8"
                else:
                    compute_type = config.compute_type
                
                if progress_callback:
                    progress_callback(0.3)
                
                model_path = str(self.get_model_path(config.model_size))
                
                self._model = WhisperModel(
                    config.model_size.value,
                    device=device,
                    compute_type=compute_type,
                    download_root=str(self.model_dir)
                )
                
                self._current_config = config
                
                if progress_callback:
                    progress_callback(1.0)
                
                return True
                
            except Exception as e:
                print(f"Failed to load model: {e}")
                self._model = None
                return False
    
    def unload_model(self):
        with self._model_lock:
            if self._model is not None:
                del self._model
                self._model = None
    
    def transcribe(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
        callback: Optional[Callable[[str], None]] = None
    ) -> Optional[TranscriptionResult]:
        if self._model is None:
            if not self.load_model():
                return None
        
        if audio.dtype == np.float32:
            audio_float = audio.flatten()
        else:
            audio_float = audio.astype(np.float32).flatten()
        
        try:
            segments_generator, info = self._model.transcribe(
                audio_float,
                language=language or self._current_config.language,
                beam_size=self._current_config.beam_size,
                best_of=self._current_config.best_of,
                temperature=self._current_config.temperature,
                vad_filter=self._current_config.vad_filter
            )
            
            segments = []
            full_text = []
            
            for segment in segments_generator:
                segment_dict = {
                    'start': segment.start,
                    'end': segment.end,
                    'text': segment.text,
                    'avg_logprob': segment.avg_logprob,
                    'no_speech_prob': segment.no_speech_prob
                }
                segments.append(segment_dict)
                full_text.append(segment.text.strip())
                
                if callback:
                    callback(segment.text)
            
            text = ' '.join(full_text)
            
            return TranscriptionResult(
                text=text,
                language=info.language,
                language_probability=info.language_probability,
                segments=segments,
                duration=info.duration
            )
            
        except Exception as e:
            print(f"Transcription failed: {e}")
            return None
    
    def transcribe_realtime(
        self,
        audio: np.ndarray,
        language: Optional[str] = None
    ) -> Generator[str, None, None]:
        if self._model is None:
            if not self.load_model():
                return
        
        if audio.dtype == np.float32:
            audio_float = audio.flatten()
        else:
            audio_float = audio.astype(np.float32).flatten()
        
        try:
            segments_generator, _ = self._model.transcribe(
                audio_float,
                language=language or self._current_config.language,
                beam_size=self._current_config.beam_size,
                vad_filter=self._current_config.vad_filter
            )
            
            for segment in segments_generator:
                yield segment.text
                
        except Exception as e:
            print(f"Realtime transcription failed: {e}")
    
    @classmethod
    def get_available_models(cls) -> list[dict]:
        return [
            {'size': ModelSize.TINY.value, 'name': 'Tiny', 'params': '39M', 'speed': 'fastest'},
            {'size': ModelSize.TINY_EN.value, 'name': 'Tiny (English)', 'params': '39M', 'speed': 'fastest'},
            {'size': ModelSize.BASE.value, 'name': 'Base', 'params': '74M', 'speed': 'fast'},
            {'size': ModelSize.BASE_EN.value, 'name': 'Base (English)', 'params': '74M', 'speed': 'fast'},
            {'size': ModelSize.SMALL.value, 'name': 'Small', 'params': '244M', 'speed': 'medium'},
            {'size': ModelSize.SMALL_EN.value, 'name': 'Small (English)', 'params': '244M', 'speed': 'medium'},
            {'size': ModelSize.MEDIUM.value, 'name': 'Medium', 'params': '769M', 'speed': 'slow'},
            {'size': ModelSize.LARGE_V3.value, 'name': 'Large v3', 'params': '1550M', 'speed': 'slowest'},
        ]
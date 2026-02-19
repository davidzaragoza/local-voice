"""Transcription engine using faster-whisper for offline STT."""

import shutil
import ssl
import urllib.error
import urllib.request
import logging
import threading
from pathlib import Path
from typing import Optional, Callable, Generator, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

import numpy as np
from faster_whisper import WhisperModel

if TYPE_CHECKING:
    from ..vocabulary.manager import VocabularyManager

logger = logging.getLogger(__name__)

VAD_MODEL_URL = "https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/faster_whisper/assets/silero_vad_v6.onnx"
VAD_MODEL_FILENAME = "silero_vad_v6.onnx"


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
    _vad_downloaded = False
    _vocabulary_manager: Optional['VocabularyManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._current_config is None:
            self._current_config = TranscriptionConfig()
        self._ensure_vad_model()
    
    def set_vocabulary_manager(self, manager: 'VocabularyManager'):
        self._vocabulary_manager = manager
    
    def _ensure_vad_model(self):
        """Ensure VAD model is available, download if needed."""
        if self._vad_downloaded:
            return
        
        try:
            import faster_whisper
            assets_dir = Path(faster_whisper.__file__).parent / "assets"
            vad_path = assets_dir / VAD_MODEL_FILENAME
            
            if vad_path.exists():
                logger.info(f"VAD model found at {vad_path}")
                self._vad_downloaded = True
                return
            
            assets_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Downloading VAD model to {vad_path}...")
            self._download_vad_model(vad_path)
            logger.info("VAD model downloaded successfully")
            self._vad_downloaded = True
            
        except Exception as e:
            logger.warning(f"Could not download VAD model: {e}")
            self._vad_downloaded = True

    def _download_vad_model(self, vad_path: Path):
        """Download VAD model with a certifi-backed SSL fallback for packaged apps."""
        try:
            urllib.request.urlretrieve(VAD_MODEL_URL, vad_path)
            return
        except urllib.error.URLError as e:
            reason = str(getattr(e, "reason", e))
            if "CERTIFICATE_VERIFY_FAILED" not in reason:
                raise
            logger.warning("Default SSL certificates failed, retrying VAD download with certifi bundle")

        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(VAD_MODEL_URL, context=context) as response:
            with open(vad_path, "wb") as output:
                shutil.copyfileobj(response, output)
    
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
                logger.exception(f"Failed to load model: {e}")
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
        task: str = "transcribe",
        callback: Optional[Callable[[str], None]] = None
    ) -> Optional[TranscriptionResult]:
        if self._model is None:
            if not self.load_model():
                return None
        
        if audio.dtype == np.float32:
            audio_float = audio.flatten()
        else:
            audio_float = audio.astype(np.float32).flatten()
        
        initial_prompt = None
        if self._vocabulary_manager:
            initial_prompt = self._vocabulary_manager.get_initial_prompt()
        
        try:
            transcribe_kwargs = {
                'language': language or self._current_config.language,
                'task': task,
                'beam_size': self._current_config.beam_size,
                'best_of': self._current_config.best_of,
                'temperature': self._current_config.temperature,
                'vad_filter': self._current_config.vad_filter
            }
            
            if initial_prompt:
                transcribe_kwargs['initial_prompt'] = initial_prompt
            
            segments_generator, info = self._model.transcribe(audio_float, **transcribe_kwargs)
            
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
            
            if self._vocabulary_manager:
                text = self._vocabulary_manager.apply_substitutions(text)
            
            return TranscriptionResult(
                text=text,
                language=info.language,
                language_probability=info.language_probability,
                segments=segments,
                duration=info.duration
            )
            
        except Exception as e:
            logger.exception(f"Transcription failed: {e}")
            return None
    
    def transcribe_realtime(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> Generator[str, None, None]:
        if self._model is None:
            if not self.load_model():
                return
        
        if audio.dtype == np.float32:
            audio_float = audio.flatten()
        else:
            audio_float = audio.astype(np.float32).flatten()
        
        initial_prompt = None
        if self._vocabulary_manager:
            initial_prompt = self._vocabulary_manager.get_initial_prompt()
        
        try:
            transcribe_kwargs = {
                'language': language or self._current_config.language,
                'task': task,
                'beam_size': self._current_config.beam_size,
                'vad_filter': self._current_config.vad_filter
            }
            
            if initial_prompt:
                transcribe_kwargs['initial_prompt'] = initial_prompt
            
            segments_generator, _ = self._model.transcribe(audio_float, **transcribe_kwargs)
            
            for segment in segments_generator:
                text = segment.text
                if self._vocabulary_manager:
                    text = self._vocabulary_manager.apply_substitutions(text)
                yield text
                
        except Exception as e:
            logger.exception(f"Realtime transcription failed: {e}")
    
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

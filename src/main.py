"""Main entry point for LocalVoice application."""

import sys
import json
import threading
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QSettings

from .gui.main_window import FloatingWindow, AppState
from .gui.tray_icon import TrayIcon
from .gui.settings_dialog import SettingsDialog
from .audio.recorder import AudioRecorder, AudioConfig
from .transcription.engine import TranscriptionEngine, TranscriptionConfig, ModelSize
from .injection.text_injector import TextInjector, InjectionConfig, InjectionMethod
from .hotkey.manager import HotkeyManager, HotkeyConfig


class TranscriptionWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, engine: TranscriptionEngine, audio_data, language: Optional[str] = None):
        super().__init__()
        self._engine = engine
        self._audio_data = audio_data
        self._language = language
    
    def run(self):
        try:
            result = self._engine.transcribe(self._audio_data, self._language)
            if result and result.text.strip():
                self.finished.emit(result.text)
            else:
                self.finished.emit("")
        except Exception as e:
            self.error.emit(str(e))


class SettingsManager:
    def __init__(self):
        self._settings_file = Path(__file__).parent.parent / "config" / "settings.json"
        self._settings = self._get_default_settings()
        self._load_from_file()
    
    def _get_default_settings(self) -> Dict[str, Any]:
        return {
            'model_size': 'base',
            'language': 'auto',
            'hotkey': 'caps_lock',
            'hotkey_mode': 'hold',
            'injection_method': 'clipboard',
            'start_minimized': False,
            'window_opacity': 95,
            'device': 'auto',
            'typing_delay': 10,
            'add_trailing_space': True,
            'preserve_clipboard': True,
        }
    
    def _load_from_file(self):
        if self._settings_file.exists():
            try:
                with open(self._settings_file, 'r') as f:
                    loaded = json.load(f)
                    for key, value in loaded.items():
                        if key in self._settings:
                            self._settings[key] = value
            except Exception as e:
                print(f"Failed to load settings: {e}")
    
    def save_settings(self, settings: Dict[str, Any]):
        self._settings.update(settings)
        self._settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._settings_file, 'w') as f:
            json.dump(self._settings, f, indent=4)
    
    def get_settings(self) -> Dict[str, Any]:
        return self._settings.copy()
    
    def get(self, key: str, default=None):
        return self._settings.get(key, default)


class LocalVoiceApp(QObject):
    injection_complete = pyqtSignal()
    start_recording_requested = pyqtSignal()
    stop_recording_requested = pyqtSignal()
    toggle_recording_requested = pyqtSignal()
    
    def __init__(self, app: QApplication):
        super().__init__()
        self._app = app
        self._settings_manager = SettingsManager()
        
        self._recorder = AudioRecorder()
        self._engine = TranscriptionEngine()
        self._injector = TextInjector()
        self._hotkey_manager = HotkeyManager()
        
        self._main_window: Optional[FloatingWindow] = None
        self._tray_icon: Optional[TrayIcon] = None
        self._transcription_worker: Optional[TranscriptionWorker] = None
        
        self._is_recording = False
        self._is_processing = False
        
        self._init_components()
        self._connect_signals()
        self._load_settings()
    
    def _init_components(self):
        self._main_window = FloatingWindow()
        self._tray_icon = TrayIcon()
        self._tray_icon.show()
        
        settings = self._settings_manager.get_settings()
        if not settings.get('start_minimized', False):
            self._main_window.show()
    
    def _connect_signals(self):
        self._main_window.recording_toggled.connect(self._on_recording_toggled)
        self._main_window.settings_requested.connect(self._show_settings)
        self._main_window.quit_requested.connect(self._quit)
        
        self._tray_icon.recording_toggled.connect(self._on_tray_recording_toggled)
        self._tray_icon.show_window_requested.connect(self._main_window.show)
        self._tray_icon.hide_window_requested.connect(self._main_window.hide)
        self._tray_icon.settings_requested.connect(self._show_settings)
        self._tray_icon.quit_requested.connect(self._quit)
        
        self._hotkey_manager.set_on_start(self._emit_start_recording)
        self._hotkey_manager.set_on_stop(self._emit_stop_recording)
        self._hotkey_manager.set_on_toggle(self._emit_toggle_recording)
        
        self.start_recording_requested.connect(self._start_recording)
        self.stop_recording_requested.connect(self._stop_recording)
        self.toggle_recording_requested.connect(self._toggle_recording)
        
        self._injector.set_on_complete_callback(self._emit_injection_complete)
        self.injection_complete.connect(self._on_injection_complete)
    
    def _emit_start_recording(self):
        self.start_recording_requested.emit()
    
    def _emit_stop_recording(self):
        self.stop_recording_requested.emit()
    
    def _emit_toggle_recording(self):
        self.toggle_recording_requested.emit()
    
    def _load_settings(self):
        settings = self._settings_manager.get_settings()
        
        self._main_window.set_opacity(settings.get('window_opacity', 95) / 100.0)
        
        hotkey = settings.get('hotkey', 'caps_lock')
        hotkey_mode = settings.get('hotkey_mode', 'hold')
        hotkey_config = HotkeyConfig.parse(hotkey, hotkey_mode)
        
        if not self._hotkey_manager._running:
            self._hotkey_manager.update_config(hotkey_config)
            self._hotkey_manager.start()
        else:
            self._hotkey_manager.update_config(hotkey_config)
        
        injection_config = InjectionConfig(
            method=InjectionMethod(settings.get('injection_method', 'clipboard')),
            typing_delay=settings.get('typing_delay', 10) / 1000.0,
            add_trailing_space=settings.get('add_trailing_space', True),
            preserve_clipboard=settings.get('preserve_clipboard', True)
        )
        self._injector.config = injection_config
    
    def _on_recording_toggled(self, start: bool):
        if start:
            self._start_recording()
        else:
            self._stop_recording()
    
    def _on_tray_recording_toggled(self, start: bool):
        if start:
            self._start_recording()
        else:
            self._stop_recording()
    
    def _start_recording(self):
        if self._is_recording or self._is_processing:
            return
        
        self._injector.capture_last_active_window()
        
        if self._recorder.start_recording():
            self._is_recording = True
            self._main_window.set_state(AppState.RECORDING)
            self._tray_icon.set_state("recording")
    
    def _stop_recording(self):
        if not self._is_recording:
            return
        
        audio_data = self._recorder.stop_recording()
        self._is_recording = False
        
        if audio_data is not None and len(audio_data) > 0:
            self._start_transcription(audio_data)
        else:
            self._main_window.set_state(AppState.IDLE)
            self._tray_icon.set_state("idle")
    
    def _toggle_recording(self):
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()
    
    def _start_transcription(self, audio_data):
        self._is_processing = True
        self._main_window.set_state(AppState.PROCESSING)
        self._tray_icon.set_state("processing")
        
        settings = self._settings_manager.get_settings()
        language = settings.get('language', 'auto')
        if language == 'auto':
            language = None
        
        model_size = settings.get('model_size', 'base')
        device = settings.get('device', 'auto')
        
        transcription_config = TranscriptionConfig(
            model_size=ModelSize(model_size),
            device=device
        )
        
        if not self._engine.is_model_loaded:
            if not self._engine.load_model(transcription_config):
                self._on_transcription_error("Failed to load model")
                return
        
        if self._transcription_worker and self._transcription_worker.isRunning():
            self._transcription_worker.terminate()
            self._transcription_worker.wait()
        
        self._transcription_worker = TranscriptionWorker(
            self._engine, audio_data, language
        )
        self._transcription_worker.finished.connect(self._on_transcription_finished)
        self._transcription_worker.error.connect(self._on_transcription_error)
        self._transcription_worker.start()
    
    def _on_transcription_finished(self, text: str):
        self._is_processing = False
        if self._transcription_worker:
            self._transcription_worker.deleteLater()
            self._transcription_worker = None
        
        if text.strip():
            self._injector.inject_async(text)
        else:
            self._main_window.set_state(AppState.IDLE)
            self._tray_icon.set_state("idle")
    
    def _on_transcription_error(self, error: str):
        self._is_processing = False
        if self._transcription_worker:
            self._transcription_worker.deleteLater()
            self._transcription_worker = None
        self._main_window.set_state(AppState.ERROR)
        self._tray_icon.set_state("error")
        
        QMessageBox.warning(
            self._main_window,
            "Transcription Error",
            f"Failed to transcribe audio: {error}"
        )
    
    def _emit_injection_complete(self):
        self.injection_complete.emit()
    
    def _on_injection_complete(self):
        self._main_window.set_state(AppState.IDLE)
        self._tray_icon.set_state("idle")
    
    def _show_settings(self):
        current_settings = self._settings_manager.get_settings()
        dialog = SettingsDialog(current_settings, self._main_window)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()
    
    def _on_settings_changed(self, settings: Dict[str, Any]):
        self._settings_manager.save_settings(settings)
        self._load_settings()
    
    def _quit(self):
        self._hotkey_manager.stop()
        self._recorder.stop_recording()
        
        if self._transcription_worker and self._transcription_worker.isRunning():
            self._transcription_worker.terminate()
            self._transcription_worker.wait()
        
        self._tray_icon.hide()
        self._main_window.close()
        self._app.quit()


def main():
    if sys.platform == 'darwin':
        sys.argv.extend(['-platform', 'cocoa'])
    
    app = QApplication(sys.argv)
    app.setApplicationName("LocalVoice")
    app.setApplicationDisplayName("LocalVoice")
    app.setQuitOnLastWindowClosed(False)
    
    app.setStyle('Fusion')
    
    from PyQt6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(80, 130, 200))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    
    main_app = LocalVoiceApp(app)
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
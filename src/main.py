"""Main entry point for LocalVoice application."""

import sys
import json
import threading
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QSettings, QTimer

from .gui.main_window import FloatingWindow, AppState
from .gui.tray_icon import TrayIcon
from .gui.settings_dialog import SettingsDialog
from .audio.recorder import AudioRecorder, AudioConfig
from .transcription.engine import TranscriptionEngine, TranscriptionConfig, ModelSize
from .injection.text_injector import TextInjector, InjectionConfig, InjectionMethod
from .hotkey.manager import HotkeyManager, HotkeyConfig


class TranscriptionWorker(QObject):
    finished = pyqtSignal()
    
    def __init__(self, engine: TranscriptionEngine, audio_data, language: Optional[str] = None, task: str = "transcribe", parent=None):
        super().__init__(parent)
        self._engine = engine
        self._audio_data = audio_data
        self._language = language
        self._task = task
        self._cancelled = False
        self._result_text = ""
        self._error_msg = ""
    
    def run(self):
        try:
            if self._cancelled:
                return
            result = self._engine.transcribe(self._audio_data, self._language, self._task)
            if self._cancelled:
                return
            if result and result.text.strip():
                self._result_text = result.text
            else:
                self._result_text = ""
        except Exception as e:
            if not self._cancelled:
                self._error_msg = str(e)
        finally:
            self.finished.emit()
    
    def get_result(self) -> str:
        return self._result_text
    
    def get_error(self) -> str:
        return self._error_msg
    
    def cancel(self):
        self._cancelled = True


class SettingsManager:
    def __init__(self):
        self._settings_file = Path(__file__).parent.parent / "config" / "settings.json"
        self._settings = self._get_default_settings()
        self._load_from_file()
    
    def _get_default_settings(self) -> Dict[str, Any]:
        return {
            'model_size': 'base',
            'language': 'auto',
            'translate_to_english': False,
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
        self._transcription_thread: Optional[QThread] = None
        
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
        
        if self._transcription_thread:
            old_thread = self._transcription_thread
            self._transcription_thread = None
            if old_thread.isRunning():
                old_thread.quit()
                if not old_thread.wait(2000):
                    old_thread.terminate()
                    old_thread.wait()
            old_thread.deleteLater()
        
        settings = self._settings_manager.get_settings()
        language = settings.get('language', 'auto')
        if language == 'auto':
            language = None
        
        translate_to_english = settings.get('translate_to_english', False)
        task = "translate" if translate_to_english else "transcribe"
        
        model_size = settings.get('model_size', 'base')
        device = settings.get('device', 'auto')
        
        transcription_config = TranscriptionConfig(
            model_size=ModelSize(model_size),
            device=device
        )
        
        if not self._engine.is_model_loaded:
            if not self._engine.load_model(transcription_config):
                self._is_processing = False
                self._main_window.set_state(AppState.ERROR)
                self._tray_icon.set_state("error")
                QMessageBox.warning(
                    self._main_window,
                    "Transcription Error",
                    "Failed to load model"
                )
                return
        
        self._transcription_thread = QThread()
        self._transcription_worker = TranscriptionWorker(
            self._engine, audio_data, language, task
        )
        self._transcription_worker.moveToThread(self._transcription_thread)
        
        self._transcription_thread.started.connect(self._transcription_worker.run)
        self._transcription_worker.finished.connect(self._on_worker_finished)
        self._transcription_worker.finished.connect(self._transcription_thread.quit)
        
        self._transcription_thread.start()
    
    def _on_worker_finished(self):
        worker = self._transcription_worker
        thread = self._transcription_thread
        self._transcription_worker = None
        self._transcription_thread = None
        self._is_processing = False
        
        if not worker:
            return
        
        error = worker.get_error()
        if error:
            self._main_window.set_state(AppState.ERROR)
            self._tray_icon.set_state("error")
            QMessageBox.warning(
                self._main_window,
                "Transcription Error",
                f"Failed to transcribe audio: {error}"
            )
        else:
            text = worker.get_result()
            if text.strip():
                self._injector.inject_async(text)
            else:
                self._main_window.set_state(AppState.IDLE)
                self._tray_icon.set_state("idle")
        
        if thread:
            thread.quit()
            if not thread.wait(1000):
                thread.terminate()
                thread.wait()
            thread.deleteLater()
        worker.deleteLater()
    
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
        self._is_recording = False
        self._is_processing = False
        
        self._hotkey_manager.stop()
        self._recorder.stop_recording()
        
        if self._transcription_thread and self._transcription_thread.isRunning():
            self._transcription_thread.quit()
            if not self._transcription_thread.wait(2000):
                self._transcription_thread.terminate()
                self._transcription_thread.wait()
        
        self._tray_icon.hide()
        self._main_window.close()
        
        QTimer.singleShot(100, self._app.quit)


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
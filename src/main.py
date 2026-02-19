"""Main entry point for LocalVoice application."""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QThread, Signal, QObject, QTimer

log_dir = Path.home() / ".localvoice" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "localvoice.log"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info("LocalVoice starting up...")


def _configure_ssl_certificates():
    """Prefer certifi CA bundle in packaged runtimes that miss system certs."""
    try:
        import certifi
    except Exception:
        return
    cert_path = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", cert_path)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", cert_path)


_configure_ssl_certificates()

from .gui.main_window import FloatingWindow, AppState
from .gui.tray_icon import TrayIcon
from .gui.settings_dialog import SettingsDialog
from .gui.themes import get_stylesheet
from .audio.recorder import AudioRecorder
from .audio.sounds import get_sound_manager
from .history.manager import HistoryManager
from .history.dialog import HistoryDialog
from .vocabulary.manager import VocabularyManager
from .transcription.engine import TranscriptionEngine, TranscriptionConfig, ModelSize
from .injection.text_injector import TextInjector, InjectionConfig, InjectionMethod
from .hotkey.manager import HotkeyManager, HotkeyConfig
from .profiles.manager import ProfileManager


class TranscriptionWorker(QObject):
    finished = Signal()
    
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


class LocalVoiceApp(QObject):
    injection_complete = Signal()
    start_recording_requested = Signal()
    stop_recording_requested = Signal()
    toggle_recording_requested = Signal()
    
    def __init__(self, app: QApplication):
        super().__init__()
        self._app = app
        self._profile_manager = ProfileManager()
        
        self._recorder = AudioRecorder()
        self._engine = TranscriptionEngine()
        self._injector = TextInjector()
        self._hotkey_manager = HotkeyManager()
        self._history_manager: Optional[HistoryManager] = None
        self._history_dialog: Optional[HistoryDialog] = None
        self._vocabulary_manager: Optional[VocabularyManager] = None
        self._active_profile_id = "default"
        self._active_profile_name = "Default"
        
        self._main_window: Optional[FloatingWindow] = None
        self._tray_icon: Optional[TrayIcon] = None
        self._transcription_worker: Optional[TranscriptionWorker] = None
        self._transcription_thread: Optional[QThread] = None
        
        self._is_recording = False
        self._is_processing = False
        self._recording_start_time = None
        
        self._init_components()
        self._connect_signals()
        self._load_settings()
    
    def _init_components(self):
        self._main_window = FloatingWindow()
        self._tray_icon = TrayIcon()
        self._tray_icon.show()
        
        global_settings = self._profile_manager.get_global_settings()
        if not global_settings.get('start_minimized', False):
            self._main_window.show()
    
    def _connect_signals(self):
        self._main_window.recording_toggled.connect(self._on_recording_toggled)
        self._main_window.settings_requested.connect(self._show_settings)
        self._main_window.history_requested.connect(self._show_history)
        self._main_window.quit_requested.connect(self._quit)
        
        self._tray_icon.recording_toggled.connect(self._on_tray_recording_toggled)
        self._tray_icon.show_window_requested.connect(self._main_window.show)
        self._tray_icon.hide_window_requested.connect(self._main_window.hide)
        self._tray_icon.settings_requested.connect(self._show_settings)
        self._tray_icon.history_requested.connect(self._show_history)
        self._tray_icon.profile_selected.connect(self._on_profile_selected)
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
        global_settings = self._profile_manager.get_global_settings()
        active_profile = self._profile_manager.get_active_profile()
        settings = active_profile["settings"]
        self._active_profile_id = active_profile["id"]
        self._active_profile_name = active_profile["name"]

        theme = global_settings.get('theme', 'dark')
        self._apply_theme(theme)
        
        self._main_window.set_opacity(global_settings.get('window_opacity', 95) / 100.0)
        self._main_window.set_profile_name(self._active_profile_name)
        
        hotkey = settings.get('hotkey', 'caps_lock')
        hotkey_mode = settings.get('hotkey_mode', 'hold')
        hotkey_config = HotkeyConfig.parse(hotkey, hotkey_mode)
        
        self._main_window.set_hotkey_info(hotkey, hotkey_mode)
        
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
        
        input_device = settings.get('input_device', None)
        if input_device is not None:
            self._recorder.set_input_device(input_device)
        
        sound_manager = get_sound_manager()
        sound_manager.enabled = settings.get('enable_sounds', False)

        if self._history_manager is None:
            self._history_manager = HistoryManager(
                max_entries=settings.get('history_max_entries', 500)
            )
        else:
            self._history_manager.max_entries = settings.get('history_max_entries', 500)
        self._history_manager.enabled = settings.get('enable_history', True)

        if self._vocabulary_manager is None:
            self._vocabulary_manager = VocabularyManager()
        words = settings.get('vocabulary_words', [])
        substitutions = settings.get('vocabulary_substitutions', {})
        self._vocabulary_manager.set_words(words)
        self._vocabulary_manager.set_substitutions(substitutions)
        self._engine.set_vocabulary_manager(self._vocabulary_manager)

        tray_profiles = [
            (profile["id"], profile["name"]) for profile in self._profile_manager.get_profiles()
        ]
        self._tray_icon.set_profiles(tray_profiles, self._active_profile_id)

        if self._history_dialog:
            self._history_dialog.set_active_profile(self._active_profile_id, self._active_profile_name)
    
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
            logger.debug("Already recording or processing, skipping")
            return
        
        logger.info("Starting recording...")
        if self._recorder.start_recording():
            self._is_recording = True
            self._recording_start_time = datetime.now()
            self._main_window.set_state(AppState.RECORDING)
            self._tray_icon.set_state("recording")
            get_sound_manager().play_start_sound()
            logger.info("Recording started successfully")
        else:
            logger.error("Failed to start recording")
    
    def _stop_recording(self):
        if not self._is_recording:
            logger.debug("Not recording, skipping stop")
            return
        
        logger.info("Stopping recording...")
        get_sound_manager().play_stop_sound()
        audio_data = self._recorder.stop_recording()
        self._is_recording = False
        
        if audio_data is not None and len(audio_data) > 0:
            logger.info(f"Recorded {len(audio_data)} audio samples, starting transcription")
            self._start_transcription(audio_data)
        else:
            logger.warning("No audio data recorded")
            self._recording_start_time = None
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
        
        settings = self._profile_manager.get_active_profile_settings()
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
        
        if not self._engine.load_model(transcription_config):
            self._is_processing = False
            self._recording_start_time = None
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
        recording_start_time = self._recording_start_time
        self._transcription_worker = None
        self._transcription_thread = None
        self._is_processing = False
        self._recording_start_time = None
        
        if not worker:
            logger.warning("Worker is None in _on_worker_finished")
            return
        
        error = worker.get_error()
        if error:
            logger.error(f"Transcription error: {error}")
            self._main_window.set_state(AppState.ERROR)
            self._tray_icon.set_state("error")
            QMessageBox.warning(
                self._main_window,
                "Transcription Error",
                f"Failed to transcribe audio: {error}"
            )
        else:
            text = worker.get_result()
            logger.info(f"Transcription result: {text[:100] if text else 'empty'}...")
            if text.strip():
                duration = None
                if recording_start_time:
                    duration = (datetime.now() - recording_start_time).total_seconds()
                
                if self._history_manager:
                    settings = self._profile_manager.get_active_profile_settings()
                    language = settings.get('language', 'auto')
                    if language == 'auto':
                        language = None
                    self._history_manager.add_entry(text, self._active_profile_id, language, duration)
                
                settings = self._profile_manager.get_active_profile_settings()
                if settings.get('copy_only', False):
                    logger.info("Copy-only mode: copying to clipboard")
                    import pyperclip
                    pyperclip.copy(text)
                    self._tray_icon.show_message("LocalVoice", "Copied to clipboard")
                    self._main_window.set_state(AppState.IDLE)
                    self._tray_icon.set_state("idle")
                else:
                    logger.info("Starting text injection...")
                    self._injector.inject_async(text)
            else:
                logger.warning("Transcription returned empty text")
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
        current_settings = self._profile_manager.get_state()
        dialog = SettingsDialog(current_settings, self._main_window)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()
    
    def _on_settings_changed(self, settings: Dict[str, Any]):
        self._profile_manager.save_state(settings)
        self._load_settings()

    def _on_profile_selected(self, profile_id: str):
        if self._is_recording or self._is_processing:
            self._tray_icon.show_message("LocalVoice", "Cannot switch profile while recording or processing")
            return
        if profile_id == self._active_profile_id:
            return
        if not self._profile_manager.set_active_profile(profile_id):
            self._tray_icon.show_message("LocalVoice", "Failed to switch profile")
            return
        self._load_settings()
    
    def _show_history(self):
        if not self._history_manager or not self._history_manager.enabled:
            QMessageBox.information(
                self._main_window,
                "History Disabled",
                "History is currently disabled. Enable it in Settings to use this feature."
            )
            return
        
        if self._history_dialog is None:
            self._history_dialog = HistoryDialog(self._history_manager, self._main_window)
            self._history_dialog.set_active_profile(self._active_profile_id, self._active_profile_name)
        else:
            self._history_dialog.set_active_profile(self._active_profile_id, self._active_profile_name)
        
        self._history_dialog.show()
        self._history_dialog.raise_()
        self._history_dialog.activateWindow()
    
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
    
    def _apply_theme(self, theme_name: str):
        stylesheet = get_stylesheet(theme_name)
        self._app.setStyleSheet(stylesheet)
        
        self._main_window.set_theme(theme_name)
        self._tray_icon.set_theme(theme_name)
        
        if self._history_dialog:
            self._history_dialog.setStyleSheet(stylesheet)


def main():
    if sys.platform == 'darwin':
        sys.argv.extend(['-platform', 'cocoa'])
    
    app = QApplication(sys.argv)
    app.setApplicationName("LocalVoice")
    app.setApplicationDisplayName("LocalVoice")
    app.setQuitOnLastWindowClosed(False)
    
    app.setStyle('Fusion')
    
    from PySide6.QtGui import QPalette, QColor
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

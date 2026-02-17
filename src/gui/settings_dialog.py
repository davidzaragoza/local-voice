"""Settings dialog for LocalVoice configuration."""

import json
from pathlib import Path
from typing import Optional, Dict, Any, Set, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QComboBox, QLabel, QPushButton, QCheckBox, QSlider,
    QGroupBox, QFormLayout, QSpinBox, QDialogButtonBox,
    QRadioButton, QButtonGroup, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QTimer
from PyQt6.QtGui import QKeyEvent, QKeySequence


class HotkeyRecorder(QLineEdit):
    hotkey_recorded = pyqtSignal(str)
    
    KEY_MAP = {
        Qt.Key.Key_CapsLock: 'Caps Lock',
        Qt.Key.Key_F1: 'F1',
        Qt.Key.Key_F2: 'F2',
        Qt.Key.Key_F3: 'F3',
        Qt.Key.Key_F4: 'F4',
        Qt.Key.Key_F5: 'F5',
        Qt.Key.Key_F6: 'F6',
        Qt.Key.Key_F7: 'F7',
        Qt.Key.Key_F8: 'F8',
        Qt.Key.Key_F9: 'F9',
        Qt.Key.Key_F10: 'F10',
        Qt.Key.Key_F11: 'F11',
        Qt.Key.Key_F12: 'F12',
        Qt.Key.Key_Space: 'Space',
        Qt.Key.Key_Tab: 'Tab',
        Qt.Key.Key_Enter: 'Enter',
        Qt.Key.Key_Return: 'Enter',
        Qt.Key.Key_Backspace: 'Backspace',
        Qt.Key.Key_Escape: 'Esc',
        Qt.Key.Key_Insert: 'Insert',
        Qt.Key.Key_Delete: 'Delete',
        Qt.Key.Key_Home: 'Home',
        Qt.Key.Key_End: 'End',
        Qt.Key.Key_PageUp: 'PageUp',
        Qt.Key.Key_PageDown: 'PageDown',
        Qt.Key.Key_Up: 'Up',
        Qt.Key.Key_Down: 'Down',
        Qt.Key.Key_Left: 'Left',
        Qt.Key.Key_Right: 'Right',
    }
    
    MODIFIER_KEYS = {
        Qt.Key.Key_Shift: 'Shift',
        Qt.Key.Key_Control: 'Ctrl',
        Qt.Key.Key_Alt: 'Alt',
        Qt.Key.Key_Meta: 'Cmd',
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = False
        self._pressed_modifiers: Set[str] = set()
        self._main_key: Optional[str] = None
        self.setReadOnly(True)
        self.setPlaceholderText("Click 'Record' to set hotkey")
        self.setText("Caps Lock")
        
        self._current_hotkey = 'caps_lock'
        self._finalize_timer = QTimer(self)
        self._finalize_timer.setSingleShot(True)
        self._finalize_timer.timeout.connect(self._finalize_hotkey)
    
    def start_recording(self):
        self._recording = True
        self._pressed_modifiers = set()
        self._main_key = None
        self.setText("Press keys...")
        self.setStyleSheet("background-color: #3a5a3a;")
        self.setFocus()
        self._finalize_timer.stop()
    
    def stop_recording(self):
        self._recording = False
        self._finalize_timer.stop()
        self.setStyleSheet("")
        if self._main_key or self._pressed_modifiers:
            self._save_current_hotkey()
    
    def _save_current_hotkey(self):
        if self._main_key:
            hotkey_parts = sorted(self._pressed_modifiers) + [self._main_key]
            hotkey_code = '+'.join([p.lower().replace(' ', '_') for p in hotkey_parts])
            self._current_hotkey = hotkey_code
        elif self._pressed_modifiers:
            hotkey_parts = sorted(self._pressed_modifiers)
            hotkey_code = '+'.join([p.lower().replace(' ', '_') for p in hotkey_parts])
            self._current_hotkey = hotkey_code
    
    def keyPressEvent(self, event: QKeyEvent):
        if not self._recording:
            super().keyPressEvent(event)
            return
        
        key = event.key()
        
        if key == Qt.Key.Key_Escape:
            self.stop_recording()
            self.set_hotkey(self._current_hotkey)
            return
        
        if key in self.MODIFIER_KEYS:
            self._pressed_modifiers.add(self.MODIFIER_KEYS[key])
            self._update_display()
            self._finalize_timer.stop()
            return
        
        if key in self.KEY_MAP:
            self._main_key = self.KEY_MAP[key]
        else:
            text = event.text().upper()
            if text and text.isalnum():
                self._main_key = text
            elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
                self._main_key = chr(ord('A') + (key - Qt.Key.Key_A))
            elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
                self._main_key = chr(ord('0') + (key - Qt.Key.Key_0))
        
        if self._main_key:
            self._update_display()
            self._finalize_timer.start(500)
    
    def keyReleaseEvent(self, event: QKeyEvent):
        if not self._recording:
            super().keyReleaseEvent(event)
            return
        
        key = event.key()
        
        if key in self.MODIFIER_KEYS:
            mod_name = self.MODIFIER_KEYS[key]
            self._pressed_modifiers.discard(mod_name)
            if not self._main_key:
                self._update_display()
                if not self._pressed_modifiers:
                    self._save_current_hotkey()
    
    def _update_display(self):
        parts = sorted(self._pressed_modifiers)
        if self._main_key:
            parts.append(self._main_key)
        if parts:
            self.setText('+'.join(parts))
    
    def _finalize_hotkey(self):
        if not self._recording:
            return
        
        self.stop_recording()
        
        if not self._main_key and not self._pressed_modifiers:
            self.set_hotkey(self._current_hotkey)
            return
        
        self._save_current_hotkey()
        self._update_display()
    
    def set_hotkey(self, hotkey: str):
        self._current_hotkey = hotkey
        parts = hotkey.split('+')
        display_parts = []
        for p in parts:
            if p == 'caps_lock':
                display_parts.append('Caps Lock')
            else:
                display_parts.append(p.title())
        self.setText('+'.join(display_parts))
    
    def get_hotkey(self) -> str:
        return self._current_hotkey


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal(dict)
    
    LANGUAGE_MAP = {
        'auto': 'Auto Detect',
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ja': 'Japanese',
        'zh': 'Chinese',
        'ko': 'Korean',
        'ar': 'Arabic',
        'hi': 'Hindi',
        'nl': 'Dutch',
        'pl': 'Polish',
        'sv': 'Swedish',
    }
    
    MODEL_SIZES = [
        ('tiny', 'Tiny (39M) - Fastest'),
        ('tiny.en', 'Tiny English (39M)'),
        ('base', 'Base (74M) - Fast'),
        ('base.en', 'Base English (74M)'),
        ('small', 'Small (244M) - Medium'),
        ('small.en', 'Small English (244M)'),
        ('medium', 'Medium (769M) - Slow'),
        ('large-v3', 'Large v3 (1550M) - Slowest'),
    ]
    
    INJECTION_METHODS = [
        ('clipboard', 'Clipboard Paste'),
        ('keyboard', 'Keyboard Simulation'),
        ('clipboard_keyboard_fallback', 'Clipboard with Keyboard Fallback'),
    ]
    
    def __init__(self, current_settings: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self._settings = current_settings or self._get_default_settings()
        self._init_ui()
        self._load_settings()
    
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
            'typing_delay': 10,
            'add_trailing_space': True,
            'preserve_clipboard': True,
        }
    
    def _init_ui(self):
        self.setWindowTitle("LocalVoice Settings")
        self.setMinimumWidth(450)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self.tabs.addTab(self._create_general_tab(), "General")
        self.tabs.addTab(self._create_model_tab(), "Model")
        self.tabs.addTab(self._create_hotkey_tab(), "Hotkey")
        self.tabs.addTab(self._create_injection_tab(), "Injection")
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _create_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        startup_group = QGroupBox("Startup")
        startup_layout = QVBoxLayout(startup_group)
        self.start_minimized = QCheckBox("Start minimized to system tray")
        startup_layout.addWidget(self.start_minimized)
        layout.addWidget(startup_group)
        
        language_group = QGroupBox("Language")
        language_layout = QFormLayout(language_group)
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            'Auto Detect', 'English', 'Spanish', 'French', 'German',
            'Italian', 'Portuguese', 'Russian', 'Japanese', 'Chinese',
            'Korean', 'Arabic', 'Hindi', 'Dutch', 'Polish', 'Swedish'
        ])
        language_layout.addRow("Speech Language:", self.language_combo)
        layout.addWidget(language_group)
        
        translation_group = QGroupBox("Translation")
        translation_layout = QVBoxLayout(translation_group)
        self.translate_to_english = QCheckBox("Translate to English")
        self.translate_to_english.setToolTip("Transcribe speech and output text in English regardless of input language")
        translation_layout.addWidget(self.translate_to_english)
        translation_info = QLabel("When enabled, speech in any language will be\ntranscribed and translated to English text.")
        translation_info.setStyleSheet("color: #888; font-size: 11px;")
        translation_layout.addWidget(translation_info)
        layout.addWidget(translation_group)
        
        opacity_group = QGroupBox("Window")
        opacity_layout = QVBoxLayout(opacity_group)
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(95)
        self.opacity_slider.valueChanged.connect(self._update_opacity_label)
        
        self.opacity_label = QLabel("95%")
        opacity_layout.addWidget(self.opacity_label)
        opacity_layout.addWidget(self.opacity_slider)
        layout.addWidget(opacity_group)
        
        layout.addStretch()
        return widget
    
    def _create_model_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        model_group = QGroupBox("Whisper Model")
        model_layout = QFormLayout(model_group)
        
        self.model_combo = QComboBox()
        for value, label in self.MODEL_SIZES:
            self.model_combo.addItem(label, value)
        model_layout.addRow("Model Size:", self.model_combo)
        
        self.model_info = QLabel()
        self.model_info.setWordWrap(True)
        self.model_info.setStyleSheet("color: #888; font-size: 11px;")
        self.model_info.setText("Base model offers good accuracy with fast processing.\nLarger models improve accuracy but require more resources.")
        model_layout.addRow(self.model_info)
        layout.addWidget(model_group)
        
        device_group = QGroupBox("Processing Device")
        device_layout = QVBoxLayout(device_group)
        
        self.device_auto = QRadioButton("Auto (Recommended)")
        self.device_auto.setChecked(True)
        self.device_cpu = QRadioButton("CPU Only")
        self.device_gpu = QRadioButton("GPU (CUDA)")
        
        device_layout.addWidget(self.device_auto)
        device_layout.addWidget(self.device_cpu)
        device_layout.addWidget(self.device_gpu)
        layout.addWidget(device_group)
        
        layout.addStretch()
        return widget
    
    def _create_hotkey_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        hotkey_group = QGroupBox("Push-to-Talk Hotkey")
        hotkey_layout = QVBoxLayout(hotkey_group)
        
        info_label = QLabel("Click 'Record' then press your desired hotkey combination.\nPress Escape to cancel recording.")
        info_label.setStyleSheet("color: #888; font-size: 11px;")
        info_label.setWordWrap(True)
        hotkey_layout.addWidget(info_label)
        
        hotkey_row = QHBoxLayout()
        self.hotkey_recorder = HotkeyRecorder()
        self.hotkey_recorder.setMinimumWidth(200)
        hotkey_row.addWidget(self.hotkey_recorder)
        
        self.record_btn = QPushButton("Record")
        self.record_btn.setFixedWidth(80)
        self.record_btn.clicked.connect(self._toggle_recording)
        hotkey_row.addWidget(self.record_btn)
        
        self.clear_btn = QPushButton("Reset")
        self.clear_btn.setFixedWidth(80)
        self.clear_btn.clicked.connect(self._reset_hotkey)
        hotkey_row.addWidget(self.clear_btn)
        
        hotkey_row.addStretch()
        hotkey_layout.addLayout(hotkey_row)
        
        layout.addWidget(hotkey_group)
        
        mode_group = QGroupBox("Activation Mode")
        mode_layout = QVBoxLayout(mode_group)
        
        self.mode_hold = QRadioButton("Hold to Record - Hold key to record, release to stop")
        self.mode_hold.setChecked(True)
        self.mode_toggle = QRadioButton("Toggle - Press once to start, press again to stop")
        
        mode_layout.addWidget(self.mode_hold)
        mode_layout.addWidget(self.mode_toggle)
        layout.addWidget(mode_group)
        
        layout.addStretch()
        return widget
    
    def _toggle_recording(self):
        if self.hotkey_recorder._recording:
            self.hotkey_recorder.stop_recording()
            self.record_btn.setText("Record")
        else:
            self.hotkey_recorder.start_recording()
            self.record_btn.setText("Stop")
    
    def _reset_hotkey(self):
        self.hotkey_recorder.set_hotkey('caps_lock')
    
    def _create_injection_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        method_group = QGroupBox("Text Insertion Method")
        method_layout = QVBoxLayout(method_group)
        
        self.injection_group = QButtonGroup(self)
        for i, (value, label) in enumerate(self.INJECTION_METHODS):
            radio = QRadioButton(label)
            radio.setProperty('method', value)
            self.injection_group.addButton(radio, i)
            method_layout.addWidget(radio)
        
        layout.addWidget(method_group)
        
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        
        self.add_trailing_space = QCheckBox("Add trailing space after text")
        self.add_trailing_space.setChecked(True)
        options_layout.addWidget(self.add_trailing_space)
        
        self.preserve_clipboard = QCheckBox("Preserve original clipboard content")
        self.preserve_clipboard.setChecked(True)
        options_layout.addWidget(self.preserve_clipboard)
        
        typing_layout = QHBoxLayout()
        typing_layout.addWidget(QLabel("Typing delay (ms):"))
        self.typing_delay = QSpinBox()
        self.typing_delay.setRange(0, 100)
        self.typing_delay.setValue(10)
        typing_layout.addWidget(self.typing_delay)
        typing_layout.addStretch()
        options_layout.addLayout(typing_layout)
        
        layout.addWidget(options_group)
        layout.addStretch()
        return widget
    
    def _update_opacity_label(self, value: int):
        self.opacity_label.setText(f"{value}%")
    
    def _load_settings(self):
        settings = self._settings
        
        self.model_combo.setCurrentIndex(
            next((i for i, (v, _) in enumerate(self.MODEL_SIZES) if v == settings.get('model_size', 'base')), 1)
        )
        
        language = settings.get('language', 'auto')
        language_name = self.LANGUAGE_MAP.get(language, 'Auto Detect')
        for i in range(self.language_combo.count()):
            if self.language_combo.itemText(i) == language_name:
                self.language_combo.setCurrentIndex(i)
                break
        
        hotkey = settings.get('hotkey', 'caps_lock')
        mode = settings.get('hotkey_mode', 'hold')
        self.hotkey_recorder.set_hotkey(hotkey)
        
        if mode == 'hold':
            self.mode_hold.setChecked(True)
        else:
            self.mode_toggle.setChecked(True)
        
        injection_method = settings.get('injection_method', 'clipboard')
        for i, (value, _) in enumerate(self.INJECTION_METHODS):
            if value == injection_method:
                btn = self.injection_group.button(i)
                if btn:
                    btn.setChecked(True)
                    break
        
        self.start_minimized.setChecked(settings.get('start_minimized', False))
        self.translate_to_english.setChecked(settings.get('translate_to_english', False))
        self.add_trailing_space.setChecked(settings.get('add_trailing_space', True))
        self.preserve_clipboard.setChecked(settings.get('preserve_clipboard', True))
        self.typing_delay.setValue(settings.get('typing_delay', 10))
        self.opacity_slider.setValue(int(settings.get('window_opacity', 95)))
        
        device = settings.get('device', 'auto')
        if device == 'auto':
            self.device_auto.setChecked(True)
        elif device == 'cpu':
            self.device_cpu.setChecked(True)
        else:
            self.device_gpu.setChecked(True)
    
    def get_settings(self) -> Dict[str, Any]:
        language_code_to_name = self.LANGUAGE_MAP
        language_name_to_code = {v: k for k, v in language_code_to_name.items()}
        
        device = 'auto'
        if self.device_cpu.isChecked():
            device = 'cpu'
        elif self.device_gpu.isChecked():
            device = 'cuda'
        
        injection_method = 'clipboard'
        checked_btn = self.injection_group.checkedButton()
        if checked_btn:
            injection_method = checked_btn.property('method')
        
        language_text = self.language_combo.currentText()
        
        return {
            'model_size': self.model_combo.currentData(),
            'language': language_name_to_code.get(language_text, 'auto'),
            'translate_to_english': self.translate_to_english.isChecked(),
            'hotkey': self.hotkey_recorder.get_hotkey(),
            'hotkey_mode': 'hold' if self.mode_hold.isChecked() else 'toggle',
            'injection_method': injection_method,
            'start_minimized': self.start_minimized.isChecked(),
            'window_opacity': self.opacity_slider.value(),
            'device': device,
            'typing_delay': self.typing_delay.value(),
            'add_trailing_space': self.add_trailing_space.isChecked(),
            'preserve_clipboard': self.preserve_clipboard.isChecked(),
        }
    
    def _apply_settings(self):
        settings = self.get_settings()
        self.settings_changed.emit(settings)
    
    def accept(self):
        if self.hotkey_recorder._recording:
            self.hotkey_recorder.stop_recording()
        self._apply_settings()
        super().accept()
    
    def reject(self):
        if self.hotkey_recorder._recording:
            self.hotkey_recorder.stop_recording()
        super().reject()
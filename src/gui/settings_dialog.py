"""Settings dialog for LocalVoice configuration."""

from copy import deepcopy
from typing import Optional, Dict, Any, Set, List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QComboBox, QLabel, QPushButton, QCheckBox, QSlider,
    QGroupBox, QFormLayout, QSpinBox, QDialogButtonBox,
    QRadioButton, QButtonGroup, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QKeyEvent

import sounddevice as sd


class HotkeyRecorder(QLineEdit):
    hotkey_recorded = Signal(str)
    
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
    settings_changed = Signal(dict)
    
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
        self._state = self._normalize_state(current_settings or self._default_state())
        self._active_profile_id = self._state.get('active_profile_id', 'default')
        self._is_switching_profile = False
        self._init_ui()
        self._load_state_into_ui()
    
    def _default_profile_settings(self) -> Dict[str, Any]:
        return {
            'model_size': 'base',
            'language': 'auto',
            'translate_to_english': False,
            'hotkey': 'caps_lock',
            'hotkey_mode': 'hold',
            'injection_method': 'clipboard',
            'device': 'auto',
            'typing_delay': 10,
            'add_trailing_space': True,
            'preserve_clipboard': True,
            'input_device': None,
            'enable_sounds': False,
            'enable_history': True,
            'history_max_entries': 500,
            'vocabulary_words': [],
            'vocabulary_substitutions': {},
            'copy_only': False,
        }

    def _default_global_settings(self) -> Dict[str, Any]:
        return {
            'start_minimized': False,
            'window_opacity': 95,
            'theme': 'dark',
        }

    def _default_state(self) -> Dict[str, Any]:
        return {
            'version': 2,
            'active_profile_id': 'default',
            'global': self._default_global_settings(),
            'profiles': [
                {
                    'id': 'default',
                    'name': 'Default',
                    'settings': self._default_profile_settings(),
                }
            ],
        }

    def _normalize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if 'profiles' not in state or 'global' not in state:
            global_settings = self._default_global_settings()
            profile_settings = self._default_profile_settings()
            for key, value in state.items():
                if key in global_settings:
                    global_settings[key] = value
                elif key in profile_settings:
                    profile_settings[key] = value
            return {
                'version': 2,
                'active_profile_id': 'default',
                'global': global_settings,
                'profiles': [
                    {'id': 'default', 'name': 'Default', 'settings': profile_settings}
                ],
            }

        normalized = self._default_state()
        loaded_global = state.get('global', {})
        if isinstance(loaded_global, dict):
            for key in normalized['global']:
                if key in loaded_global:
                    normalized['global'][key] = loaded_global[key]

        profiles = []
        loaded_profiles = state.get('profiles', [])
        if isinstance(loaded_profiles, list):
            for idx, profile in enumerate(loaded_profiles):
                if not isinstance(profile, dict):
                    continue
                profile_id = str(profile.get('id') or f"profile_{idx + 1}").strip()
                profile_name = str(profile.get('name') or f"Profile {idx + 1}").strip()
                profile_settings = self._default_profile_settings()
                raw_settings = profile.get('settings', {})
                if isinstance(raw_settings, dict):
                    for key in profile_settings:
                        if key in raw_settings:
                            profile_settings[key] = raw_settings[key]
                profiles.append({'id': profile_id, 'name': profile_name, 'settings': profile_settings})

        if not profiles:
            profiles = normalized['profiles']
        normalized['profiles'] = profiles

        active_profile_id = str(state.get('active_profile_id') or '').strip()
        if not any(p['id'] == active_profile_id for p in profiles):
            active_profile_id = profiles[0]['id']
        normalized['active_profile_id'] = active_profile_id
        return normalized
    
    def _init_ui(self):
        self.setWindowTitle("LocalVoice Settings")
        self.setMinimumWidth(620)
        self.resize(680, 720)
        self.setModal(True)
        
        layout = QVBoxLayout(self)

        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selection_changed)
        profile_row.addWidget(self.profile_combo, 1)

        self.new_profile_btn = QPushButton("New")
        self.new_profile_btn.setFixedWidth(96)
        self.new_profile_btn.clicked.connect(self._create_profile)
        profile_row.addWidget(self.new_profile_btn)

        self.rename_profile_btn = QPushButton("Rename")
        self.rename_profile_btn.setFixedWidth(96)
        self.rename_profile_btn.clicked.connect(self._rename_profile)
        profile_row.addWidget(self.rename_profile_btn)

        self.delete_profile_btn = QPushButton("Delete")
        self.delete_profile_btn.setFixedWidth(96)
        self.delete_profile_btn.clicked.connect(self._delete_profile)
        profile_row.addWidget(self.delete_profile_btn)

        layout.addLayout(profile_row)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self.tabs.addTab(self._create_general_tab(), "General")
        self.tabs.addTab(self._create_audio_tab(), "Audio")
        self.tabs.addTab(self._create_model_tab(), "Model")
        self.tabs.addTab(self._create_hotkey_tab(), "Hotkey")
        self.tabs.addTab(self._create_injection_tab(), "Injection")
        self.tabs.addTab(self._create_vocabulary_tab(), "Vocabulary")
        
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
        
        history_group = QGroupBox("History")
        history_layout = QVBoxLayout(history_group)
        
        self.enable_history = QCheckBox("Enable transcription history")
        self.enable_history.setChecked(True)
        history_layout.addWidget(self.enable_history)
        
        max_entries_layout = QHBoxLayout()
        max_entries_layout.addWidget(QLabel("Max entries:"))
        self.history_max_entries = QSpinBox()
        self.history_max_entries.setRange(50, 5000)
        self.history_max_entries.setValue(500)
        self.history_max_entries.setSingleStep(100)
        max_entries_layout.addWidget(self.history_max_entries)
        max_entries_layout.addStretch()
        history_layout.addLayout(max_entries_layout)
        
        layout.addWidget(history_group)
        
        theme_group = QGroupBox("Appearance")
        theme_layout = QVBoxLayout(theme_group)
        
        theme_form = QFormLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        theme_form.addRow("Theme:", self.theme_combo)
        theme_layout.addLayout(theme_form)
        
        layout.addWidget(theme_group)
        
        layout.addStretch()
        return widget
    
    def _create_audio_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        input_group = QGroupBox("Input Device")
        input_layout = QVBoxLayout(input_group)
        
        info_label = QLabel("Select the microphone to use for recording.")
        info_label.setStyleSheet("color: #888; font-size: 11px;")
        info_label.setWordWrap(True)
        input_layout.addWidget(info_label)
        
        self.input_device_combo = QComboBox()
        self._populate_input_devices()
        input_layout.addWidget(self.input_device_combo)
        
        refresh_btn = QPushButton("Refresh Devices")
        refresh_btn.setFixedWidth(120)
        refresh_btn.clicked.connect(self._populate_input_devices)
        input_layout.addWidget(refresh_btn)
        
        layout.addWidget(input_group)
        
        sounds_group = QGroupBox("Audio Feedback")
        sounds_layout = QVBoxLayout(sounds_group)
        
        self.enable_sounds = QCheckBox("Enable audio feedback sounds")
        self.enable_sounds.setToolTip("Play a sound when recording starts and stops")
        sounds_layout.addWidget(self.enable_sounds)
        
        sounds_info = QLabel("Provides audio confirmation of recording state\nwhen the floating window is not visible.")
        sounds_info.setStyleSheet("color: #888; font-size: 11px;")
        sounds_layout.addWidget(sounds_info)
        
        layout.addWidget(sounds_group)
        
        layout.addStretch()
        return widget
    
    def _populate_input_devices(self):
        self.input_device_combo.clear()
        self.input_device_combo.addItem("Default", None)
        
        try:
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    name = device['name']
                    if len(name) > 50:
                        name = name[:47] + "..."
                    self.input_device_combo.addItem(f"{name}", i)
        except Exception as e:
            self.input_device_combo.addItem("Error loading devices", None)
    
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
        
        self.copy_only = QCheckBox("Copy to clipboard only (no auto-paste)")
        self.copy_only.setToolTip("When enabled, transcribed text is copied to clipboard without automatic pasting")
        options_layout.addWidget(self.copy_only)
        
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
    
    def _create_vocabulary_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        words_group = QGroupBox("Custom Words")
        words_layout = QVBoxLayout(words_group)
        
        words_info = QLabel("Add names, technical terms, or domain-specific words to improve transcription accuracy.")
        words_info.setStyleSheet("color: #888; font-size: 11px;")
        words_info.setWordWrap(True)
        words_layout.addWidget(words_info)
        
        self._words_list = QListWidget()
        self._words_list.setMaximumHeight(150)
        words_layout.addWidget(self._words_list)
        
        add_word_layout = QHBoxLayout()
        self._new_word_input = QLineEdit()
        self._new_word_input.setPlaceholderText("Enter a word or phrase")
        add_word_layout.addWidget(self._new_word_input)
        
        add_word_btn = QPushButton("Add")
        add_word_btn.setFixedWidth(60)
        add_word_btn.clicked.connect(self._add_vocabulary_word)
        add_word_layout.addWidget(add_word_btn)
        
        remove_word_btn = QPushButton("Remove")
        remove_word_btn.setFixedWidth(70)
        remove_word_btn.clicked.connect(self._remove_vocabulary_word)
        add_word_layout.addWidget(remove_word_btn)
        
        words_layout.addLayout(add_word_layout)
        
        self._words_count_label = QLabel("0 / 50 words")
        self._words_count_label.setStyleSheet("color: #888; font-size: 11px;")
        words_layout.addWidget(self._words_count_label)
        
        layout.addWidget(words_group)
        
        subs_group = QGroupBox("Substitutions (Optional)")
        subs_layout = QVBoxLayout(subs_group)
        
        subs_info = QLabel("Define text replacements to fix common transcription errors automatically.")
        subs_info.setStyleSheet("color: #888; font-size: 11px;")
        subs_info.setWordWrap(True)
        subs_layout.addWidget(subs_info)
        
        self._subs_list = QListWidget()
        self._subs_list.setMaximumHeight(120)
        subs_layout.addWidget(self._subs_list)
        
        add_sub_layout = QHBoxLayout()
        
        self._sub_from_input = QLineEdit()
        self._sub_from_input.setPlaceholderText("From")
        add_sub_layout.addWidget(self._sub_from_input)
        
        arrow_label = QLabel("→")
        add_sub_layout.addWidget(arrow_label)
        
        self._sub_to_input = QLineEdit()
        self._sub_to_input.setPlaceholderText("To")
        add_sub_layout.addWidget(self._sub_to_input)
        
        add_sub_btn = QPushButton("Add")
        add_sub_btn.setFixedWidth(60)
        add_sub_btn.clicked.connect(self._add_substitution)
        add_sub_layout.addWidget(add_sub_btn)
        
        remove_sub_btn = QPushButton("Remove")
        remove_sub_btn.setFixedWidth(70)
        remove_sub_btn.clicked.connect(self._remove_substitution)
        add_sub_layout.addWidget(remove_sub_btn)
        
        subs_layout.addLayout(add_sub_layout)
        layout.addWidget(subs_group)
        
        layout.addStretch()
        return widget
    
    def _add_vocabulary_word(self):
        word = self._new_word_input.text().strip()
        if word:
            if self._words_list.count() >= 50:
                return
            for i in range(self._words_list.count()):
                if self._words_list.item(i).text().lower() == word.lower():
                    return
            self._words_list.addItem(word)
            self._new_word_input.clear()
            self._update_words_count()
    
    def _remove_vocabulary_word(self):
        current = self._words_list.currentItem()
        if current:
            self._words_list.takeItem(self._words_list.row(current))
            self._update_words_count()
    
    def _update_words_count(self):
        self._words_count_label.setText(f"{self._words_list.count()} / 50 words")
    
    def _add_substitution(self):
        from_text = self._sub_from_input.text().strip()
        to_text = self._sub_to_input.text().strip()
        if from_text and to_text:
            for i in range(self._subs_list.count()):
                item = self._subs_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == from_text:
                    self._subs_list.takeItem(i)
                    break
            item = QListWidgetItem(f'"{from_text}" → "{to_text}"')
            item.setData(Qt.ItemDataRole.UserRole, from_text)
            item.setData(Qt.ItemDataRole.UserRole + 1, to_text)
            self._subs_list.addItem(item)
            self._sub_from_input.clear()
            self._sub_to_input.clear()
    
    def _remove_substitution(self):
        current = self._subs_list.currentItem()
        if current:
            self._subs_list.takeItem(self._subs_list.row(current))
    
    def _load_state_into_ui(self):
        self._refresh_profile_combo()
        self._load_global_settings()
        self._load_profile_settings(self._active_profile_id)

    def _load_global_settings(self):
        global_settings = self._state.get('global', {})
        self.start_minimized.setChecked(global_settings.get('start_minimized', False))
        self.opacity_slider.setValue(int(global_settings.get('window_opacity', 95)))

        theme = global_settings.get('theme', 'dark')
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == theme:
                self.theme_combo.setCurrentIndex(i)
                break

    def _get_profile_by_id(self, profile_id: str) -> Optional[Dict[str, Any]]:
        for profile in self._state.get('profiles', []):
            if profile.get('id') == profile_id:
                return profile
        return None

    def _load_profile_settings(self, profile_id: str):
        profile = self._get_profile_by_id(profile_id)
        if not profile:
            return
        settings = profile['settings']

        self._is_switching_profile = True
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

        self.translate_to_english.setChecked(settings.get('translate_to_english', False))
        self.add_trailing_space.setChecked(settings.get('add_trailing_space', True))
        self.preserve_clipboard.setChecked(settings.get('preserve_clipboard', True))
        self.typing_delay.setValue(settings.get('typing_delay', 10))

        device = settings.get('device', 'auto')
        if device == 'auto':
            self.device_auto.setChecked(True)
        elif device == 'cpu':
            self.device_cpu.setChecked(True)
        else:
            self.device_gpu.setChecked(True)

        input_device = settings.get('input_device', None)
        input_found = False
        for i in range(self.input_device_combo.count()):
            if self.input_device_combo.itemData(i) == input_device:
                self.input_device_combo.setCurrentIndex(i)
                input_found = True
                break
        if not input_found:
            self.input_device_combo.setCurrentIndex(0)

        self.enable_sounds.setChecked(settings.get('enable_sounds', False))
        self.enable_history.setChecked(settings.get('enable_history', True))
        self.history_max_entries.setValue(settings.get('history_max_entries', 500))
        self.copy_only.setChecked(settings.get('copy_only', False))

        self._load_vocabulary(settings)
        self._is_switching_profile = False

    def _load_vocabulary(self, settings: Dict[str, Any]):
        self._words_list.clear()
        self._subs_list.clear()
        
        words = settings.get('vocabulary_words', [])
        for word in words:
            self._words_list.addItem(word)
        self._update_words_count()
        
        substitutions = settings.get('vocabulary_substitutions', {})
        for source, target in substitutions.items():
            item = QListWidgetItem(f'"{source}" → "{target}"')
            item.setData(Qt.ItemDataRole.UserRole, source)
            item.setData(Qt.ItemDataRole.UserRole + 1, target)
            self._subs_list.addItem(item)

    def _collect_profile_settings_from_ui(self) -> Dict[str, Any]:
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
            'device': device,
            'typing_delay': self.typing_delay.value(),
            'add_trailing_space': self.add_trailing_space.isChecked(),
            'preserve_clipboard': self.preserve_clipboard.isChecked(),
            'input_device': self.input_device_combo.currentData(),
            'enable_sounds': self.enable_sounds.isChecked(),
            'enable_history': self.enable_history.isChecked(),
            'history_max_entries': self.history_max_entries.value(),
            'vocabulary_words': self._get_vocabulary_words(),
            'vocabulary_substitutions': self._get_vocabulary_substitutions(),
            'copy_only': self.copy_only.isChecked(),
        }

    def _collect_global_settings_from_ui(self) -> Dict[str, Any]:
        return {
            'start_minimized': self.start_minimized.isChecked(),
            'window_opacity': self.opacity_slider.value(),
            'theme': self.theme_combo.currentData(),
        }

    def _refresh_profile_combo(self):
        self._is_switching_profile = True
        self.profile_combo.clear()
        for profile in self._state.get('profiles', []):
            self.profile_combo.addItem(profile['name'], profile['id'])

        for i in range(self.profile_combo.count()):
            if self.profile_combo.itemData(i) == self._active_profile_id:
                self.profile_combo.setCurrentIndex(i)
                break

        self.delete_profile_btn.setEnabled(len(self._state.get('profiles', [])) > 1)
        self._is_switching_profile = False

    def _save_active_profile_from_ui(self):
        profile = self._get_profile_by_id(self._active_profile_id)
        if not profile:
            return
        profile['settings'] = self._collect_profile_settings_from_ui()
        self._state['global'] = self._collect_global_settings_from_ui()

    def _on_profile_selection_changed(self, index: int):
        if self._is_switching_profile:
            return
        if index < 0:
            return
        selected_profile_id = self.profile_combo.itemData(index)
        if not selected_profile_id or selected_profile_id == self._active_profile_id:
            return

        self._save_active_profile_from_ui()
        self._active_profile_id = selected_profile_id
        self._state['active_profile_id'] = selected_profile_id
        self._load_profile_settings(selected_profile_id)

    def _profile_name_exists(self, name: str, exclude_profile_id: Optional[str] = None) -> bool:
        for profile in self._state.get('profiles', []):
            if exclude_profile_id and profile['id'] == exclude_profile_id:
                continue
            if profile['name'].lower() == name.lower():
                return True
        return False

    def _create_profile(self):
        self._save_active_profile_from_ui()
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if self._profile_name_exists(name):
            QMessageBox.warning(self, "Duplicate Name", "A profile with this name already exists.")
            return

        existing_ids = {p['id'] for p in self._state.get('profiles', [])}
        base = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_") or "profile"
        profile_id = base
        n = 2
        while profile_id in existing_ids:
            profile_id = f"{base}_{n}"
            n += 1

        new_profile = {
            'id': profile_id,
            'name': name,
            'settings': deepcopy(self._collect_profile_settings_from_ui()),
        }
        self._state['profiles'].append(new_profile)
        self._active_profile_id = profile_id
        self._state['active_profile_id'] = profile_id
        self._refresh_profile_combo()
        self._load_profile_settings(profile_id)

    def _rename_profile(self):
        profile = self._get_profile_by_id(self._active_profile_id)
        if not profile:
            return
        name, ok = QInputDialog.getText(self, "Rename Profile", "Profile name:", text=profile['name'])
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if self._profile_name_exists(name, exclude_profile_id=profile['id']):
            QMessageBox.warning(self, "Duplicate Name", "A profile with this name already exists.")
            return
        profile['name'] = name
        self._refresh_profile_combo()

    def _delete_profile(self):
        profiles = self._state.get('profiles', [])
        if len(profiles) <= 1:
            QMessageBox.information(self, "Cannot Delete", "At least one profile must remain.")
            return

        profile = self._get_profile_by_id(self._active_profile_id)
        if not profile:
            return

        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f'Delete profile "{profile["name"]}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._state['profiles'] = [p for p in profiles if p['id'] != profile['id']]
        self._active_profile_id = self._state['profiles'][0]['id']
        self._state['active_profile_id'] = self._active_profile_id
        self._refresh_profile_combo()
        self._load_profile_settings(self._active_profile_id)

    def get_state(self) -> Dict[str, Any]:
        self._save_active_profile_from_ui()
        return {
            'version': 2,
            'active_profile_id': self._active_profile_id,
            'global': deepcopy(self._state.get('global', self._default_global_settings())),
            'profiles': deepcopy(self._state.get('profiles', [])),
        }
    
    def _get_vocabulary_words(self) -> List[str]:
        words = []
        for i in range(self._words_list.count()):
            words.append(self._words_list.item(i).text())
        return words
    
    def _get_vocabulary_substitutions(self) -> Dict[str, str]:
        subs = {}
        for i in range(self._subs_list.count()):
            item = self._subs_list.item(i)
            source = item.data(Qt.ItemDataRole.UserRole)
            target = item.data(Qt.ItemDataRole.UserRole + 1)
            if source and target:
                subs[source] = target
        return subs
    
    def _apply_settings(self):
        self.settings_changed.emit(self.get_state())
    
    def accept(self):
        if self.hotkey_recorder._recording:
            self.hotkey_recorder.stop_recording()
        self._apply_settings()
        super().accept()
    
    def reject(self):
        if self.hotkey_recorder._recording:
            self.hotkey_recorder.stop_recording()
        super().reject()

"""Global hotkey manager using pynput for cross-platform keyboard listening."""

import threading
from typing import Callable, Optional, Set, List
from dataclasses import dataclass, field
from enum import Enum

from pynput import keyboard
from pynput.keyboard import Key, KeyCode


class HotkeyAction(Enum):
    TOGGLE_RECORDING = "toggle_recording"
    START_RECORDING = "start_recording"
    STOP_RECORDING = "stop_recording"


@dataclass
class HotkeyConfig:
    hotkey: str = "caps_lock"
    mode: str = "hold"
    modifiers: Set[str] = field(default_factory=set)
    primary_key: str = "caps_lock"
    
    @classmethod
    def parse(cls, hotkey_string: str, mode: str = "hold") -> 'HotkeyConfig':
        parts = hotkey_string.lower().split('+')
        
        modifier_keywords = {'shift', 'ctrl', 'alt', 'cmd', 'meta'}
        modifiers = set()
        primary_key = None
        
        for part in parts:
            part = part.strip()
            if part in modifier_keywords:
                modifiers.add(part)
            else:
                primary_key = part
        
        if primary_key is None:
            primary_key = parts[-1].strip() if parts else "caps_lock"
            modifiers.discard(primary_key)
        
        return cls(
            hotkey=hotkey_string,
            mode=mode,
            modifiers=modifiers,
            primary_key=primary_key
        )


class HotkeyManager:
    KEY_MAP = {
        'caps_lock': Key.caps_lock,
        'f1': Key.f1,
        'f2': Key.f2,
        'f3': Key.f3,
        'f4': Key.f4,
        'f5': Key.f5,
        'f6': Key.f6,
        'f7': Key.f7,
        'f8': Key.f8,
        'f9': Key.f9,
        'f10': Key.f10,
        'f11': Key.f11,
        'f12': Key.f12,
        'space': Key.space,
        'tab': Key.tab,
        'enter': Key.enter,
        'return': Key.enter,
        'esc': Key.esc,
        'escape': Key.esc,
        'backspace': Key.backspace,
        'home': Key.home,
        'end': Key.end,
        'page_up': Key.page_up,
        'page_down': Key.page_down,
    }
    
    MODIFIER_MAP = {
        'shift': Key.shift,
        'ctrl': Key.ctrl,
        'alt': Key.alt,
        'cmd': Key.cmd,
        'meta': Key.cmd,
    }
    
    REVERSE_MODIFIER_MAP = {
        Key.shift: 'shift',
        Key.shift_l: 'shift',
        Key.shift_r: 'shift',
        Key.ctrl: 'ctrl',
        Key.ctrl_l: 'ctrl',
        Key.ctrl_r: 'ctrl',
        Key.alt: 'alt',
        Key.alt_l: 'alt',
        Key.alt_r: 'alt',
        Key.cmd: 'cmd',
        Key.cmd_l: 'cmd',
        Key.cmd_r: 'cmd',
    }
    
    def __init__(self, config: Optional[HotkeyConfig] = None):
        self.config = config or HotkeyConfig()
        self._listener: Optional[keyboard.Listener] = None
        self._key_pressed: bool = False
        self._modifiers_pressed: Set[str] = set()
        self._on_start_callback: Optional[Callable[[], None]] = None
        self._on_stop_callback: Optional[Callable[[], None]] = None
        self._on_toggle_callback: Optional[Callable[[], None]] = None
        self._lock = threading.Lock()
        self._running = False
    
    def set_on_start(self, callback: Callable[[], None]):
        self._on_start_callback = callback
    
    def set_on_stop(self, callback: Callable[[], None]):
        self._on_stop_callback = callback
    
    def set_on_toggle(self, callback: Callable[[], None]):
        self._on_toggle_callback = callback
    
    def _get_key(self, key_name: str) -> Optional[Key]:
        return self.KEY_MAP.get(key_name.lower())
    
    def _get_modifier(self, mod_name: str) -> Optional[Key]:
        return self.MODIFIER_MAP.get(mod_name.lower())
    
    def _is_modifier_key(self, key) -> bool:
        return key in self.REVERSE_MODIFIER_MAP
    
    def _get_modifier_name(self, key) -> Optional[str]:
        return self.REVERSE_MODIFIER_MAP.get(key)
    
    def _is_primary_a_modifier(self) -> bool:
        return self.config.primary_key in self.MODIFIER_MAP
    
    def _check_modifiers_match(self) -> bool:
        required_mods = self.config.modifiers.copy()
        if not self._is_primary_a_modifier():
            if not required_mods:
                return not self._modifiers_pressed
            return required_mods.issubset(self._modifiers_pressed) and len(self._modifiers_pressed) == len(required_mods)
        return required_mods.issubset(self._modifiers_pressed)
    
    def _all_hotkey_modifiers_pressed(self) -> bool:
        all_mods = self.config.modifiers.copy()
        if self._is_primary_a_modifier():
            all_mods.add(self.config.primary_key)
        return all_mods == self._modifiers_pressed
    
    def _on_press(self, key):
        with self._lock:
            if isinstance(key, Key) and self._is_modifier_key(key):
                mod_name = self._get_modifier_name(key)
                if mod_name:
                    self._modifiers_pressed.add(mod_name)
                
                if self._is_primary_a_modifier():
                    if self._all_hotkey_modifiers_pressed() and self._check_modifiers_match():
                        if self.config.mode == "hold":
                            if not self._key_pressed:
                                self._key_pressed = True
                                if self._on_start_callback:
                                    self._on_start_callback()
                        elif self.config.mode == "toggle":
                            if not self._key_pressed:
                                self._key_pressed = True
                                if self._on_toggle_callback:
                                    self._on_toggle_callback()
                return
            
            primary = self._get_key(self.config.primary_key)
            
            is_primary = False
            if isinstance(key, Key):
                is_primary = key == primary
            elif isinstance(key, KeyCode):
                try:
                    char = key.char
                    if char and char.lower() == self.config.primary_key.lower():
                        is_primary = True
                except AttributeError:
                    pass
            
            if is_primary and self._check_modifiers_match():
                if self.config.mode == "hold":
                    if not self._key_pressed:
                        self._key_pressed = True
                        if self._on_start_callback:
                            self._on_start_callback()
                elif self.config.mode == "toggle":
                    if not self._key_pressed:
                        self._key_pressed = True
                        if self._on_toggle_callback:
                            self._on_toggle_callback()
    
    def _on_release(self, key):
        with self._lock:
            if isinstance(key, Key) and self._is_modifier_key(key):
                mod_name = self._get_modifier_name(key)
                
                if self._is_primary_a_modifier():
                    if self._key_pressed and mod_name in self._modifiers_pressed:
                        self._key_pressed = False
                        if self.config.mode == "hold":
                            if self._on_stop_callback:
                                self._on_stop_callback()
                
                if mod_name:
                    self._modifiers_pressed.discard(mod_name)
                return
            
            primary = self._get_key(self.config.primary_key)
            
            is_primary = False
            if isinstance(key, Key):
                is_primary = key == primary
            elif isinstance(key, KeyCode):
                try:
                    char = key.char
                    if char and char.lower() == self.config.primary_key.lower():
                        is_primary = True
                except AttributeError:
                    pass
            
            if is_primary and self._check_modifiers_match():
                if self.config.mode == "hold":
                    if self._key_pressed:
                        self._key_pressed = False
                        if self._on_stop_callback:
                            self._on_stop_callback()
                elif self.config.mode == "toggle":
                    self._key_pressed = False
    
    def start(self) -> bool:
        if self._running:
            return True
        
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release
            )
            self._listener.start()
            self._running = True
            return True
        except Exception as e:
            print(f"Failed to start hotkey listener: {e}")
            return False
    
    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._running = False
        self._key_pressed = False
        self._modifiers_pressed.clear()
    
    def update_config(self, config: HotkeyConfig):
        with self._lock:
            self.config = config
            self._key_pressed = False
            self._modifiers_pressed.clear()
    
    def update_from_string(self, hotkey_string: str, mode: str = "hold"):
        config = HotkeyConfig.parse(hotkey_string, mode)
        self.update_config(config)
    
    def is_hotkey_pressed(self) -> bool:
        with self._lock:
            return self._key_pressed
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
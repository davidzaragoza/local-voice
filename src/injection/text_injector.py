"""Text injection module for inserting transcribed text into other applications."""

import time
import threading
import logging
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass

import pyperclip
from pynput import keyboard

logger = logging.getLogger(__name__)


class InjectionMethod(Enum):
    CLIPBOARD = "clipboard"
    KEYBOARD = "keyboard"
    CLIPBOARD_KEYBOARD_FALLBACK = "clipboard_keyboard_fallback"


@dataclass
class InjectionConfig:
    method: InjectionMethod = InjectionMethod.CLIPBOARD
    typing_delay: float = 0.01
    add_trailing_space: bool = True
    preserve_clipboard: bool = True


class TextInjector:
    def __init__(self, config: Optional[InjectionConfig] = None):
        self.config = config or InjectionConfig()
        self._keyboard_controller = keyboard.Controller()
        self._clipboard_backup: Optional[str] = None
        self._on_complete_callback: Optional[Callable[[], None]] = None
    
    def set_on_complete_callback(self, callback: Callable[[], None]):
        self._on_complete_callback = callback
    
    def _backup_clipboard(self) -> bool:
        if not self.config.preserve_clipboard:
            return True
        
        try:
            self._clipboard_backup = pyperclip.paste()
            return True
        except Exception:
            self._clipboard_backup = None
            return False
    
    def _restore_clipboard(self):
        if not self.config.preserve_clipboard or self._clipboard_backup is None:
            return
        
        try:
            time.sleep(0.05)
            pyperclip.copy(self._clipboard_backup)
        except Exception as e:
            print(f"Failed to restore clipboard: {e}")
        finally:
            self._clipboard_backup = None
    
    def inject_clipboard(self, text: str) -> bool:
        try:
            logger.info(f"Injecting text via clipboard: {text[:50]}...")
            self._backup_clipboard()
            pyperclip.copy(text)
            time.sleep(0.05)
            
            modifier = self._get_modifier_key_for_platform()
            
            with self._keyboard_controller.pressed(modifier):
                self._keyboard_controller.press('v')
                self._keyboard_controller.release('v')
            
            time.sleep(0.1)
            self._restore_clipboard()
            logger.info("Clipboard injection successful")
            return True
            
        except Exception as e:
            logger.error(f"Clipboard injection failed: {e}")
            print(f"Clipboard injection failed: {e}")
            return False
    
    def inject_keyboard(self, text: str) -> bool:
        try:
            logger.info(f"Injecting text via keyboard: {text[:50]}...")
            for char in text:
                if char == '\n':
                    self._keyboard_controller.press(keyboard.Key.enter)
                    self._keyboard_controller.release(keyboard.Key.enter)
                elif char == '\t':
                    self._keyboard_controller.press(keyboard.Key.tab)
                    self._keyboard_controller.release(keyboard.Key.tab)
                else:
                    self._keyboard_controller.type(char)
                
                if self.config.typing_delay > 0:
                    time.sleep(self.config.typing_delay)
            
            logger.info("Keyboard injection successful")
            return True
            
        except Exception as e:
            logger.error(f"Keyboard injection failed: {e}")
            print(f"Keyboard injection failed: {e}")
            return False
    
    def inject(self, text: str) -> bool:
        if not text.strip():
            return False
        
        if self.config.add_trailing_space and not text.endswith(' ') and not text.endswith('\n'):
            text += ' '
        
        if self.config.method == InjectionMethod.CLIPBOARD:
            success = self.inject_clipboard(text)
            if not success:
                success = self.inject_keyboard(text)
            return success
        
        elif self.config.method == InjectionMethod.KEYBOARD:
            success = self.inject_keyboard(text)
            if not success:
                success = self.inject_clipboard(text)
            return success
        
        elif self.config.method == InjectionMethod.CLIPBOARD_KEYBOARD_FALLBACK:
            success = self.inject_clipboard(text)
            if not success:
                return self.inject_keyboard(text)
            return success
        
        return False
    
    def inject_async(self, text: str, callback: Optional[Callable[[bool], None]] = None):
        def _inject():
            success = self.inject(text)
            if callback:
                callback(success)
            if self._on_complete_callback:
                self._on_complete_callback()
        
        thread = threading.Thread(target=_inject, daemon=True)
        thread.start()
    
    @staticmethod
    def _get_modifier_key_for_platform() -> keyboard.Key:
        import platform
        if platform.system() == 'Darwin':
            return keyboard.Key.cmd
        elif platform.system() == 'Linux':
            return keyboard.Key.ctrl
        else:
            return keyboard.Key.ctrl
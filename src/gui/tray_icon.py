"""System tray icon for LocalVoice."""

from typing import Optional, Callable

from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from PySide6.QtCore import Signal, QObject, Qt

from .themes import get_theme, get_menu_stylesheet


class TrayIcon(QSystemTrayIcon):
    show_window_requested = Signal()
    hide_window_requested = Signal()
    settings_requested = Signal()
    history_requested = Signal()
    quit_requested = Signal()
    recording_toggled = Signal(bool)
    profile_selected = Signal(str)
    _state_change_requested = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_recording = False
        self._theme = "dark"
        self._create_icons()
        self._create_menu()
        
        self._state_change_requested.connect(self._do_set_state)
        
        self.activated.connect(self._on_activated)
        self.setIcon(self._idle_icon)
    
    def set_theme(self, theme_name: str):
        self._theme = theme_name
        self._create_icons()
        self._menu.setStyleSheet(get_menu_stylesheet(theme_name))
    
    def _create_icons(self):
        theme = get_theme(self._theme)
        self._idle_icon = self._create_icon(QColor(theme['tray_idle']))
        self._recording_icon = self._create_icon(QColor(theme['tray_recording']))
        self._processing_icon = self._create_icon(QColor(theme['tray_processing']))
    
    def _create_icon(self, color: QColor) -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(8, 8, 48, 48)
        
        painter.setPen(QColor(255, 255, 255))
        painter.setBrush(QColor(255, 255, 255))
        painter.drawRoundedRect(24, 18, 16, 24, 6, 6)
        
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = painter.pen()
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawArc(18, 28, 28, 24, 200 * 16, 140 * 16)
        
        painter.drawLine(32, 38, 32, 48)
        painter.drawLine(26, 48, 38, 48)
        
        painter.end()
        
        return QIcon(pixmap)
    
    def _create_menu(self):
        self._menu = QMenu()
        self._menu.setStyleSheet(get_menu_stylesheet(self._theme))
        
        self._toggle_action = QAction("Start Recording", self)
        self._toggle_action.triggered.connect(self._toggle_recording)
        self._menu.addAction(self._toggle_action)
        
        self._menu.addSeparator()
        
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self.show_window_requested.emit)
        self._menu.addAction(show_action)
        
        hide_action = QAction("Hide Window", self)
        hide_action.triggered.connect(self.hide_window_requested.emit)
        self._menu.addAction(hide_action)
        
        self._menu.addSeparator()
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.settings_requested.emit)
        self._menu.addAction(settings_action)
        
        history_action = QAction("History", self)
        history_action.triggered.connect(self.history_requested.emit)
        self._menu.addAction(history_action)

        self._profiles_menu = QMenu("Profiles", self._menu)
        self._menu.addMenu(self._profiles_menu)
        
        self._menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(quit_action)
        
        self.setContextMenu(self._menu)

    def set_profiles(self, profiles: list[tuple[str, str]], active_profile_id: str):
        self._profiles_menu.clear()
        for profile_id, profile_name in profiles:
            action = QAction(profile_name, self._profiles_menu)
            action.setCheckable(True)
            action.setChecked(profile_id == active_profile_id)
            action.triggered.connect(
                lambda checked, pid=profile_id: self.profile_selected.emit(pid)
            )
            self._profiles_menu.addAction(action)
    
    def _on_activated(self, reason):
        try:
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                self.show_window_requested.emit()
            elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
                self._toggle_recording()
        except Exception:
            pass
    
    def _toggle_recording(self):
        self._is_recording = not self._is_recording
        self._update_state()
        self.recording_toggled.emit(self._is_recording)
    
    def set_recording(self, recording: bool):
        self._is_recording = recording
        self._update_state()
    
    def set_state(self, state: str):
        self._state_change_requested.emit(state)
    
    def show_message(self, title: str, message: str, duration: int = 2000):
        self.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, duration)
    
    def _do_set_state(self, state: str):
        if state == "idle":
            self.setIcon(self._idle_icon)
        elif state == "recording":
            self.setIcon(self._recording_icon)
        elif state == "processing":
            self.setIcon(self._processing_icon)
        elif state == "error":
            self.setIcon(self._idle_icon)
    
    def _update_state(self):
        if self._is_recording:
            self._toggle_action.setText("Stop Recording")
            self.setIcon(self._recording_icon)
        else:
            self._toggle_action.setText("Start Recording")
            self.setIcon(self._idle_icon)

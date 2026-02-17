"""System tray icon for LocalVoice."""

from typing import Optional, Callable

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from PyQt6.QtCore import pyqtSignal, QObject, Qt


class TrayIcon(QSystemTrayIcon):
    show_window_requested = pyqtSignal()
    hide_window_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    recording_toggled = pyqtSignal(bool)
    _state_change_requested = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_recording = False
        self._create_icons()
        self._create_menu()
        
        self._state_change_requested.connect(self._do_set_state)
        
        self.activated.connect(self._on_activated)
        self.setIcon(self._idle_icon)
        self.setToolTip("LocalVoice - Ready")
    
    def _create_icons(self):
        self._idle_icon = self._create_icon(QColor(100, 100, 100))
        self._recording_icon = self._create_icon(QColor(220, 60, 60))
        self._processing_icon = self._create_icon(QColor(80, 130, 200))
    
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
        self._menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #444444;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #444444;
            }
            QMenu::separator {
                height: 1px;
                background: #444444;
                margin: 5px 10px;
            }
        """)
        
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
        
        self._menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(quit_action)
        
        self.setContextMenu(self._menu)
    
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
    
    def _do_set_state(self, state: str):
        if state == "idle":
            self.setIcon(self._idle_icon)
            self.setToolTip("LocalVoice - Ready")
        elif state == "recording":
            self.setIcon(self._recording_icon)
            self.setToolTip("LocalVoice - Recording...")
        elif state == "processing":
            self.setIcon(self._processing_icon)
            self.setToolTip("LocalVoice - Processing...")
        elif state == "error":
            self.setIcon(self._idle_icon)
            self.setToolTip("LocalVoice - Error")
    
    def _update_state(self):
        if self._is_recording:
            self._toggle_action.setText("Stop Recording")
            self.setIcon(self._recording_icon)
            self.setToolTip("LocalVoice - Recording...")
        else:
            self._toggle_action.setText("Start Recording")
            self.setIcon(self._idle_icon)
            self.setToolTip("LocalVoice - Ready")
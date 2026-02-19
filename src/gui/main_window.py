"""Main floating window UI for LocalVoice."""

from enum import Enum
from typing import Optional, Callable
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QFrame, QMenu, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QSize, Signal, QPropertyAnimation, QEasingCurve, QPoint, QRect
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QCursor, QIcon, QAction

from .themes import get_theme, get_menu_stylesheet


class AppState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    ERROR = "error"


class MicButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = AppState.IDLE
        self._pulse_value = 0
        self._pulse_direction = 1
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._animate_pulse)
        self._rotation_angle = 0
        self._rotation_timer = QTimer(self)
        self._rotation_timer.timeout.connect(self._animate_rotation)
        self._theme = "dark"
        
        self.setMinimumSize(40, 40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFlat(True)
    
    def set_theme(self, theme_name: str):
        self._theme = theme_name
        self.update()
    
    @property
    def state(self) -> AppState:
        return self._state
    
    @state.setter
    def state(self, value: AppState):
        self._state = value
        self.update()
        
        if value == AppState.RECORDING:
            self._pulse_timer.start(30)
            self._rotation_timer.stop()
        elif value == AppState.PROCESSING:
            self._pulse_timer.stop()
            self._rotation_timer.start(20)
        else:
            self._pulse_timer.stop()
            self._rotation_timer.stop()
    
    def _animate_pulse(self):
        self._pulse_value += 5 * self._pulse_direction
        if self._pulse_value >= 100:
            self._pulse_direction = -1
        elif self._pulse_value <= 0:
            self._pulse_direction = 1
        self.update()
    
    def _animate_rotation(self):
        self._rotation_angle = (self._rotation_angle + 5) % 360
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        center = rect.center()
        radius = min(rect.width(), rect.height()) // 2 - 5
        
        theme = get_theme(self._theme)
        
        if self._state == AppState.IDLE:
            bg_color = QColor(theme['mic_idle_bg'])
            border_color = QColor(theme['mic_idle_border'])
            icon_color = QColor(theme['mic_idle_icon'])
        elif self._state == AppState.RECORDING:
            pulse_factor = self._pulse_value / 100.0
            base_bg = QColor(theme['mic_recording_bg'])
            bg_color = QColor(
                int(base_bg.red() * (0.5 + 0.5 * pulse_factor)),
                int(base_bg.green() * pulse_factor),
                int(base_bg.blue() * pulse_factor)
            )
            border_color = QColor(theme['mic_recording_border'])
            icon_color = QColor(theme['mic_recording_icon'])
        elif self._state == AppState.PROCESSING:
            bg_color = QColor(theme['mic_processing_bg'])
            border_color = QColor(theme['mic_processing_border'])
            icon_color = QColor(theme['mic_processing_icon'])
        elif self._state == AppState.ERROR:
            bg_color = QColor(theme['mic_error_bg'])
            border_color = QColor(theme['mic_error_border'])
            icon_color = QColor(theme['mic_error_icon'])
        else:
            bg_color = QColor(theme['mic_idle_bg'])
            border_color = QColor(theme['mic_idle_border'])
            icon_color = QColor(theme['mic_idle_icon'])
        
        painter.setPen(QPen(border_color, 3))
        painter.setBrush(QBrush(bg_color))
        painter.drawEllipse(center, radius, radius)
        
        if self._state == AppState.PROCESSING:
            painter.save()
            painter.translate(center)
            painter.rotate(self._rotation_angle)
            
            pen = QPen(icon_color, 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            
            arc_radius = radius - 15
            for i in range(8):
                angle = i * 45
                length = 8 + (i % 3) * 4
                x1 = int(arc_radius * 0.7 * (1 if i % 2 == 0 else 0.9))
                painter.drawLine(
                    QPoint(x1, -length),
                    QPoint(x1, length)
                )
            
            painter.restore()
        else:
            self._draw_mic_icon(painter, center, icon_color, radius)
    
    def _draw_mic_icon(self, painter: QPainter, center, color: QColor, button_radius: int):
        painter.setPen(QPen(color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        mic_width = 16
        mic_height = 28
        mic_x = center.x() - mic_width // 2
        mic_y = center.y() - mic_height // 2 - 2
        
        painter.drawRoundedRect(mic_x, mic_y, mic_width, mic_height, 8, 8)
        
        arc_radius = button_radius - 20
        start_angle = 200 * 16
        span_angle = 140 * 16
        painter.drawArc(
            center.x() - arc_radius,
            center.y() - arc_radius // 2 + 8,
            arc_radius * 2,
            arc_radius,
            start_angle,
            span_angle
        )
        
        painter.drawLine(
            center.x() - 12, center.y() + 18,
            center.x() + 12, center.y() + 18
        )
        painter.drawLine(
            center.x(), center.y() + 8,
            center.x(), center.y() + 18
        )


class FloatingWindow(QWidget):
    recording_toggled = Signal(bool)
    settings_requested = Signal()
    history_requested = Signal()
    quit_requested = Signal()
    _state_change_requested = Signal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = AppState.IDLE
        self._drag_pos = None
        self._opacity = 0.95
        self._recording_start_time: Optional[datetime] = None
        self._duration_timer = QTimer(self)
        self._duration_timer.timeout.connect(self._update_duration_display)
        self._hotkey = "Caps Lock"
        self._hotkey_mode = "hold"
        self._profile_name = "Default"
        self._theme = "dark"
        
        self._state_change_requested.connect(self._do_set_state)
        
        self._init_ui()
    
    def _init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setFixedSize(100, 125)
        self.setWindowOpacity(self._opacity)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 10)
        layout.setSpacing(5)
        
        self.mic_button = MicButton(self)
        self.mic_button.clicked.connect(self._on_mic_clicked)
        self.mic_button.installEventFilter(self)
        layout.addWidget(self.mic_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self._duration_label = QLabel("00:00", self)
        self._duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._duration_label.hide()
        layout.addWidget(self._duration_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        self._update_duration_label_style()
        self._update_tooltip()
    
    def _on_mic_clicked(self):
        if self._state == AppState.IDLE:
            self.set_state(AppState.RECORDING)
            self.recording_toggled.emit(True)
        elif self._state == AppState.RECORDING:
            self.set_state(AppState.PROCESSING)
            self.recording_toggled.emit(False)
        elif self._state == AppState.ERROR:
            self.set_state(AppState.IDLE)
    
    def set_state(self, state: AppState):
        self._state_change_requested.emit(state)
    
    def _do_set_state(self, state: AppState):
        self._state = state
        self.mic_button.state = state
        self._update_tooltip()
        
        if state == AppState.RECORDING:
            self._recording_start_time = datetime.now()
            self._duration_label.setText("00:00")
            self._duration_label.show()
            self._duration_timer.start(1000)
        else:
            self._duration_timer.stop()
            self._duration_label.hide()
            self._recording_start_time = None
    
    def _update_duration_display(self):
        if self._recording_start_time is None:
            return
        
        elapsed = datetime.now() - self._recording_start_time
        total_seconds = int(elapsed.total_seconds())
        minutes, seconds = divmod(total_seconds, 60)
        
        if total_seconds >= 3600:
            hours, minutes = divmod(minutes, 60)
            self._duration_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        else:
            self._duration_label.setText(f"{minutes:02d}:{seconds:02d}")
    
    def get_state(self) -> AppState:
        return self._state
    
    def set_opacity(self, opacity: float):
        self._opacity = max(0.3, min(1.0, opacity))
        self.setWindowOpacity(self._opacity)
    
    def set_theme(self, theme_name: str):
        self._theme = theme_name
        self.mic_button.set_theme(theme_name)
        self._update_duration_label_style()
        self._update_tooltip()
    
    def _update_duration_label_style(self):
        theme = get_theme(self._theme)
        self._duration_label.setStyleSheet(f"""
            QLabel {{
                color: {theme['mic_recording_icon']};
                font-size: 12px;
                font-weight: bold;
                background-color: transparent;
            }}
        """)
    
    def set_hotkey_info(self, hotkey: str, mode: str):
        self._hotkey = self._format_hotkey(hotkey)
        self._hotkey_mode = mode
        self._update_tooltip()

    def set_profile_name(self, profile_name: str):
        self._profile_name = profile_name
        self._update_tooltip()
    
    def _format_hotkey(self, hotkey: str) -> str:
        return hotkey.replace('_', ' ').replace('+', '+').title()
    
    def _update_tooltip(self):
        mode_text = "Hold" if self._hotkey_mode == "hold" else "Toggle"
        state_text = self._state.value.capitalize()
        tooltip = f"LocalVoice - {state_text} [{self._hotkey} - {mode_text}] | Profile: {self._profile_name}"
        
        theme = get_theme(self._theme)
        self.setStyleSheet(f"""
            QToolTip {{
                color: {theme['text']};
                background-color: {theme['window_bg']};
                border: 1px solid {theme['border']};
                padding: 4px;
            }}
        """)
        self.setToolTip(tooltip)
        self.mic_button.setToolTip(tooltip)
    
    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(get_menu_stylesheet(self._theme))
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.settings_requested.emit)
        menu.addAction(settings_action)
        
        history_action = QAction("History", self)
        history_action.triggered.connect(self.history_requested.emit)
        menu.addAction(history_action)
        
        menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)
        
        menu.exec(self.mapToGlobal(pos))
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
    
    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
    
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_mic_clicked()
    
    def eventFilter(self, obj, event):
        if obj == self.mic_button:
            if event.type() in (event.Type.MouseButtonPress, event.Type.MouseMove, event.Type.MouseButtonRelease):
                if event.type() == event.Type.MouseButtonPress:
                    if event.button() == Qt.MouseButton.LeftButton:
                        self._drag_pos = event.globalPosition().toPoint() - self.pos()
                        return True
                elif event.type() == event.Type.MouseMove:
                    if self._drag_pos is not None:
                        self.move(event.globalPosition().toPoint() - self._drag_pos)
                        return True
                elif event.type() == event.Type.MouseButtonRelease:
                    if event.button() == Qt.MouseButton.LeftButton:
                        if self._drag_pos is not None:
                            self._drag_pos = None
                            return True
        return super().eventFilter(obj, event)

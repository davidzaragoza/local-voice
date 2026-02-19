"""Theme definitions and management for LocalVoice."""

from typing import Dict, Any
from PySide6.QtGui import QColor


THEMES: Dict[str, Dict[str, Any]] = {
    'dark': {
        'name': 'Dark',
        'window_bg': '#2d2d2d',
        'window_bg_alt': '#252525',
        'text': '#ffffff',
        'text_secondary': '#888888',
        'button_bg': '#3c3c3c',
        'button_hover': '#4a4a4a',
        'accent': '#5082c8',
        'border': '#444444',
        'mic_idle_bg': '#3c3c3c',
        'mic_idle_border': '#646464',
        'mic_idle_icon': '#c8c8c8',
        'mic_recording_bg': '#c83232',
        'mic_recording_border': '#dc5050',
        'mic_recording_icon': '#ff6464',
        'mic_processing_bg': '#325080',
        'mic_processing_border': '#5082c8',
        'mic_processing_icon': '#96c8ff',
        'mic_error_bg': '#502828',
        'mic_error_border': '#c85050',
        'mic_error_icon': '#ff6464',
        'tray_idle': '#646464',
        'tray_recording': '#dc3c3c',
        'tray_processing': '#5082c8',
        'menu_bg': '#2d2d2d',
        'menu_item_selected': '#444444',
        'input_bg': '#3c3c3c',
        'input_border': '#555555',
        'scrollbar': '#4a4a4a',
    },
    'light': {
        'name': 'Light',
        'window_bg': '#f5f5f5',
        'window_bg_alt': '#e8e8e8',
        'text': '#1a1a1a',
        'text_secondary': '#666666',
        'button_bg': '#e0e0e0',
        'button_hover': '#d0d0d0',
        'accent': '#4080c0',
        'border': '#c0c0c0',
        'mic_idle_bg': '#e0e0e0',
        'mic_idle_border': '#b0b0b0',
        'mic_idle_icon': '#505050',
        'mic_recording_bg': '#e85050',
        'mic_recording_border': '#c84040',
        'mic_recording_icon': '#ffffff',
        'mic_processing_bg': '#5090d0',
        'mic_processing_border': '#4080c0',
        'mic_processing_icon': '#ffffff',
        'mic_error_bg': '#e87070',
        'mic_error_border': '#d05050',
        'mic_error_icon': '#ffffff',
        'tray_idle': '#808080',
        'tray_recording': '#d04040',
        'tray_processing': '#4080c0',
        'menu_bg': '#f5f5f5',
        'menu_item_selected': '#e0e0e0',
        'input_bg': '#ffffff',
        'input_border': '#c0c0c0',
        'scrollbar': '#d0d0d0',
    }
}


def get_theme(name: str) -> Dict[str, Any]:
    return THEMES.get(name, THEMES['dark'])


def get_stylesheet(theme_name: str) -> str:
    theme = get_theme(theme_name)
    
    return f"""
        QWidget {{
            background-color: {theme['window_bg']};
            color: {theme['text']};
        }}
        
        QDialog {{
            background-color: {theme['window_bg']};
        }}
        
        QLabel {{
            color: {theme['text']};
            background-color: transparent;
        }}
        
        QPushButton {{
            background-color: {theme['button_bg']};
            color: {theme['text']};
            border: 1px solid {theme['border']};
            padding: 6px 12px;
            border-radius: 4px;
        }}
        
        QPushButton:hover {{
            background-color: {theme['button_hover']};
        }}
        
        QPushButton:pressed {{
            background-color: {theme['border']};
        }}
        
        QLineEdit {{
            background-color: {theme['input_bg']};
            color: {theme['text']};
            border: 1px solid {theme['input_border']};
            padding: 4px 8px;
            border-radius: 4px;
        }}
        
        QLineEdit:focus {{
            border: 1px solid {theme['accent']};
        }}
        
        QTextEdit {{
            background-color: {theme['input_bg']};
            color: {theme['text']};
            border: 1px solid {theme['input_border']};
            border-radius: 4px;
        }}
        
        QComboBox {{
            background-color: {theme['input_bg']};
            color: {theme['text']};
            border: 1px solid {theme['input_border']};
            padding: 4px 8px;
            border-radius: 4px;
        }}
        
        QComboBox:hover {{
            border: 1px solid {theme['accent']};
        }}
        
        QComboBox::drop-down {{
            border: none;
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {theme['window_bg']};
            color: {theme['text']};
            selection-background-color: {theme['accent']};
        }}
        
        QSpinBox {{
            background-color: {theme['input_bg']};
            color: {theme['text']};
            border: 1px solid {theme['input_border']};
            padding: 4px 8px;
            border-radius: 4px;
        }}
        
        QSpinBox:focus {{
            border: 1px solid {theme['accent']};
        }}
        
        QCheckBox {{
            color: {theme['text']};
            spacing: 8px;
        }}
        
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {theme['border']};
            border-radius: 3px;
            background-color: {theme['input_bg']};
        }}
        
        QCheckBox::indicator:checked {{
            background-color: {theme['accent']};
            border: 1px solid {theme['accent']};
        }}
        
        QRadioButton {{
            color: {theme['text']};
            spacing: 8px;
        }}
        
        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {theme['border']};
            border-radius: 8px;
            background-color: {theme['input_bg']};
        }}
        
        QRadioButton::indicator:checked {{
            background-color: {theme['accent']};
            border: 1px solid {theme['accent']};
        }}
        
        QGroupBox {{
            color: {theme['text']};
            border: 1px solid {theme['border']};
            border-radius: 4px;
            margin-top: 12px;
            padding-top: 8px;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }}
        
        QTabWidget::pane {{
            border: 1px solid {theme['border']};
            background-color: {theme['window_bg']};
        }}
        
        QTabBar::tab {{
            background-color: {theme['button_bg']};
            color: {theme['text']};
            padding: 8px 16px;
            border: 1px solid {theme['border']};
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {theme['window_bg']};
            border-bottom: 1px solid {theme['window_bg']};
        }}
        
        QTabBar::tab:hover:!selected {{
            background-color: {theme['button_hover']};
        }}
        
        QSlider::groove:horizontal {{
            background: {theme['border']};
            height: 6px;
            border-radius: 3px;
        }}
        
        QSlider::handle:horizontal {{
            background: {theme['accent']};
            width: 16px;
            height: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }}
        
        QMenu {{
            background-color: {theme['menu_bg']};
            color: {theme['text']};
            border: 1px solid {theme['border']};
            padding: 4px;
        }}
        
        QMenu::item {{
            padding: 6px 24px;
            border-radius: 4px;
        }}
        
        QMenu::item:selected {{
            background-color: {theme['menu_item_selected']};
        }}
        
        QMenu::separator {{
            height: 1px;
            background: {theme['border']};
            margin: 4px 8px;
        }}
        
        QListWidget {{
            background-color: {theme['input_bg']};
            color: {theme['text']};
            border: 1px solid {theme['input_border']};
            border-radius: 4px;
        }}
        
        QListWidget::item {{
            padding: 4px 8px;
        }}
        
        QListWidget::item:selected {{
            background-color: {theme['accent']};
            color: white;
        }}
        
        QListWidget::item:hover:!selected {{
            background-color: {theme['button_hover']};
        }}
        
        QScrollBar:vertical {{
            background: {theme['window_bg']};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background: {theme['scrollbar']};
            border-radius: 6px;
            min-height: 20px;
        }}
        
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        QToolTip {{
            background-color: {theme['window_bg']};
            color: {theme['text']};
            border: 1px solid {theme['border']};
            padding: 4px 8px;
            border-radius: 4px;
        }}
    """


def get_menu_stylesheet(theme_name: str) -> str:
    theme = get_theme(theme_name)
    
    return f"""
        QMenu {{
            background-color: {theme['menu_bg']};
            color: {theme['text']};
            border: 1px solid {theme['border']};
            padding: 5px;
        }}
        QMenu::item {{
            padding: 5px 20px;
            border-radius: 3px;
        }}
        QMenu::item:selected {{
            background-color: {theme['menu_item_selected']};
        }}
        QMenu::separator {{
            height: 1px;
            background: {theme['border']};
            margin: 5px 10px;
        }}
    """


def get_color(theme_name: str, key: str) -> QColor:
    theme = get_theme(theme_name)
    color_str = theme.get(key, '#000000')
    return QColor(color_str)

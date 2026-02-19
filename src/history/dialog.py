"""History dialog UI for LocalVoice."""

from datetime import datetime
from typing import Optional, List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QMessageBox, QFileDialog,
    QApplication
)
from PySide6.QtCore import Qt, Signal
from pathlib import Path

from .manager import HistoryManager, HistoryEntry


class HistoryDialog(QDialog):
    entry_copied = Signal(str)
    
    def __init__(self, history_manager: HistoryManager, parent=None):
        super().__init__(parent)
        self._history_manager = history_manager
        self._entries: List[HistoryEntry] = []
        self._current_search = ""
        self._active_profile_id: Optional[str] = None
        self._active_profile_name: str = "All Profiles"
        self._init_ui()
        self._load_entries()
    
    def _init_ui(self):
        self.setWindowTitle("Transcription History")
        self.setMinimumSize(600, 400)
        self.resize(700, 500)
        
        layout = QVBoxLayout(self)
        
        search_layout = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search transcriptions...")
        self._search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_input)
        layout.addLayout(search_layout)
        
        self._entries_list = QListWidget()
        self._entries_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._entries_list.itemDoubleClicked.connect(self._on_double_click)
        self._entries_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._entries_list)
        
        self._info_label = QLabel()
        self._info_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._info_label)
        
        button_layout = QHBoxLayout()
        
        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setEnabled(False)
        self._copy_btn.clicked.connect(self._copy_selected)
        button_layout.addWidget(self._copy_btn)
        
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._delete_selected)
        button_layout.addWidget(self._delete_btn)
        
        button_layout.addStretch()
        
        self._export_btn = QPushButton("Export")
        self._export_btn.clicked.connect(self._export_history)
        button_layout.addWidget(self._export_btn)
        
        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.clicked.connect(self._clear_all)
        button_layout.addWidget(self._clear_btn)
        
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self._close_btn)
        
        layout.addLayout(button_layout)
    
    def showEvent(self, event):
        super().showEvent(event)
        self._load_entries()
    
    def _load_entries(self):
        self._entries = self._history_manager.get_entries(
            limit=100,
            search=self._current_search if self._current_search else None,
            profile_id=self._active_profile_id
        )
        self._refresh_list()
    
    def _refresh_list(self):
        self._entries_list.clear()
        
        for entry in self._entries:
            timestamp_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            duration_str = ""
            if entry.duration:
                mins, secs = divmod(int(entry.duration), 60)
                duration_str = f" [{mins:02d}:{secs:02d}]"
            
            language_str = f" ({entry.language})" if entry.language else ""
            
            preview = entry.text[:100] + "..." if len(entry.text) > 100 else entry.text
            preview = preview.replace('\n', ' ')
            
            item_text = f"{timestamp_str}{duration_str}{language_str}\n{preview}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            self._entries_list.addItem(item)
        
        total = self._history_manager.get_count(
            search=self._current_search if self._current_search else None,
            profile_id=self._active_profile_id
        )
        self._info_label.setText(
            f"Profile: {self._active_profile_name} | Showing {len(self._entries)} of {total} entries"
        )
    
    def _on_search_changed(self, text: str):
        self._current_search = text.strip()
        self._load_entries()
    
    def _on_selection_changed(self):
        has_selection = len(self._entries_list.selectedItems()) > 0
        self._copy_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)
    
    def _get_selected_entry(self) -> Optional[HistoryEntry]:
        selected = self._entries_list.selectedItems()
        if not selected:
            return None
        entry_id = selected[0].data(Qt.ItemDataRole.UserRole)
        return self._history_manager.get_entry(entry_id)
    
    def _on_double_click(self, item: QListWidgetItem):
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        entry = self._history_manager.get_entry(entry_id)
        if entry:
            self._copy_to_clipboard(entry.text)
            self.entry_copied.emit(entry.text)
    
    def _copy_selected(self):
        entry = self._get_selected_entry()
        if entry:
            self._copy_to_clipboard(entry.text)
            self.entry_copied.emit(entry.text)
    
    def _copy_to_clipboard(self, text: str):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
    
    def _delete_selected(self):
        selected = self._entries_list.selectedItems()
        if not selected:
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Entry",
            "Are you sure you want to delete this entry?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            entry_id = selected[0].data(Qt.ItemDataRole.UserRole)
            self._history_manager.delete_entry(entry_id)
            self._load_entries()
    
    def _clear_all(self):
        reply = QMessageBox.question(
            self,
            "Clear All History",
            "Are you sure you want to delete all history entries?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._history_manager.clear_all()
            self._load_entries()
    
    def _export_history(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export History",
            "transcription_history.json",
            "JSON Files (*.json)"
        )
        
        if filepath:
            if self._history_manager.export_to_json(Path(filepath), profile_id=self._active_profile_id):
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"History exported to {filepath}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    "Failed to export history."
                )

    def set_active_profile(self, profile_id: str, profile_name: str):
        self._active_profile_id = profile_id
        self._active_profile_name = profile_name
        self._load_entries()

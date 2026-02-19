"""History management and persistence for LocalVoice."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class HistoryEntry:
    id: int
    timestamp: datetime
    text: str
    profile_id: str = "default"
    language: Optional[str] = None
    duration: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'text': self.text,
            'profile_id': self.profile_id,
            'language': self.language,
            'duration': self.duration,
        }


class HistoryManager:
    def __init__(self, max_entries: int = 500):
        self._data_dir = Path.home() / ".localvoice"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_dir / "history.db"
        self._max_entries = max_entries
        self._enabled = True
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    text TEXT NOT NULL,
                    profile_id TEXT NOT NULL DEFAULT 'default',
                    language TEXT,
                    duration REAL
                )
            ''')
            columns = [row[1] for row in conn.execute("PRAGMA table_info(history)").fetchall()]
            if "profile_id" not in columns:
                conn.execute("ALTER TABLE history ADD COLUMN profile_id TEXT NOT NULL DEFAULT 'default'")
                conn.execute("UPDATE history SET profile_id = 'default' WHERE profile_id IS NULL OR profile_id = ''")
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp ON history(timestamp DESC)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_profile_timestamp ON history(profile_id, timestamp DESC)
            ''')
            conn.commit()
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
    
    @property
    def max_entries(self) -> int:
        return self._max_entries
    
    @max_entries.setter
    def max_entries(self, value: int):
        self._max_entries = value
    
    def add_entry(
        self,
        text: str,
        profile_id: str = "default",
        language: Optional[str] = None,
        duration: Optional[float] = None
    ) -> Optional[int]:
        if not self._enabled or not text.strip():
            return None
        
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                'INSERT INTO history (timestamp, text, profile_id, language, duration) VALUES (?, ?, ?, ?, ?)',
                (timestamp, text, profile_id, language, duration)
            )
            conn.commit()
            entry_id = cursor.lastrowid
            
            self._cleanup_old_entries(conn)
            
            return entry_id
    
    def _cleanup_old_entries(self, conn):
        conn.execute('''
            DELETE FROM history WHERE id NOT IN (
                SELECT id FROM history ORDER BY timestamp DESC LIMIT ?
            )
        ''', (self._max_entries,))
    
    def get_entries(
        self,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
        profile_id: Optional[str] = None
    ) -> List[HistoryEntry]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if search:
                if profile_id:
                    cursor = conn.execute(
                        '''
                        SELECT id, timestamp, text, profile_id, language, duration
                        FROM history
                        WHERE text LIKE ? AND profile_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ? OFFSET ?
                        ''',
                        (f'%{search}%', profile_id, limit, offset)
                    )
                else:
                    cursor = conn.execute(
                        '''
                        SELECT id, timestamp, text, profile_id, language, duration
                        FROM history
                        WHERE text LIKE ?
                        ORDER BY timestamp DESC
                        LIMIT ? OFFSET ?
                        ''',
                        (f'%{search}%', limit, offset)
                    )
            else:
                if profile_id:
                    cursor = conn.execute(
                        '''
                        SELECT id, timestamp, text, profile_id, language, duration
                        FROM history
                        WHERE profile_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ? OFFSET ?
                        ''',
                        (profile_id, limit, offset)
                    )
                else:
                    cursor = conn.execute(
                        '''
                        SELECT id, timestamp, text, profile_id, language, duration
                        FROM history
                        ORDER BY timestamp DESC
                        LIMIT ? OFFSET ?
                        ''',
                        (limit, offset)
                    )
            
            entries = []
            for row in cursor.fetchall():
                entries.append(HistoryEntry(
                    id=row['id'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    text=row['text'],
                    profile_id=row['profile_id'] or "default",
                    language=row['language'],
                    duration=row['duration']
                ))
            
            return entries
    
    def get_entry(self, entry_id: int) -> Optional[HistoryEntry]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT id, timestamp, text, profile_id, language, duration FROM history WHERE id = ?',
                (entry_id,)
            )
            row = cursor.fetchone()
            if row:
                return HistoryEntry(
                    id=row['id'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    text=row['text'],
                    profile_id=row['profile_id'] or "default",
                    language=row['language'],
                    duration=row['duration']
                )
            return None
    
    def delete_entry(self, entry_id: int) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute('DELETE FROM history WHERE id = ?', (entry_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def clear_all(self) -> int:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute('DELETE FROM history')
            conn.commit()
            return cursor.rowcount
    
    def get_count(self, search: Optional[str] = None, profile_id: Optional[str] = None) -> int:
        with sqlite3.connect(self._db_path) as conn:
            if search:
                if profile_id:
                    cursor = conn.execute(
                        'SELECT COUNT(*) FROM history WHERE text LIKE ? AND profile_id = ?',
                        (f'%{search}%', profile_id)
                    )
                else:
                    cursor = conn.execute(
                        'SELECT COUNT(*) FROM history WHERE text LIKE ?',
                        (f'%{search}%',)
                    )
            else:
                if profile_id:
                    cursor = conn.execute('SELECT COUNT(*) FROM history WHERE profile_id = ?', (profile_id,))
                else:
                    cursor = conn.execute('SELECT COUNT(*) FROM history')
            return cursor.fetchone()[0]
    
    def export_to_json(self, filepath: Path, profile_id: Optional[str] = None) -> bool:
        try:
            entries = self.get_entries(limit=self._max_entries, profile_id=profile_id)
            data = [entry.to_dict() for entry in entries]
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

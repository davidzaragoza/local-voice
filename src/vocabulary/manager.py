"""Vocabulary management for custom words and substitutions."""

import re
from typing import Optional, List, Dict


class VocabularyManager:
    MAX_WORDS = 50
    
    def __init__(self):
        self._words: List[str] = []
        self._substitutions: Dict[str, str] = {}
    
    @property
    def words(self) -> List[str]:
        return self._words.copy()
    
    @property
    def substitutions(self) -> Dict[str, str]:
        return self._substitutions.copy()
    
    def add_word(self, word: str) -> bool:
        word = word.strip()
        if not word:
            return False
        if word in self._words:
            return False
        if len(self._words) >= self.MAX_WORDS:
            return False
        self._words.append(word)
        return True
    
    def remove_word(self, word: str) -> bool:
        word = word.strip()
        if word in self._words:
            self._words.remove(word)
            return True
        return False
    
    def set_words(self, words: List[str]) -> bool:
        unique_words = []
        seen = set()
        for w in words:
            w = w.strip()
            if w and w not in seen:
                unique_words.append(w)
                seen.add(w)
        self._words = unique_words[:self.MAX_WORDS]
        return True
    
    def add_substitution(self, source: str, target: str) -> bool:
        source = source.strip()
        target = target.strip()
        if not source or not target:
            return False
        self._substitutions[source] = target
        return True
    
    def remove_substitution(self, source: str) -> bool:
        source = source.strip()
        if source in self._substitutions:
            del self._substitutions[source]
            return True
        return False
    
    def set_substitutions(self, substitutions: Dict[str, str]) -> bool:
        self._substitutions = substitutions.copy()
        return True
    
    def get_initial_prompt(self) -> Optional[str]:
        if not self._words:
            return None
        words_str = ', '.join(self._words[:self.MAX_WORDS])
        return f"Context: words: {words_str}."
    
    def apply_substitutions(self, text: str) -> str:
        if not self._substitutions:
            return text
        
        result = text
        for source, target in self._substitutions.items():
            pattern = re.compile(re.escape(source), re.IGNORECASE)
            result = pattern.sub(target, result)
        
        return result
    
    def clear_all(self):
        self._words = []
        self._substitutions = {}

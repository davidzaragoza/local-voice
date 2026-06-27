"""Vocabulary management for custom words and substitutions."""

import re
from typing import Optional, List, Dict


class VocabularyManager:
    MAX_WORDS = 50
    
    def __init__(self):
        self._words: List[str] = []
        self._substitutions: Dict[str, str] = {}
        self._compiled_pattern: Optional[re.Pattern] = None
        self._lookup: Dict[str, str] = {}
    
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
        self._invalidate_cache()
        return True

    def remove_substitution(self, source: str) -> bool:
        source = source.strip()
        if source in self._substitutions:
            del self._substitutions[source]
            self._invalidate_cache()
            return True
        return False

    def set_substitutions(self, substitutions: Dict[str, str]) -> bool:
        # Validate/coerce so a hand-edited or corrupt settings.json (non-str
        # keys/values, empty/whitespace keys) can't raise inside re at
        # transcription time.
        cleaned: Dict[str, str] = {}
        if isinstance(substitutions, dict):
            for source, target in substitutions.items():
                if not isinstance(source, str) or not isinstance(target, str):
                    continue
                source = source.strip()
                target = target.strip()
                if not source or not target:
                    continue
                cleaned[source] = target
        self._substitutions = cleaned
        self._invalidate_cache()
        return True

    def _invalidate_cache(self):
        self._compiled_pattern = None
        self._lookup = {}

    def _build_cache(self):
        # Build a single alternation regex so each source is matched only
        # against the original text (no cascade) in one pass. Longer sources
        # first so they take precedence over shorter overlapping ones.
        self._lookup = {source.lower(): target for source, target in self._substitutions.items()}
        sources = sorted(self._substitutions.keys(), key=len, reverse=True)
        pattern_str = '|'.join(re.escape(s) for s in sources)
        self._compiled_pattern = re.compile(pattern_str, re.IGNORECASE)
    
    def get_initial_prompt(self) -> Optional[str]:
        if not self._words:
            return None
        words_str = ', '.join(self._words[:self.MAX_WORDS])
        return f"Context: words: {words_str}."
    
    def apply_substitutions(self, text: str) -> str:
        if not self._substitutions:
            return text

        if self._compiled_pattern is None:
            self._build_cache()

        def _replace(match: re.Match) -> str:
            return self._lookup.get(match.group(0).lower(), match.group(0))

        return self._compiled_pattern.sub(_replace, text)

    def clear_all(self):
        self._words = []
        self._substitutions = {}
        self._invalidate_cache()

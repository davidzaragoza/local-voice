"""Profile-aware settings management with legacy migration support."""

import json
import logging
import os
import re
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProfileManager:
    VERSION = 2

    GLOBAL_KEYS = {"start_minimized", "window_opacity", "theme"}

    PROFILE_KEYS = {
        "model_size",
        "language",
        "translate_to_english",
        "hotkey",
        "hotkey_mode",
        "injection_method",
        "device",
        "typing_delay",
        "add_trailing_space",
        "preserve_clipboard",
        "input_device",
        "enable_sounds",
        "enable_history",
        "history_max_entries",
        "vocabulary_words",
        "vocabulary_substitutions",
        "copy_only",
    }

    # Expected python type per key plus optional numeric clamp (min, max).
    # Values that don't match the expected type are dropped so the default is
    # kept, protecting against hand-edited or corrupt settings.json.
    _VALUE_SPEC = {
        "start_minimized": {"type": bool},
        "window_opacity": {"type": int, "min": 30, "max": 100},
        "theme": {"type": str},
        "model_size": {"type": str},
        "language": {"type": str},
        "translate_to_english": {"type": bool},
        "hotkey": {"type": str},
        "hotkey_mode": {"type": str},
        "injection_method": {"type": str},
        "device": {"type": str},
        "typing_delay": {"type": int, "min": 0, "max": 1000},
        "add_trailing_space": {"type": bool},
        "preserve_clipboard": {"type": bool},
        "input_device": {"type": int, "min": 0, "allow_none": True},
        "enable_sounds": {"type": bool},
        "enable_history": {"type": bool},
        "history_max_entries": {"type": int, "min": 1, "max": 100000},
        "vocabulary_words": {"type": list},
        "vocabulary_substitutions": {"type": dict},
        "copy_only": {"type": bool},
    }

    @classmethod
    def _coerce_value(cls, key: str, value: Any):
        """Validate/clamp a setting value.

        Returns (is_valid, coerced_value). When is_valid is False the caller
        should keep the existing default instead of the incoming value.
        """
        spec = cls._VALUE_SPEC.get(key)
        if spec is None:
            return True, value

        if value is None:
            return (True, None) if spec.get("allow_none") else (False, None)

        expected = spec["type"]
        # bool is a subclass of int; guard so a bool isn't accepted as int and
        # an int (e.g. 0/1) isn't silently accepted as bool.
        if expected is int:
            if isinstance(value, bool) or not isinstance(value, int):
                return False, None
        elif not isinstance(value, expected):
            return False, None

        if expected is int:
            if "min" in spec:
                value = max(spec["min"], value)
            if "max" in spec:
                value = min(spec["max"], value)
        return True, value

    def __init__(self):
        self._settings_file = Path(__file__).parent.parent.parent / "config" / "settings.json"
        self._state = self._default_state()
        self._load()

    def _default_global_settings(self) -> Dict[str, Any]:
        return {
            "start_minimized": False,
            "window_opacity": 95,
            "theme": "dark",
        }

    def _default_profile_settings(self) -> Dict[str, Any]:
        return {
            "model_size": "base",
            "language": "auto",
            "translate_to_english": False,
            "hotkey": "caps_lock",
            "hotkey_mode": "hold",
            "injection_method": "clipboard",
            "device": "auto",
            "typing_delay": 10,
            "add_trailing_space": True,
            "preserve_clipboard": True,
            "input_device": None,
            "enable_sounds": False,
            "enable_history": True,
            "history_max_entries": 500,
            "vocabulary_words": [],
            "vocabulary_substitutions": {},
            "copy_only": False,
        }

    def _default_state(self) -> Dict[str, Any]:
        return {
            "version": self.VERSION,
            "active_profile_id": "default",
            "global": self._default_global_settings(),
            "profiles": [
                {
                    "id": "default",
                    "name": "Default",
                    "settings": self._default_profile_settings(),
                }
            ],
        }

    def _load(self):
        if not self._settings_file.exists():
            self._save()
            return

        try:
            with open(self._settings_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except Exception as e:
            # Preserve the unreadable file so the user can recover it manually
            # instead of silently destroying their profiles/settings.
            logger.error("Failed to read settings file, backing up and resetting: %s", e)
            self._backup_corrupt_settings()
            self._state = self._default_state()
            self._save()
            return

        if self._is_legacy_settings(loaded):
            self._state = self._migrate_legacy(loaded)
            self._save()
            return

        self._state = self._normalize_state(loaded)
        self._save()

    def _save(self):
        self._settings_file.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file then atomically replace, so a crash mid-write
        # can never leave a truncated/corrupt settings.json behind.
        tmp_path = self._settings_file.with_suffix(self._settings_file.suffix + ".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._settings_file)
        except Exception as e:
            logger.error("Failed to save settings file: %s", e)
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass

    def _backup_corrupt_settings(self):
        try:
            backup_path = self._settings_file.with_name(
                f"{self._settings_file.name}.corrupt-{int(time.time())}"
            )
            os.replace(self._settings_file, backup_path)
            logger.warning("Backed up corrupt settings to %s", backup_path)
        except Exception as e:
            logger.error("Could not back up corrupt settings file: %s", e)

    def _is_legacy_settings(self, data: Dict[str, Any]) -> bool:
        return "profiles" not in data or "global" not in data

    def _migrate_legacy(self, legacy: Dict[str, Any]) -> Dict[str, Any]:
        global_settings = self._default_global_settings()
        profile_settings = self._default_profile_settings()

        for key, value in legacy.items():
            if key in self.GLOBAL_KEYS:
                global_settings[key] = value
            elif key in self.PROFILE_KEYS:
                profile_settings[key] = value

        return {
            "version": self.VERSION,
            "active_profile_id": "default",
            "global": global_settings,
            "profiles": [
                {
                    "id": "default",
                    "name": "Default",
                    "settings": profile_settings,
                }
            ],
        }

    def _normalize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._default_state()
        normalized["version"] = self.VERSION

        loaded_global = state.get("global", {})
        if isinstance(loaded_global, dict):
            for key in self.GLOBAL_KEYS:
                if key in loaded_global:
                    valid, value = self._coerce_value(key, loaded_global[key])
                    if valid:
                        normalized["global"][key] = value

        loaded_profiles = state.get("profiles", [])
        profiles: List[Dict[str, Any]] = []
        used_ids = set()

        if isinstance(loaded_profiles, list):
            for i, profile in enumerate(loaded_profiles):
                if not isinstance(profile, dict):
                    continue
                profile_id = str(profile.get("id") or "").strip()
                profile_name = str(profile.get("name") or "").strip()
                profile_settings = profile.get("settings", {})

                if not profile_id:
                    profile_id = self._generate_profile_id(profile_name or f"profile_{i + 1}", used_ids)
                if profile_id in used_ids:
                    profile_id = self._generate_profile_id(profile_id, used_ids)
                used_ids.add(profile_id)

                if not profile_name:
                    profile_name = f"Profile {i + 1}"

                settings = self._default_profile_settings()
                if isinstance(profile_settings, dict):
                    for key in self.PROFILE_KEYS:
                        if key in profile_settings:
                            valid, value = self._coerce_value(key, profile_settings[key])
                            if valid:
                                settings[key] = value

                profiles.append(
                    {
                        "id": profile_id,
                        "name": profile_name,
                        "settings": settings,
                    }
                )

        if not profiles:
            profiles = normalized["profiles"]

        normalized["profiles"] = profiles

        requested_active_id = str(state.get("active_profile_id", "")).strip()
        active_id = profiles[0]["id"]
        if requested_active_id and any(p["id"] == requested_active_id for p in profiles):
            active_id = requested_active_id
        normalized["active_profile_id"] = active_id

        return normalized

    def _generate_profile_id(self, name: str, existing_ids: set[str]) -> str:
        base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "profile"
        candidate = base
        suffix = 2
        while candidate in existing_ids:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def _find_profile_index(self, profile_id: str) -> int:
        for i, profile in enumerate(self._state["profiles"]):
            if profile["id"] == profile_id:
                return i
        return -1

    def get_state(self) -> Dict[str, Any]:
        return deepcopy(self._state)

    def save_state(self, state: Dict[str, Any]):
        self._state = self._normalize_state(state)
        self._save()

    def get_global_settings(self) -> Dict[str, Any]:
        return deepcopy(self._state["global"])

    def get_profiles(self) -> List[Dict[str, Any]]:
        return deepcopy(self._state["profiles"])

    def get_active_profile(self) -> Dict[str, Any]:
        active_id = self._state["active_profile_id"]
        index = self._find_profile_index(active_id)
        if index == -1:
            profile = self._state["profiles"][0]
            self._state["active_profile_id"] = profile["id"]
            self._save()
            return deepcopy(profile)
        return deepcopy(self._state["profiles"][index])

    def get_active_profile_settings(self) -> Dict[str, Any]:
        return deepcopy(self.get_active_profile()["settings"])

    def get_active_profile_id(self) -> str:
        return self._state["active_profile_id"]

    def set_active_profile(self, profile_id: str) -> bool:
        if self._find_profile_index(profile_id) == -1:
            return False
        self._state["active_profile_id"] = profile_id
        self._save()
        return True

    def save_global_settings(self, settings: Dict[str, Any]):
        for key in self.GLOBAL_KEYS:
            if key in settings:
                self._state["global"][key] = settings[key]
        self._save()

    def save_active_profile_settings(self, settings: Dict[str, Any]):
        active_id = self._state["active_profile_id"]
        index = self._find_profile_index(active_id)
        if index == -1:
            return
        for key in self.PROFILE_KEYS:
            if key in settings:
                self._state["profiles"][index]["settings"][key] = settings[key]
        self._save()

    def create_profile(self, name: str, base_settings: Optional[Dict[str, Any]] = None) -> str:
        existing_ids = {p["id"] for p in self._state["profiles"]}
        profile_id = self._generate_profile_id(name, existing_ids)
        settings = self._default_profile_settings()
        source = base_settings or self.get_active_profile_settings()
        for key in self.PROFILE_KEYS:
            if key in source:
                settings[key] = source[key]

        self._state["profiles"].append(
            {
                "id": profile_id,
                "name": name,
                "settings": settings,
            }
        )
        self._state["active_profile_id"] = profile_id
        self._save()
        return profile_id

    def rename_profile(self, profile_id: str, new_name: str) -> bool:
        index = self._find_profile_index(profile_id)
        if index == -1:
            return False
        self._state["profiles"][index]["name"] = new_name
        self._save()
        return True

    def delete_profile(self, profile_id: str) -> bool:
        if len(self._state["profiles"]) <= 1:
            return False
        index = self._find_profile_index(profile_id)
        if index == -1:
            return False

        was_active = self._state["active_profile_id"] == profile_id
        del self._state["profiles"][index]

        if was_active:
            self._state["active_profile_id"] = self._state["profiles"][0]["id"]

        self._save()
        return True

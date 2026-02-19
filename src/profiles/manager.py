"""Profile-aware settings management with legacy migration support."""

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional


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
        except Exception:
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
        with open(self._settings_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=4, ensure_ascii=False)

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
                    normalized["global"][key] = loaded_global[key]

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
                            settings[key] = profile_settings[key]

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

# src/preferences.py
import json
from pathlib import Path
from common.logging import Logger, NullLogger


class PreferencesManager:
    """Manages user preferences stored in DATA_ROOT/preferences.json

    Handles creator settings like default name and gift flow preferences.
    """

    def __init__(self, data_root: Path, logger: Logger | None = None):
        """Initialize the PreferencesManager.

        Args:
            data_root: Path to the data root directory
            logger: Optional logger instance
        """
        self._logger: Logger = logger or NullLogger()
        self.preferences_path: Path = data_root / "preferences.json"
        self._ensure_preferences_file()

    def _ensure_preferences_file(self) -> None:
        """Create preferences file with defaults if it doesn't exist."""
        if not self.preferences_path.exists():
            default_preferences = {
                "creator_name": "",
                "default_gift_flow_enabled": False,
                "default_show_tracklist": True,
            }
            self._save_preferences(default_preferences)
            self._logger.info(f"Created default preferences at {self.preferences_path}")

    def _save_preferences(self, preferences: dict) -> None:
        """Save preferences to disk.

        Args:
            preferences: Dictionary of preferences to save
        """
        try:
            with open(self.preferences_path, "w", encoding="utf-8") as f:
                json.dump(preferences, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._logger.error(f"Failed to save preferences: {e}")
            raise

    def get_preferences(self) -> dict:
        """Get all user preferences.

        Returns:
            Dictionary containing all preferences
        """
        try:
            with open(self.preferences_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self._logger.error(f"Failed to load preferences: {e}")
            # Return defaults if file is corrupted
            return {
                "creator_name": "",
                "default_gift_flow_enabled": False,
                "default_show_tracklist": True,
            }

    def get_creator_name(self) -> str:
        """Get the stored creator name.

        Returns:
            Creator name string (may be empty)
        """
        prefs = self.get_preferences()
        return prefs.get("creator_name", "")

    def set_creator_name(self, name: str) -> None:
        """Set the creator name preference.

        Args:
            name: Creator name to store
        """
        prefs = self.get_preferences()
        prefs["creator_name"] = name.strip()
        self._save_preferences(prefs)
        self._logger.info(f"Updated creator name to: {name}")

    def get_default_gift_flow_enabled(self) -> bool:
        """Get the default gift flow enabled setting.

        Returns:
            Whether gift flow should be enabled by default
        """
        prefs = self.get_preferences()
        return prefs.get("default_gift_flow_enabled", False)

    def set_default_gift_flow_enabled(self, enabled: bool) -> None:
        """Set the default gift flow enabled preference.

        Args:
            enabled: Whether to enable gift flow by default
        """
        prefs = self.get_preferences()
        prefs["default_gift_flow_enabled"] = enabled
        self._save_preferences(prefs)
        self._logger.info(f"Updated default gift flow enabled to: {enabled}")

    def get_default_show_tracklist(self) -> bool:
        """Get the default show tracklist setting.

        Returns:
            Whether tracklist should be shown after completion by default
        """
        prefs = self.get_preferences()
        return prefs.get("default_show_tracklist", True)

    def set_default_show_tracklist(self, show: bool) -> None:
        """Set the default show tracklist preference.

        Args:
            show: Whether to show tracklist after completion by default
        """
        prefs = self.get_preferences()
        prefs["default_show_tracklist"] = show
        self._save_preferences(prefs)
        self._logger.info(f"Updated default show tracklist to: {show}")

    def update_preferences(self, updates: dict) -> dict:
        """Update multiple preferences at once.

        Args:
            updates: Dictionary of preference keys and values to update

        Returns:
            Updated preferences dictionary
        """
        prefs = self.get_preferences()

        # Only update known preference keys
        allowed_keys = {
            "creator_name",
            "default_gift_flow_enabled",
            "default_show_tracklist",
        }

        for key, value in updates.items():
            if key in allowed_keys:
                prefs[key] = value
            else:
                self._logger.warning(f"Ignoring unknown preference key: {key}")

        self._save_preferences(prefs)
        self._logger.info(f"Updated preferences: {list(updates.keys())}")

        return prefs

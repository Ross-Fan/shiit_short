"""Configuration loader module."""

import os
import yaml
from pathlib import Path
from typing import Any, Dict


class Config:
    """Configuration manager for the short monitoring system."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize configuration loader.

        Args:
            config_path: Path to the YAML configuration file.
        """
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}

        # Override with environment variables if present
        self._load_env_overrides()

    def _load_env_overrides(self) -> None:
        """Load configuration overrides from environment variables."""
        env_mappings = {
            "BINANCE_API_KEY": ("api", "binance", "api_key"),
            "BINANCE_SECRET_KEY": ("api", "binance", "secret_key"),
            "BINANCE_TESTNET": ("api", "binance", "testnet"),
        }

        for env_key, config_path in env_mappings.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                self._set_nested(self._config, config_path, env_value)

    def _set_nested(self, data: Dict, keys: tuple, value: Any) -> None:
        """Set a nested dictionary value using a tuple of keys."""
        for key in keys[:-1]:
            if key not in data:
                data[key] = {}
            data = data[key]
        data[keys[-1]] = value

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Args:
            *keys: Nested keys to access the value (e.g., "monitor", "interval_check")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get an entire configuration section.

        Args:
            section: Section name

        Returns:
            Section dictionary or empty dict if not found
        """
        return self._config.get(section, {})

    @property
    def raw(self) -> Dict[str, Any]:
        """Get raw configuration dictionary."""
        return self._config

    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()

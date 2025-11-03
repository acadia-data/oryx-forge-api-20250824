"""Configuration Service for managing application settings."""

import sys
from pathlib import Path
from typing import Optional, Dict
from configobj import ConfigObj
from loguru import logger


class ConfigService:
    """
    Service class for managing application configuration.

    Handles reading and writing to .oryxforge.cfg file with support for
    sections and key-value pairs.
    """

    def __init__(self, working_dir: Optional[str] = None):
        """
        Initialize configuration service.

        Args:
            working_dir: Working directory where config file is located
                        (if None, uses ProjectContext.get() which falls back to current directory)
        """
        if working_dir is None:
            from .env_config import ProjectContext
            self.working_dir = Path(ProjectContext.get())
        else:
            self.working_dir = Path(working_dir)
        self.config_file = self.working_dir / '.oryxforge.cfg'

    def _load_config(self) -> ConfigObj:
        """
        Load configuration file.

        Returns:
            ConfigObj: Configuration object
        """
        config = ConfigObj()
        if self.config_file.exists():
            config = ConfigObj(str(self.config_file))
        return config

    def _save_config(self, config: ConfigObj) -> None:
        """
        Save configuration file.

        Args:
            config: Configuration object to save
        """
        config.filename = str(self.config_file)
        config.write()

    def get(self, section: str, key: str) -> Optional[str]:
        """
        Get a configuration value.

        Args:
            section: Configuration section name
            key: Configuration key within section

        Returns:
            Optional[str]: Configuration value or None if not found
        """
        if not self.config_file.exists():
            return None

        config = self._load_config()
        section_data = config.get(section, {})
        return section_data.get(key)

    def set(self, section: str, key: str, value: str) -> None:
        """
        Set a configuration value.

        Args:
            section: Configuration section name
            key: Configuration key within section
            value: Configuration value to set
        """
        config = self._load_config()
        if section not in config:
            config[section] = {}
        config[section][key] = value
        self._save_config(config)
        logger.debug(f"Config updated: [{section}] {key} = {value}")

    def get_all(self, section: str) -> Dict[str, str]:
        """
        Get all key-value pairs from a configuration section.

        Args:
            section: Configuration section name

        Returns:
            Dict[str, str]: Dictionary of configuration values (empty dict if section doesn't exist)
        """
        if not self.config_file.exists():
            return {}

        config = self._load_config()
        return dict(config.get(section, {}))

    def validate_mount_point(self, mount_point: str) -> Path:
        """
        Validate and normalize mount point path.

        Args:
            mount_point: Mount point path to validate

        Returns:
            Path: Normalized Path object

        Raises:
            ValueError: If mount point format is invalid
        """
        # Convert to Path object for normalization
        path = Path(mount_point)

        # Validate format based on platform
        if sys.platform == 'win32':
            # Windows: Check for drive letter or UNC path
            path_str = str(path)
            is_absolute = path.is_absolute()
            is_unc = path_str.startswith(r'\\') or path_str.startswith('//')

            if not (is_absolute or is_unc):
                raise ValueError(
                    f"Windows mount point must be absolute with drive letter (e.g., 'D:\\data') "
                    f"or UNC path (e.g., '\\\\\\\\server\\\\share'). Got: {mount_point}"
                )
        else:
            # Unix: Must be absolute
            if not path.is_absolute():
                raise ValueError(
                    f"Mount point must be an absolute path (e.g., '/mnt/data'). Got: {mount_point}"
                )

        return path

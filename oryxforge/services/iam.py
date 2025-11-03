"""Identity and Access Management (IAM) service for OryxForge.

Manages user credentials and profile configuration.
"""

from pathlib import Path
from typing import Dict, Optional
from configobj import ConfigObj
from loguru import logger


class CredentialsManager:
    """
    Manages user credentials and profile configuration.

    Stores user_id and project_id in a .oryxforge.cfg file in the working directory.
    """

    def __init__(self, working_dir: Optional[str] = None):
        """
        Initialize CredentialsManager.

        Args:
            working_dir: Working directory where config file is located
                        (if None, uses ProjectContext.get() which falls back to current directory)
        """
        if working_dir is None:
            from .env_config import ProjectContext
            self.working_dir = Path(ProjectContext.get())
        else:
            self.working_dir = Path(working_dir)

    @property
    def config_file(self) -> Path:
        """Get configuration file path."""
        return self.working_dir / '.oryxforge.cfg'

    def set_profile(self, user_id: str, project_id: str) -> None:
        """
        Set user profile (user_id and project_id) in configuration.

        Args:
            user_id: User ID to store
            project_id: Project ID to store
        """
        # Read existing config or create new
        config = ConfigObj()
        if self.config_file.exists():
            config = ConfigObj(str(self.config_file))

        # Set profile config
        if 'profile' not in config:
            config['profile'] = {}
        config['profile']['user_id'] = user_id
        config['profile']['project_id'] = project_id

        # Write config
        config.filename = str(self.config_file)
        config.write()

        logger.success(f"Profile set: user_id={user_id}, project_id={project_id}")

    def get_profile(self) -> Dict[str, str]:
        """
        Get current profile (user_id and project_id) from configuration.

        Returns:
            Dict with 'user_id' and 'project_id' keys

        Raises:
            ValueError: If profile is not configured
        """
        if not self.config_file.exists():
            raise ValueError(
                "No profile configured. Set profile with:\n"
                "  oryxforge admin profile set --userid <userid> --projectid <projectid>\n"
                "Or use CredentialsManager.set_profile(user_id, project_id)"
            )

        config = ConfigObj(str(self.config_file))
        profile = config.get('profile', {})

        if 'user_id' not in profile or 'project_id' not in profile:
            raise ValueError(
                "Incomplete profile configuration. Set profile with:\n"
                "  oryxforge admin profile set --userid <userid> --projectid <projectid>\n"
                "Or use CredentialsManager.set_profile(user_id, project_id)"
            )

        return {
            'user_id': profile['user_id'],
            'project_id': profile['project_id']
        }

    def clear_profile(self) -> None:
        """
        Clear profile configuration.

        Removes the profile section from configuration file.
        """
        if not self.config_file.exists():
            logger.info("No profile to clear")
            return

        config = ConfigObj(str(self.config_file))
        if 'profile' in config:
            del config['profile']
            config.filename = str(self.config_file)
            config.write()
            logger.success("Profile cleared")
        else:
            logger.info("No profile to clear")

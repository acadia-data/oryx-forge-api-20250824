"""Environment-aware configuration for OryxForge with zero-parameter services."""

import os
import sys
from pathlib import Path
from contextvars import ContextVar
from typing import Optional
from loguru import logger


# Thread-safe context variable for project working directory
_project_context: ContextVar[Optional[str]] = ContextVar('project_context', default=None)


class ProjectContext:
    """
    Manages project context using thread-local storage.

    Allows services to access project configuration without parameters.
    All configuration is stored in a single .oryxforge.cfg file.
    """

    @staticmethod
    def is_api_mode() -> bool:
        """
        Detect if running in API mode.

        Returns:
            True if running in GCP or local API mode
        """
        return os.environ.get('GOOGLE_CLOUD_PROJECT') is not None or \
               'uvicorn' in sys.modules or \
               os.environ.get('FASTAPI_ENV') is not None

    @staticmethod
    def set(user_id: str, project_id: str) -> str:
        """
        Set the current project context.

        After calling this, all services can find their configuration
        without any parameters.

        Args:
            user_id: User UUID
            project_id: Project UUID

        Returns:
            str: Working directory that was set
        """
        # Determine working directory based on environment
        if ProjectContext.is_api_mode():
            if os.environ.get('GOOGLE_CLOUD_PROJECT'):
                # GCP production
                working_dir = f"/tmp/{user_id}/{project_id}"
            else:
                # Local API development
                api_base = os.environ.get('ORYX_MOUNT_ROOT', '.')
                working_dir = f"{api_base}/mnt/projects/{user_id}/{project_id}"
        else:
            # CLI mode - use current directory
            working_dir = str(Path.cwd())

        # Create directory
        Path(working_dir).mkdir(parents=True, exist_ok=True)

        # Write configuration file
        ProjectContext._init_config(user_id, project_id, working_dir)

        # Set context variable
        _project_context.set(working_dir)

        logger.debug(f"Set project context: {working_dir}")
        return working_dir

    @staticmethod
    def get() -> str:
        """
        Get the current project working directory.

        Returns:
            str: Working directory for current project context

        Returns current directory if no context set (CLI mode).
        """
        context_dir = _project_context.get()
        if context_dir:
            return context_dir

        # Default to current directory (CLI mode)
        return str(Path.cwd())

    @staticmethod
    def clear():
        """Clear the project context."""
        _project_context.set(None)

    @staticmethod
    def _init_config(user_id: str, project_id: str, working_dir: str) -> None:
        """
        Initialize configuration file.

        Writes to .oryxforge.cfg with [profile] and [mount] sections.
        """
        from .iam import CredentialsManager
        from .config_service import ConfigService

        # Write credentials to [profile] section
        creds_manager = CredentialsManager(working_dir=working_dir)
        creds_manager.set_profile(user_id=user_id, project_id=project_id)

        # Write mount configuration to [mount] section
        config_service = ConfigService(working_dir=working_dir)

        if ProjectContext.is_api_mode():
            # API mode - set mount point and disable auto-mounting
            if os.environ.get('GOOGLE_CLOUD_PROJECT'):
                mount_point = f"/mnt/data/{user_id}/{project_id}"
            else:
                api_base = os.environ.get('ORYX_MOUNT_ROOT', '.')
                mount_point = f"{api_base}/mnt/data/{user_id}/{project_id}"

            config_service.set('mount', 'mount_point', mount_point)
            config_service.set('mount', 'mount_ensure', 'false')

            # Create mount subdirectory
            Path(mount_point).mkdir(parents=True, exist_ok=True)

            logger.debug(f"API mode: mount_point={mount_point}, mount_ensure=false")
        else:
            # CLI mode - enable auto-mounting, let user configure mount point
            config_service.set('mount', 'mount_ensure', 'true')

            logger.debug("CLI mode: mount_ensure=true")

"""Environment-aware configuration for OryxForge with zero-parameter services."""

import os
import sys
from pathlib import Path
from contextvars import ContextVar
from typing import Optional
from loguru import logger


# Thread-safe context variable for project working directory
_project_context: ContextVar[Optional[str]] = ContextVar('project_context', default=None)

# Thread-safe context variable for request initialization tracking
_request_initialized: ContextVar[bool] = ContextVar('request_initialized', default=False)


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
               os.environ.get('FASTAPI_ENV') is not None

    @staticmethod
    def get_mount_parent_path(user_id: str = None, project_id: str = None) -> str:
        """
        Get the mount parent path for API mode.

        This centralizes the logic for determining mount paths in API mode.

        Args:
            user_id: User UUID (optional, if provided returns project-specific path)
            project_id: Project UUID (optional, if provided returns project-specific path)

        Returns:
            str: Mount parent path
                - If user_id/project_id provided: Full project path (e.g., /mnt/data/{user}/{project})
                - If not provided: Parent mount path (e.g., /mnt/data)

        Raises:
            ValueError: If ORYX_MOUNT_ROOT not set in local API mode

        Examples:
            >>> ProjectContext.get_mount_parent_path()
            'D:/data/oryx-forge-api/mnt/data'
            >>> ProjectContext.get_mount_parent_path(user_id='abc', project_id='xyz')
            'D:/data/oryx-forge-api/mnt/data/abc/xyz'
        """
        if os.environ.get('GOOGLE_CLOUD_PROJECT'):
            # GCP production
            base_path = "/mnt/data"
        else:
            # Local API development
            api_base = os.environ.get('ORYX_MOUNT_ROOT')
            if not api_base:
                raise ValueError(
                    "ORYX_MOUNT_ROOT environment variable must be set when running in local API mode. "
                    "Example: export ORYX_MOUNT_ROOT=/path/to/project/root"
                )
            base_path = str(Path(api_base) / "mnt" / "data")

        # If user_id and project_id provided, return full project path
        if user_id and project_id:
            return str(Path(base_path) / user_id / project_id)

        # Otherwise return parent mount path
        return base_path

    @staticmethod
    def set(user_id: str, project_id: str, working_dir: str = None, write_config: bool = True) -> str:
        """
        Set the current project context.

        After calling this, all services can find their configuration
        without any parameters.

        Args:
            user_id: User UUID
            project_id: Project UUID
            working_dir: Optional working directory (for tests). If None, auto-detect based on environment.
            write_config: Whether to write .oryxforge.cfg file (default True).
                         When False, directory is not created (useful before git clone).

        Returns:
            str: Working directory that was set
        """
        # Track if working_dir was explicitly provided (test mode)
        is_test_mode = working_dir is not None

        # Determine working directory
        if working_dir:
            # Explicitly provided (typically for tests)
            working_dir = str(Path(working_dir).resolve())
        elif ProjectContext.is_api_mode():
            if os.environ.get('GOOGLE_CLOUD_PROJECT'):
                # GCP production
                working_dir = f"/tmp/{user_id}/{project_id}"
            else:
                # Local API development
                api_base = os.environ.get('ORYX_MOUNT_ROOT')
                if not api_base:
                    raise ValueError(
                        "ORYX_MOUNT_ROOT environment variable must be set when running in local API mode. "
                        "Example: export ORYX_MOUNT_ROOT=/path/to/project/root"
                    )
                working_dir = str(Path(api_base) / "mnt" / "projects" / user_id / project_id)
        else:
            # CLI mode - use current directory
            working_dir = str(Path.cwd())

        # Only create directory if we're writing config (need dir to write file)
        # When write_config=False, directory will be created by git clone
        if write_config:
            Path(working_dir).mkdir(parents=True, exist_ok=True)
            ProjectContext._init_config(user_id, project_id, working_dir, is_test_mode=is_test_mode)

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
        _request_initialized.set(False)

    @staticmethod
    def mark_initialized():
        """Mark that request-scoped initialization has been completed."""
        _request_initialized.set(True)

    @staticmethod
    def is_initialized() -> bool:
        """Check if request-scoped initialization has been completed.

        Returns:
            bool: True if initialization completed for this request
        """
        return _request_initialized.get()

    @staticmethod
    def write_config(user_id: str, project_id: str, working_dir: str = None) -> None:
        """
        Write configuration file after repo is cloned.

        This allows setting context (creating directory) without writing config first,
        so git clone can work on an empty directory. Call this after clone completes.

        Args:
            user_id: User UUID
            project_id: Project UUID
            working_dir: Optional working directory. If None, uses current context.
        """
        if working_dir is None:
            working_dir = ProjectContext.get()

        # Config writing happens after clone, so not test mode
        is_test_mode = False
        ProjectContext._init_config(user_id, project_id, working_dir, is_test_mode=is_test_mode)
        logger.debug(f"Wrote config to {working_dir}")

    @staticmethod
    def _init_config(user_id: str, project_id: str, working_dir: str, is_test_mode: bool = False) -> None:
        """
        Initialize configuration file.

        Writes to .oryxforge.cfg with [profile] and [mount] sections.

        Args:
            user_id: User UUID
            project_id: Project UUID
            working_dir: Working directory path
            is_test_mode: If True, disable mount_ensure (for tests)
        """
        from .iam import CredentialsManager
        from .config_service import ConfigService

        # Write credentials to [profile] section
        creds_manager = CredentialsManager(working_dir=working_dir)
        creds_manager.set_profile(user_id=user_id, project_id=project_id)

        # Write mount configuration to [mount] section
        config_service = ConfigService(working_dir=working_dir)

        if is_test_mode:
            # Test mode - disable auto-mounting
            config_service.set('mount', 'mount_ensure', 'false')
            logger.debug("Test mode: mount_ensure=false")
        elif ProjectContext.is_api_mode():
            # API mode - set mount point and disable auto-mounting
            mount_point = ProjectContext.get_mount_parent_path(user_id, project_id)

            config_service.set('mount', 'mount_point', mount_point)
            config_service.set('mount', 'mount_ensure', 'false')

            # Create mount subdirectory
            Path(mount_point).mkdir(parents=True, exist_ok=True)

            logger.debug(f"API mode: mount_point={mount_point}, mount_ensure=false")
        else:
            # CLI mode - enable auto-mounting, let user configure mount point
            config_service.set('mount', 'mount_ensure', 'true')

            # Set default mode to 'explore' for new projects
            config_service.set('active', 'mode', 'explore')

            logger.debug("CLI mode: mount_ensure=true, mode=explore")

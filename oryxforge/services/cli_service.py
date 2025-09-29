"""CLI Service for managing user configuration and project operations."""

import os
from pathlib import Path
from typing import Dict, List, Optional
from configobj import ConfigObj
from supabase import Client
from loguru import logger
from .utils import init_supabase_client
from .repo_service import RepoService
from .project_service import ProjectService


class CLIService:
    """
    Service class for CLI operations including user configuration and project management.
    """

    def __init__(self, user_id: str = None, cwd: str = None):
        """
        Initialize CLI service.

        Args:
            user_id: User ID (if None, read from config)
            cwd: Working directory (if None, use current directory)
        """
        self.cwd = Path(cwd) if cwd else Path.cwd()

        # Initialize user_id
        if user_id:
            self.user_id = user_id
        else:
            config = self.get_user_config()
            if 'userid' not in config:
                raise ValueError("No user ID configured. Run 'oryxforge admin userid set <userid>' first.")
            self.user_id = config['userid']

        # Initialize Supabase client
        self.supabase_client = init_supabase_client()

        # Validate user exists
        self._validate_user()


    def _validate_user(self) -> None:
        """Validate that user exists in auth.users table."""
        try:
            response = self.supabase_client.auth.admin.get_user_by_id(self.user_id)
            if not response.user:
                raise ValueError(f"User ID {self.user_id} not found in database")
        except Exception as e:
            raise ValueError(f"Failed to validate user ID {self.user_id}: {str(e)}")

    @property
    def config_dir(self) -> Path:
        """Get global configuration directory."""
        return Path.home() / '.oryxforge'

    @property
    def config_file(self) -> Path:
        """Get global configuration file path."""
        return self.config_dir / 'cfg.ini'

    @property
    def project_config_file(self) -> Path:
        """Get project-specific configuration file path."""
        return self.cwd / '.oryxforge'

    def get_user_config(self) -> Dict[str, str]:
        """
        Read user configuration from global config file.

        Returns:
            Dict with user configuration
        """
        if not self.config_file.exists():
            return {}

        config = ConfigObj(str(self.config_file))
        return dict(config.get('user', {}))

    def get_user_id(self) -> Optional[str]:
        """
        Get the current user ID from configuration or instance.

        Returns:
            str: User ID if configured, None if not set

        Raises:
            ValueError: If configuration file exists but is corrupted
        """
        try:
            # Return instance user_id if available
            if hasattr(self, 'user_id') and self.user_id:
                return self.user_id

            # Try to get from config file
            config = self.get_user_config()
            return config.get('userid')
        except Exception as e:
            raise ValueError(f"Failed to get user ID: {str(e)}")

    @staticmethod
    def get_configured_user_id() -> Optional[str]:
        """
        Get the user ID from global configuration without initializing CLIService.

        Returns:
            str: User ID if configured, None if not set

        Raises:
            ValueError: If configuration file exists but is corrupted
        """
        try:
            config_dir = Path.home() / '.oryxforge'
            config_file = config_dir / 'cfg.ini'

            if not config_file.exists():
                return None

            config = ConfigObj(str(config_file))
            user_config = config.get('user', {})
            return user_config.get('userid')
        except Exception as e:
            raise ValueError(f"Failed to read user configuration: {str(e)}")

    def set_user_config(self, user_id: str) -> None:
        """
        Set user ID in global configuration.

        Args:
            user_id: User ID to store

        Raises:
            ValueError: If user_id doesn't exist in database
        """
        # Create a temporary instance to validate user
        temp_service = CLIService.__new__(CLIService)
        temp_service.user_id = user_id
        temp_service.supabase_client = init_supabase_client()
        temp_service._validate_user()

        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Read existing config or create new
        config = ConfigObj()
        if self.config_file.exists():
            config = ConfigObj(str(self.config_file))

        # Set user config
        if 'user' not in config:
            config['user'] = {}
        config['user']['userid'] = user_id

        # Write config
        config.filename = str(self.config_file)
        config.write()

        logger.success(f"User ID {user_id} saved to {self.config_file}")

    def projects_create(self, name: str, setup_repo: bool = True) -> str:
        """
        Create a new project for the current user.

        Args:
            name: Project name (must be unique for user)
            setup_repo: Whether to create GitLab repository (default: True)

        Returns:
            str: Created project ID

        Raises:
            ValueError: If project name already exists for user
        """
        return ProjectService.create_project(name, self.user_id, setup_repo)

    def project_exists(self, project_id: str) -> bool:
        """
        Check if project exists and belongs to current user.

        Args:
            project_id: Project ID to check

        Returns:
            bool: True if project exists
        """
        try:
            response = (
                self.supabase_client.table("projects")
                .select("id")
                .eq("id", project_id)
                .eq("user_owner", self.user_id)
                .execute()
            )
            return len(response.data) > 0
        except Exception:
            return False

    def projects_list(self) -> List[Dict[str, str]]:
        """
        List all projects for the current user.

        Returns:
            List of dicts with project id and name
        """
        try:
            response = (
                self.supabase_client.table("projects")
                .select("id, name")
                .eq("user_owner", self.user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data
        except Exception as e:
            raise ValueError(f"Failed to list projects: {str(e)}")

    def project_activate(self, project_id: str) -> None:
        """
        Activate a project by updating local configuration.

        Args:
            project_id: Project ID to activate

        Raises:
            ValueError: If project doesn't exist
        """
        if not self.project_exists(project_id):
            raise ValueError(f"Project {project_id} not found or access denied")

        # Read existing config or create new
        config = ConfigObj()
        if self.project_config_file.exists():
            config = ConfigObj(str(self.project_config_file))

        # Set active project
        if 'active' not in config:
            config['active'] = {}
        config['active']['project_id'] = project_id

        # Write config
        config.filename = str(self.project_config_file)
        config.write()

        logger.success(f"Activated project {project_id}")

    def dataset_activate(self, dataset_id: str) -> None:
        """
        Activate a dataset by updating local configuration.

        Args:
            dataset_id: Dataset ID to activate

        Raises:
            ValueError: If dataset doesn't exist or doesn't belong to user
        """
        # Validate dataset exists and belongs to user
        try:
            response = (
                self.supabase_client.table("datasets")
                .select("id")
                .eq("id", dataset_id)
                .eq("user_owner", self.user_id)
                .execute()
            )
            if not response.data:
                raise ValueError(f"Dataset {dataset_id} not found or access denied")
        except Exception as e:
            raise ValueError(f"Failed to validate dataset: {str(e)}")

        # Update config
        config = ConfigObj()
        if self.project_config_file.exists():
            config = ConfigObj(str(self.project_config_file))

        if 'active' not in config:
            config['active'] = {}
        config['active']['dataset_id'] = dataset_id

        config.filename = str(self.project_config_file)
        config.write()

        logger.success(f"Activated dataset {dataset_id}")

    def sheet_activate(self, sheet_id: str) -> None:
        """
        Activate a datasheet by updating local configuration.

        Args:
            sheet_id: Datasheet ID to activate

        Raises:
            ValueError: If datasheet doesn't exist or doesn't belong to user
        """
        # Validate datasheet exists and belongs to user
        try:
            response = (
                self.supabase_client.table("datasheets")
                .select("id")
                .eq("id", sheet_id)
                .eq("user_owner", self.user_id)
                .execute()
            )
            if not response.data:
                raise ValueError(f"Datasheet {sheet_id} not found or access denied")
        except Exception as e:
            raise ValueError(f"Failed to validate datasheet: {str(e)}")

        # Update config
        config = ConfigObj()
        if self.project_config_file.exists():
            config = ConfigObj(str(self.project_config_file))

        if 'active' not in config:
            config['active'] = {}
        config['active']['sheet_id'] = sheet_id

        config.filename = str(self.project_config_file)
        config.write()

        logger.success(f"Activated datasheet {sheet_id}")

    def get_active(self) -> Dict[str, str]:
        """
        Get active project, dataset, and datasheet from local configuration.

        Returns:
            Dict with active IDs (empty dict if no config)
        """
        if not self.project_config_file.exists():
            return {}

        config = ConfigObj(str(self.project_config_file))
        return dict(config.get('active', {}))

    def interactive_project_select(self) -> str:
        """
        Interactive project selection from list.

        Returns:
            str: Selected project ID

        Raises:
            ValueError: If no projects found or invalid selection
        """
        projects = self.projects_list()
        if not projects:
            raise ValueError("No projects found for this user")

        print("\nAvailable projects:")
        print("=" * 50)
        for i, project in enumerate(projects, 1):
            print(f"{i:2d}. {project['name']} (ID: {project['id']})")

        while True:
            try:
                choice = input(f"\nSelect project (1-{len(projects)}): ").strip()
                if not choice:
                    raise ValueError("Selection cancelled")

                index = int(choice) - 1
                if 0 <= index < len(projects):
                    return projects[index]['id']
                else:
                    print(f"Invalid selection. Please enter 1-{len(projects)}")
            except (ValueError, KeyboardInterrupt):
                raise ValueError("Project selection cancelled")

    def repo_push(self, message: str, project_id: str = None) -> str:
        """
        Push changes to GitLab repository.

        Args:
            message: Commit message
            project_id: Project ID (if None, use active project)

        Returns:
            str: Commit hash

        Raises:
            ValueError: If project not found or push fails
        """
        if not project_id:
            active = self.get_active()
            project_id = active.get('project_id')
            if not project_id:
                raise ValueError("No project ID provided and no active project set")

        if not self.project_exists(project_id):
            raise ValueError(f"Project {project_id} not found or access denied")

        try:
            repo_service = RepoService(project_id, str(self.cwd))
            commit_hash = repo_service.push(message)
            logger.success(f"Changes pushed successfully: {commit_hash}")
            return commit_hash
        except Exception as e:
            raise ValueError(f"Failed to push changes: {str(e)}")

    def repo_pull(self, project_id: str = None) -> None:
        """
        Pull latest changes from GitLab repository.

        Args:
            project_id: Project ID (if None, use active project)

        Raises:
            ValueError: If project not found or pull fails
        """
        if not project_id:
            active = self.get_active()
            project_id = active.get('project_id')
            if not project_id:
                raise ValueError("No project ID provided and no active project set")

        if not self.project_exists(project_id):
            raise ValueError(f"Project {project_id} not found or access denied")

        try:
            repo_service = RepoService(project_id, str(self.cwd))
            repo_service.pull()
            logger.success("Repository updated successfully")
        except Exception as e:
            raise ValueError(f"Failed to pull changes: {str(e)}")

    def repo_status(self, project_id: str = None) -> Dict[str, bool]:
        """
        Get repository status information.

        Args:
            project_id: Project ID (if None, use active project)

        Returns:
            Dict with status information

        Raises:
            ValueError: If project not found
        """
        if not project_id:
            active = self.get_active()
            project_id = active.get('project_id')
            if not project_id:
                raise ValueError("No project ID provided and no active project set")

        if not self.project_exists(project_id):
            raise ValueError(f"Project {project_id} not found or access denied")

        try:
            repo_service = RepoService(project_id, str(self.cwd))

            status = {
                'exists_locally': repo_service.repo_exists_locally(),
                'exists_on_gitlab': repo_service._repo_exists_on_gitlab()
            }

            return status
        except Exception as e:
            raise ValueError(f"Failed to get repository status: {str(e)}")

    def admin_pull(self, project_id: str, working_dir: str = None) -> str:
        """
        Pull project repository and activate it.

        Args:
            project_id: Project ID to pull and activate
            working_dir: Working directory (if None, use current directory)

        Returns:
            str: Path to repository

        Raises:
            ValueError: If project not found or operations fail
        """
        if not self.project_exists(project_id):
            raise ValueError(f"Project {project_id} not found or access denied")

        # Use provided working directory or current directory
        target_dir = Path(working_dir) if working_dir else self.cwd

        try:
            # Initialize project service with target directory
            project_service = ProjectService(project_id, self.user_id)

            # Create repo service with target directory
            repo_service = RepoService(project_id, str(target_dir))

            # Ensure repository exists locally (clone if missing, pull if exists)
            repo_path = repo_service.ensure_repo()

            # Activate the project
            # Update CLI service working directory to match repository location
            old_cwd = self.cwd
            self.cwd = Path(repo_path)

            try:
                self.project_activate(project_id)
            finally:
                # Restore original cwd if activation failed
                if old_cwd != Path(repo_path):
                    self.cwd = old_cwd

            logger.success(f"Project {project_id} pulled and activated at {repo_path}")
            return repo_path

        except Exception as e:
            raise ValueError(f"Failed to pull and activate project: {str(e)}")
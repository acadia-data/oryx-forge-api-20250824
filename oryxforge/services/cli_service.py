"""CLI Service for managing user configuration and project operations."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from supabase import Client
from loguru import logger
from .utils import init_supabase_client
from .repo_service import RepoService
from .project_service import ProjectService
from .iam import CredentialsManager
from .config_service import ConfigService


class CLIService:
    """
    Service class for CLI operations including user configuration and project management.
    """

    # Valid project modes
    VALID_MODES = {'explore', 'edit', 'plan'}

    def __init__(self, user_id: str = None, cwd: str = None):
        """
        Initialize CLI service.

        Args:
            user_id: User ID (if None, read from profile via CredentialsManager)
            cwd: Working directory (if None, use current directory)
        """
        self.cwd = Path(cwd) if cwd else Path.cwd()

        # Initialize ConfigService
        self.config_service = ConfigService(working_dir=str(self.cwd))

        # Initialize user_id
        if user_id:
            self.user_id = user_id
        else:
            # Get user_id from profile via CredentialsManager
            creds_manager = CredentialsManager(working_dir=str(self.cwd))
            try:
                profile = creds_manager.get_profile()
                self.user_id = profile['user_id']
            except ValueError as e:
                raise ValueError(f"No profile configured. Run 'oryxforge admin profile set --userid <userid> --projectid <projectid>' first. {str(e)}")

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
        Activate a project by updating local configuration using CredentialsManager.

        Args:
            project_id: Project ID to activate

        Raises:
            ValueError: If project doesn't exist
        """
        if not self.project_exists(project_id):
            raise ValueError(f"Project {project_id} not found or access denied")

        # Use CredentialsManager to set profile
        creds_manager = CredentialsManager(working_dir=str(self.cwd))
        creds_manager.set_profile(user_id=self.user_id, project_id=project_id)

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

        # Update config using ConfigService
        self.config_service.set('active', 'dataset_id', dataset_id)

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

        # Update config using ConfigService
        self.config_service.set('active', 'sheet_id', sheet_id)

        logger.success(f"Activated datasheet {sheet_id}")

    def get_active(self) -> Dict[str, str]:
        """
        Get active project, dataset, datasheet, and mode from local configuration.

        Returns:
            Dict with active IDs including user_id and project_id from profile
        """
        # Get profile from CredentialsManager
        try:
            creds_manager = CredentialsManager(working_dir=str(self.cwd))
            profile = creds_manager.get_profile()
        except ValueError:
            # No profile set, return empty dict
            return {}

        # Also get dataset, sheet, and mode from config if exists
        result = {'user_id': profile['user_id'], 'project_id': profile['project_id']}

        # Get additional active settings from ConfigService
        active_section = self.config_service.get_all('active')
        if 'dataset_id' in active_section:
            result['dataset_id'] = active_section['dataset_id']
        if 'sheet_id' in active_section:
            result['sheet_id'] = active_section['sheet_id']
        if 'mode' in active_section:
            result['mode'] = active_section['mode']

        return result

    def mode_set(self, mode: str) -> None:
        """
        Set the project mode.

        Args:
            mode: Project mode to set (must be one of: explore, edit, plan)

        Raises:
            ValueError: If mode is not valid
        """
        if mode not in self.VALID_MODES:
            raise ValueError(
                f"Invalid mode '{mode}'. Must be one of: {', '.join(sorted(self.VALID_MODES))}"
            )

        self.config_service.set('active', 'mode', mode)
        logger.success(f"Project mode set to '{mode}'")

    def mode_get(self) -> Optional[str]:
        """
        Get the current project mode.

        Returns:
            Optional[str]: Current mode or None if not set
        """
        return self.config_service.get('active', 'mode')

    def mount_point_set(self, mount_point: str) -> None:
        """
        Set the mount point for the project data directory.

        Args:
            mount_point: Path to use as mount point (must be absolute path)

        Raises:
            ValueError: If mount point format is invalid
        """
        # Validate and normalize path
        path = self.config_service.validate_mount_point(mount_point)

        # Store as POSIX format for cross-platform compatibility
        self.config_service.set('active', 'mount_point', path.as_posix())

        logger.success(f"Mount point set to '{path.as_posix()}'")

    def mount_point_get(self) -> Optional[str]:
        """
        Get the configured mount point.

        Returns:
            Optional[str]: Mount point path in POSIX format, or None if not set
        """
        return self.config_service.get('active', 'mount_point')

    def mount_point_suggest(self, base_path: str) -> str:
        """
        Suggest a mount point with user/project hierarchy.

        Takes a base path and appends /{user_id}/{project_id}/data to create
        a project-specific mount point directory.

        Args:
            base_path: Base directory path (e.g., 'D:\\data\\oryx-forge')

        Returns:
            str: Suggested mount point path in POSIX format

        Raises:
            ValueError: If no profile is configured or path validation fails

        Example:
            >>> cli_service.mount_point_suggest("D:\\data\\oryx-forge")
            'D:/data/oryx-forge/550e8400-e29b-41d4-a716-446655440000/abc123-project-id/data'
        """
        # Get profile (both user_id and project_id)
        active = self.get_active()

        # Validate profile is configured
        if not active or 'user_id' not in active or 'project_id' not in active:
            raise ValueError(
                "No profile configured. Run 'oryxforge admin profile set --userid <id> --projectid <id>' first."
            )

        user_id = active['user_id']
        project_id = active['project_id']

        # Build suggested path: base_path/user_id/project_id/data
        suggested_path = Path(base_path) / user_id / project_id / "data"

        # Validate and return as POSIX
        validated_path = self.config_service.validate_mount_point(str(suggested_path))
        return validated_path.as_posix()

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

    def sources_list(self) -> List[Dict[str, Any]]:
        """
        List all data sources for the current project.

        Returns:
            List of dicts with source information (name, file_type, created_at, etc.)

        Raises:
            ValueError: If no profile configured or query fails
        """
        from .iam import CredentialsManager

        # Get profile
        creds_manager = CredentialsManager(working_dir=str(self.cwd))
        try:
            profile = creds_manager.get_profile()
            project_id = profile['project_id']
        except ValueError as e:
            raise ValueError(
                f"No profile configured. Run 'oryxforge admin config profile set --userid <userid> --projectid <projectid>' first. {str(e)}"
            )

        try:
            response = (
                self.supabase_client.table("data_sources")
                .select("id, name, type as file_type, created_at, status")
                .eq("project_id", project_id)
                .eq("user_owner", self.user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data
        except Exception as e:
            raise ValueError(f"Failed to list data sources: {str(e)}")

    def import_file(self, path: str) -> Dict[str, Any]:
        """
        Import a file into the active project's "Sources" dataset.

        Creates a data_sources entry with local:// URI and uses ImportService to process.

        Args:
            path: Path to the file to import

        Returns:
            Dict containing:
                - message: Success message
                - file_id: ID of the data_sources entry
                - file_name: Name of the imported file
                - dataset_id: ID of the Sources dataset
                - sheet_id: ID of the created datasheet
                - sheet_name: Python name of the created datasheet (name_python)
                - dataset_name: Name of the dataset ("Sources")

        Raises:
            ValueError: If import fails or no active project configured
        """
        from .import_service import ImportService
        from .iam import CredentialsManager

        # Get profile
        creds_manager = CredentialsManager(working_dir=str(self.cwd))
        profile = creds_manager.get_profile()
        user_id = profile['user_id']
        project_id = profile['project_id']

        # Extract file name from path
        file_path = Path(path)
        file_name = file_path.name

        # Create data_sources entry with local:// URI
        file_uri = f"local://{file_path.resolve()}"

        # Use upsert to handle retries - if same filename already exists for this project, reuse it
        response = self.supabase_client.table("data_sources").upsert({
            "uri": file_uri,
            "name": file_name,
            "type": "auto",
            "user_owner": user_id,
            "project_id": project_id,
            "status": {
                "flag": "pending",
                "msg": "File registered, awaiting processing"
            }
        },
        on_conflict="name,project_id,user_owner").execute()

        file_id = response.data[0]['id']
        logger.info(f"Data source ready with file_id: {file_id}")

        # Import using ImportService
        import_service = ImportService(file_id)
        result = import_service.import_file()

        logger.success(f"File imported: {result['message']}")

        return result

    def chat(self, message: str) -> Dict[str, Any]:
        """
        Process a chat message for interactive data analysis.

        Args:
            message: User's chat message

        Returns:
            Dict containing:
                - message: Agent response text
                - target_dataset: Target dataset name_python
                - target_sheet: Target sheet name_python
                - cost_usd: Cost of operation
                - duration_ms: Duration of operation

        Raises:
            ValueError: If no profile configured or chat processing fails
        """
        from .chat_service import ChatService
        from .iam import CredentialsManager

        # Get profile
        creds_manager = CredentialsManager(working_dir=str(self.cwd))
        try:
            profile = creds_manager.get_profile()
            user_id = profile['user_id']
            project_id = profile['project_id']
        except ValueError as e:
            raise ValueError(
                f"No profile configured. Run 'oryxforge admin profile set --userid <userid> --projectid <projectid>' first. {str(e)}"
            )

        # Get mode (default to 'explore' if not set)
        mode = self.mode_get()
        if not mode:
            mode = 'explore'
            logger.info("No mode set, defaulting to 'explore'")

        # Get active dataset and sheet from configuration
        active_config = self.get_active()
        ds_active = active_config.get('dataset_id')
        sheet_active = active_config.get('sheet_id')

        # Initialize ChatService
        chat_service = ChatService(user_id=user_id, project_id=project_id)

        # Process chat
        logger.info(f"Processing chat message in mode: {mode}")
        result = chat_service.chat(
            message_user=message,
            mode=mode,
            ds_active=ds_active,
            sheet_active=sheet_active
        )

        logger.success("Chat message processed successfully")
        return result
"""Project Service for managing datasets, datasheets, and project operations."""

import os
import subprocess
import sys
import platform
import ctypes
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
import time
import pandas as pd
import gcsfs
from supabase import Client
from loguru import logger
from .workflow_service import WorkflowService
from .repo_service import RepoService
from .utils import init_supabase_client, get_project_data
from .iam import CredentialsManager
from .config_service import ConfigService

# Sentinel value for "read mount_ensure from config"
_READ_FROM_CONFIG = object()


class ProjectService:
    """
    Service class for project-level operations including datasets, datasheets, and git operations.
    """

    def __init__(self, project_id: Optional[str] = None, user_id: Optional[str] = None, working_dir: Optional[str] = None, mount_ensure = _READ_FROM_CONFIG):
        """
        Initialize project service.

        Gets user_id and project_id from CredentialsManager if not provided.

        Args:
            project_id: Project ID (if None, read from profile)
            user_id: User ID (if None, read from profile)
            working_dir: Working directory (if None, get from ProjectContext)
            mount_ensure: Mount validation behavior:
                - True: Validate mount and auto-mount if needed (CLI default)
                - False: Validate mount exists, fail if not ready (API mode)
                - None: Skip mount validation entirely (mount management commands)
                - Not provided (default): Read from config, defaults to True if not in config

        Raises:
            ValueError: If project doesn't exist or profile is not configured
        """
        # Get working_dir from ProjectContext if not provided
        if working_dir is None:
            from .env_config import ProjectContext
            self.working_dir = ProjectContext.get()
        else:
            self.working_dir = working_dir

        # Get profile from CredentialsManager if not provided
        if project_id is None or user_id is None:
            creds_manager = CredentialsManager(working_dir=self.working_dir)
            profile = creds_manager.get_profile()
            self.project_id = project_id or profile['project_id']
            self.user_id = user_id or profile['user_id']
        else:
            self.project_id = project_id
            self.user_id = user_id

        # Read mount configuration from [mount] section
        config_service = ConfigService(working_dir=self.working_dir)
        saved_mount = config_service.get('mount', 'mount_point')
        if saved_mount:
            # Convert from POSIX format to native Path
            self.mount_point = str(Path(saved_mount))
            logger.debug(f"Using mount point from config: {self.mount_point}")
        else:
            # Use default
            self.mount_point = "./data"
            logger.debug("Using default mount point: ./data")

        # Determine mount_ensure setting (tri-state logic)
        if mount_ensure is _READ_FROM_CONFIG:
            # Read from [mount] section in config
            mount_ensure_str = config_service.get('mount', 'mount_ensure')
            self.mount_ensure_final = (mount_ensure_str != 'false') if mount_ensure_str else True
        elif mount_ensure is None:
            # Explicitly set to None → skip mount validation (mount management mode)
            self.mount_ensure_final = None
        else:
            # Explicitly set to True or False → use provided value
            self.mount_ensure_final = mount_ensure

        # Initialize Supabase client
        self.supabase_client = init_supabase_client()

        # Run request-scoped initialization (once per request)
        # Always initialize resources; mount_ensure only controls auto-mount behavior
        from .env_config import ProjectContext
        if not ProjectContext.is_initialized():
            self._initialize_resources()
            ProjectContext.mark_initialized()

    @property
    def mount_point_path(self) -> Path:
        """
        Get mount point as a Path object for easy path manipulation.

        Returns:
            Path: Mount point as pathlib Path object

        Examples:
            >>> ps = ProjectService()
            >>> file_path = ps.mount_point_path / "exploration" / "data.parquet"
        """
        return Path(self.mount_point)

    def _validate_project(self) -> None:
        """Validate that project exists and belongs to user."""
        try:
            project_data = get_project_data(
                self.supabase_client,
                self.project_id,
                self.user_id,
                fields="id, name"
            )
            self.project_name = project_data['name']
            logger.debug(f"Validated project: {self.project_name}")

        except Exception as e:
            raise ValueError(f"Failed to validate project: {str(e)}")

    def _get_mount_check_path(self) -> str:
        """Get the path to check for mount status based on mode.

        In API mode, we check the parent mount directory since all projects
        share a common mounted parent. In CLI mode, we check the project-specific
        mount point.

        Returns:
            str: Path to check for mount status
                - API mode: Parent mount path (e.g., D:/data/oryx-forge-api/mnt/data)
                - CLI mode: Project mount path (e.g., ./data)
        """
        from .env_config import ProjectContext
        if ProjectContext.is_api_mode():
            # API mode: check parent mount (without user/project subdirs)
            return ProjectContext.get_mount_parent_path()
        else:
            # CLI mode: check project-specific mount
            return self.mount_point

    def _initialize_resources(self) -> None:
        """Initialize and validate resources (always runs once per request).

        This method ALWAYS runs during the first ProjectService initialization per request.
        It performs critical validation and setup:
        - Validates project exists and belongs to user
        - Checks mount accessibility (skipped if mount_ensure_final is None or in test mode)
        - Attempts auto-mount if needed (CLI mode with mount_ensure=True)
        - Configures d6tflow directory

        The mount_ensure_final setting controls mount validation behavior:
        - True: Validate and auto-mount if not ready (CLI mode)
        - False: Validate only, fail if not ready (API mode)
        - None: Skip mount validation entirely (mount management commands)

        Raises:
            ValueError: If project validation fails or mount is not accessible
        """
        from .env_config import ProjectContext

        # Step 1: Validate project exists and belongs to user
        self._validate_project()

        # Step 2: Skip mount validation if mount_ensure_final is None (mount management mode)
        if self.mount_ensure_final is None:
            logger.debug("Mount validation skipped (mount_ensure=None, mount management mode)")
            # Still configure d6tflow with whatever mount_point is set
            import d6tflow
            d6tflow.set_dir(self.mount_point)
            logger.success(f"Initialized (validation skipped): mount={self.mount_point}, d6tflow configured")
            return

        # Step 3: Check if in test mode (working_dir contains temp directory patterns)
        is_test_mode = self._is_test_mode()

        if not is_test_mode:
            # Step 3: Get appropriate mount check path based on mode
            mount_check_path = self._get_mount_check_path()

            # Step 4: Check if mount is ready for operations
            if not self._is_mount_ready(mount_check_path):
                # Step 5: Handle unmounted state based on mode
                if self.mount_ensure_final:
                    # CLI mode: Attempt to auto-mount
                    self._attempt_mount()
                else:
                    # API mode: Fail fast with clear error
                    mode_desc = "parent mount directory" if ProjectContext.is_api_mode() else "project mount point"
                    raise ValueError(
                        f"Mount not ready: {mode_desc} at '{mount_check_path}' is not accessible. "
                        f"In {'API' if ProjectContext.is_api_mode() else 'CLI'} mode, mount must be set up before starting."
                    )

            logger.debug(f"Mount verified at {mount_check_path}")
        else:
            logger.debug(f"Test mode detected - skipping mount validation")

        # Step 6: Configure d6tflow directory (always set, even in test mode)
        import d6tflow
        d6tflow.set_dir(self.mount_point)
        logger.success(f"Initialized: mount={self.mount_point}, d6tflow configured")

    def _is_test_mode(self) -> bool:
        """Detect if running in test mode.

        Test mode is detected by checking if working_dir contains temp directory patterns.

        Returns:
            bool: True if in test mode, False otherwise
        """
        import tempfile
        temp_dir = tempfile.gettempdir()
        return str(self.working_dir).startswith(temp_dir)

    def _is_mount_ready(self, path: str) -> bool:
        """Check if mount path is ready for operations.

        Verifies that the mount path exists and is accessible. In CLI mode,
        additionally checks if path is actually mounted (not just a directory).

        Args:
            path: Path to check (mount_check_path)

        Returns:
            bool: True if mount is ready, False otherwise

        Note:
            API mode trusts external mount setup (just checks existence).
            CLI mode verifies it's actually a mount point.
        """
        from .env_config import ProjectContext

        # First check: Path must exist
        if not os.path.exists(path):
            logger.debug(f"Mount path does not exist: {path}")
            return False

        # API mode: Trust external mount setup (path exists = ready)
        if ProjectContext.is_api_mode():
            logger.debug(f"API mode: Mount path exists at {path}")
            return True

        # CLI mode: Verify it's actually mounted (not just a directory)
        # Temporarily set mount_point for is_mounted() check
        original_mount_point = self.mount_point
        self.mount_point = path
        try:
            is_mounted = self.is_mounted()
            logger.debug(f"CLI mode: Mount check at {path} = {is_mounted}")
            return is_mounted
        finally:
            # Restore original mount_point
            self.mount_point = original_mount_point

    def _attempt_mount(self) -> None:
        """Attempt to mount the data directory (CLI mode only).

        Tries to mount using rclone. Only called when mount_ensure=true
        and mount is not already mounted.

        Raises:
            ValueError: If mount operation fails
        """
        logger.info(f"Mount not ready, attempting to mount {self.mount_point}...")
        if not self.mount():
            raise ValueError(
                f"Failed to mount data directory at {self.mount_point}. "
                f"Please check that rclone is installed and configured correctly."
            )


    @classmethod
    def create_project(cls, name: str, user_id: str, setup_repo: bool = True) -> str:
        """Create a new project with optional repository setup.

        Args:
            name: Project display name (must be unique for user)
            user_id: User UUID who owns the project
            setup_repo: Whether to create GitLab repository (default: True)

        Returns:
            str: Created project UUID

        Raises:
            ValueError: If project name already exists or creation fails
        """
        # Initialize Supabase client for project creation
        supabase_client = init_supabase_client()

        try:
            # Create project in database
            response = (
                supabase_client.table("projects")
                .insert({
                    "name": name,
                    "user_owner": user_id
                })
                .execute()
            )

            if not response.data:
                raise ValueError("Failed to create project")

            project_id = response.data[0]['id']
            logger.success(f"Created project '{name}' with ID: {project_id}")

            # Optionally create GitLab repository
            if setup_repo:
                try:
                    repo_service = RepoService(project_id=project_id, user_id=user_id, working_dir=str(Path.cwd()))
                    created = repo_service.create_repo()
                    if created:
                        logger.success(f"Created GitLab repository for project '{name}'")
                    else:
                        logger.info(f"GitLab repository already exists for project '{name}'")
                except Exception as e:
                    logger.warning(f"Failed to create GitLab repository: {str(e)}")
                    # Don't fail the entire operation if repo creation fails

            return project_id

        except Exception as e:
            if "unique_user_project_name" in str(e):
                raise ValueError(f"Project '{name}' already exists for this user")
            raise ValueError(f"Failed to create project: {str(e)}")

    @classmethod
    def project_init(cls, project_id: str, user_id: str, target_dir: str = None) -> str:
        """
        Initialize project locally: clone repo and set up config.

        This is the recommended way to set up a project locally for both CLI and API.
        Order of operations: set context (no dir creation) → ensure/clone repo → write config.

        Args:
            project_id: Project UUID
            user_id: User UUID
            target_dir: Target directory (if None, auto-determine from environment)

        Returns:
            str: Path to initialized project directory

        Raises:
            ValueError: If initialization fails
        """
        from .env_config import ProjectContext

        # Get project data to ensure repo exists on GitLab
        supabase_client = init_supabase_client()
        project_data = get_project_data(supabase_client, project_id, user_id, fields="name,name_git,git_path")

        # Check if GitLab repo exists, create if needed
        if not project_data.get('git_path'):
            logger.info("GitLab repository not found, creating...")
            repo_service_temp = RepoService(project_id=project_id, user_id=user_id, working_dir=str(Path.cwd()))
            repo_service_temp.create_repo()
            # Refresh project_data to get updated git_path
            project_data = get_project_data(supabase_client, project_id, user_id, fields="name,name_git,git_path")

        # Set context WITHOUT writing config and WITHOUT creating directory
        # ProjectContext.set() will auto-determine working_dir based on environment if target_dir is None
        working_dir = ProjectContext.set(user_id, project_id, working_dir=target_dir, write_config=False)

        # Ensure repository exists (clone if missing, pull if exists)
        repo_service = RepoService(project_id=project_id, user_id=user_id, working_dir=working_dir)
        repo_service.ensure_repo()

        # NOW write config (after repo clone/pull completes)
        ProjectContext.write_config(user_id, project_id, working_dir)

        logger.success(f"Initialized project at {working_dir}")
        return working_dir

    def ds_list(self) -> List[Dict[str, str]]:
        """List all datasets for the current project.

        Returns:
            List[Dict[str, str]]: List of dicts with keys:
                - id: Dataset UUID
                - name: Dataset display name
                - name_python: Python-safe name (snake_case)
        """
        try:
            response = (
                self.supabase_client.table("datasets")
                .select("id, name, name_python")
                .eq("project_id", self.project_id)
                .eq("user_owner", self.user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data
        except Exception as e:
            raise ValueError(f"Failed to list datasets: {str(e)}")

    def ds_create(self, name: str) -> Dict[str, str]:
        """Create a new dataset in the current project.

        The name will be automatically converted to a Python-safe name_python (snake_case).

        Uses upsert to handle idempotent operations - if a dataset with the same
        (user_owner, project_id, name) already exists, returns the existing dataset data.

        Args:
            name: Dataset display name (e.g., 'My Data Sources')

        Returns:
            Dict[str, str]: Dict with keys:
                - id: Dataset UUID
                - name: Dataset display name
                - name_python: Python-safe name (snake_case)

        Raises:
            ValueError: If dataset creation fails or name is reserved
        """
        # Check for reserved dataset names
        reserved_names = ['preview']
        if name.lower() in reserved_names:
            raise ValueError(f"Dataset name '{name}' is reserved and cannot be used. Reserved names: {', '.join(reserved_names)}")

        try:
            response = (
                self.supabase_client.table("datasets")
                .upsert({
                    "name": name,
                    "user_owner": self.user_id,
                    "project_id": self.project_id
                },
                on_conflict="user_owner,project_id,name")
                .execute()
            )

            if not response.data:
                raise ValueError("Failed to create dataset")

            dataset_data = response.data[0]
            logger.success(f"Dataset '{name}' ready with ID: {dataset_data['id']}")

            # Return relevant fields
            return {
                'id': dataset_data['id'],
                'name': dataset_data['name'],
                'name_python': dataset_data['name_python']
            }

        except Exception as e:
            raise ValueError(f"Failed to create dataset: {str(e)}")

    def ds_create_get(self, name: str) -> Dict[str, str]:
        """Create a new dataset in the current project.

        The name will be automatically converted to a Python-safe name_python (snake_case).

        Uses upsert to handle idempotent operations - if a dataset with the same
        (user_owner, project_id, name) already exists, returns the existing dataset data.

        Args:
            name: Dataset display name (e.g., 'My Data Sources')

        Returns:
            Dict[str, str]: Dict with keys:
                - id: Dataset UUID
                - name: Dataset display name
                - name_python: Python-safe name (snake_case)

        Raises:
            ValueError: If dataset creation fails
        """
        return self.ds_create(name)

    def sheet_create(self, dataset_id: Optional[str] = None, name: str = None, source_id: Optional[str] = None, type: str = 'table', dataset_name_python: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Create a new datasheet in the specified dataset.

        The name will be automatically converted to a Python-safe name_python (PascalCase).

        Uses upsert to handle idempotent operations - if a sheet with the same
        (user_owner, dataset_id, name) already exists, returns the existing sheet data.

        Args:
            dataset_id: Dataset UUID (if None, must provide dataset_name_python)
            name: Datasheet display name (e.g., 'HPI Master CSV')
            source_id: Optional UUID of data_sources entry that this sheet is imported from
            type: Type of datasheet (default: 'table')
            dataset_name_python: Dataset Python name (snake_case) to look up dataset_id (lower priority than dataset_id)
            metadata: Optional dict of additional key-value pairs to store in the datasheet (e.g., {'uri': 'path/to/file', 'size': 1024})

        Returns:
            Dict[str, str]: Dict with keys:
                - id: Datasheet UUID
                - name: Datasheet display name
                - name_python: Python-safe name (PascalCase)
                - dataset_id: Parent dataset UUID

        Raises:
            ValueError: If dataset doesn't exist or neither dataset_id nor dataset_name_python provided

        Note:
            Parameter priority for dataset resolution: dataset_id > dataset_name_python
        """
        # Resolve dataset_id from dataset_name_python if needed
        resolved_dataset_id = dataset_id
        if not resolved_dataset_id and dataset_name_python:
            dataset_info = self.ds_get(name_python=dataset_name_python)
            resolved_dataset_id = dataset_info['id']

        if not resolved_dataset_id:
            raise ValueError("Either dataset_id or dataset_name_python must be provided")

        # Validate dataset exists and belongs to user
        if not self.ds_exists(resolved_dataset_id):
            raise ValueError(f"Dataset {resolved_dataset_id} not found or access denied")

        try:
            # Build upsert data
            upsert_data = {
                "name": name,
                "user_owner": self.user_id,
                "dataset_id": resolved_dataset_id,
                "type": type
            }

            # Add source_id if provided
            if source_id is not None:
                upsert_data["source_id"] = source_id

            # Add metadata fields if provided
            if metadata is not None:
                for key, value in metadata.items():
                    upsert_data[key] = value

            response = (
                self.supabase_client.table("datasheets")
                .upsert(upsert_data,
                on_conflict="user_owner,dataset_id,name")
                .execute()
            )

            if not response.data:
                raise ValueError("Failed to create datasheet")

            sheet_data = response.data[0]
            logger.success(f"Datasheet '{name}' ready with ID: {sheet_data['id']}")

            # Return relevant fields
            return {
                'id': sheet_data['id'],
                'name': sheet_data['name'],
                'name_python': sheet_data['name_python'],
                'dataset_id': sheet_data['dataset_id']
            }

        except Exception as e:
            raise ValueError(f"Failed to create datasheet: {str(e)}")

    def sheet_list(self, dataset_id: str = None, dataset_name: str = None, dataset_name_python: str = None) -> List[Dict[str, str]]:
        """List datasheets for specified dataset or all datasets in project.

        Args:
            dataset_id: Dataset UUID (if None, list all datasheets in project)
            dataset_name: Dataset display name to filter by (lower priority than dataset_id)
            dataset_name_python: Dataset Python name (snake_case) to filter by (lowest priority)

        Returns:
            List[Dict[str, str]]: List of dicts with keys:
                - id: Datasheet UUID
                - name: Datasheet display name
                - name_python: Python-safe name (PascalCase)
                - dataset_id: Parent dataset UUID

        Note:
            Parameter priority: dataset_id > dataset_name > dataset_name_python
            Returns empty list if no matches found
        """
        try:
            # Resolve dataset_id from name parameters if needed
            resolved_dataset_id = dataset_id

            if not resolved_dataset_id and dataset_name:
                # Query datasets by name
                response = (
                    self.supabase_client.table("datasets")
                    .select("id")
                    .eq("project_id", self.project_id)
                    .eq("user_owner", self.user_id)
                    .eq("name", dataset_name)
                    .execute()
                )
                if response.data:
                    resolved_dataset_id = response.data[0]['id']
                else:
                    return []  # No matching dataset found

            if not resolved_dataset_id and dataset_name_python:
                # Query datasets by name_python
                response = (
                    self.supabase_client.table("datasets")
                    .select("id")
                    .eq("project_id", self.project_id)
                    .eq("user_owner", self.user_id)
                    .eq("name_python", dataset_name_python)
                    .execute()
                )
                if response.data:
                    resolved_dataset_id = response.data[0]['id']
                else:
                    return []  # No matching dataset found

            # Build datasheets query
            query = (
                self.supabase_client.table("datasheets")
                .select("id, name, name_python, dataset_id")
                .eq("user_owner", self.user_id)
            )

            if resolved_dataset_id:
                query = query.eq("dataset_id", resolved_dataset_id)
            else:
                # Filter by project through datasets
                datasets = self.ds_list()
                dataset_ids = [ds['id'] for ds in datasets]
                if not dataset_ids:
                    return []
                query = query.in_("dataset_id", dataset_ids)

            response = query.order("created_at", desc=True).execute()
            return response.data

        except Exception as e:
            raise ValueError(f"Failed to list datasheets: {str(e)}")

    def ds_sheet_list(self, format: str = 'df'):
        """List all dataset-sheet combinations for the current project.

        Args:
            format: Output format - 'df' for pandas DataFrame (default), 'list' for list of dicts

        Returns:
            If format='df': pandas DataFrame with columns:
                - name_dataset: Dataset display name
                - name_sheet: Sheet display name
                - name_python: Combined {dataset_name_python}.{sheet_name_python} (e.g., "sources.HpiMasterCsv")

            If format='list': List of dicts with same keys

        Raises:
            ValueError: If query fails or invalid format specified
        """
        if format not in ['df', 'list']:
            raise ValueError(f"Invalid format '{format}'. Must be 'df' or 'list'")

        try:
            # Query datasheets with join to datasets
            response = (
                self.supabase_client.table("datasheets")
                .select("name, name_python, datasets!inner(name, name_python, project_id, user_owner)")
                .eq("user_owner", self.user_id)
                .eq("datasets.project_id", self.project_id)
                .eq("datasets.user_owner", self.user_id)
                .order("name_python")
                .execute()
            )

            # Build result list
            results = []
            for row in response.data:
                results.append({
                    'name_dataset': row['datasets']['name'],
                    'name_sheet': row['name'],
                    'name_python': f"{row['datasets']['name_python']}.{row['name_python']}"
                })

            if format == 'df':
                return pd.DataFrame(results)
            else:
                return results

        except Exception as e:
            raise ValueError(f"Failed to list dataset-sheet combinations: {str(e)}")

    def ds_sheet_get(self, name_python: str) -> Dict[str, any]:
        """Get dataset and sheet information from combined "dataset.sheet" notation.

        Args:
            name_python: Combined dataset.sheet name in Python notation (e.g., "sources.HpiMasterCsv")

        Returns:
            Dict with keys:
            {
                'dataset': {
                    'id': '...',
                    'name': 'Sources',
                    'name_python': 'sources'
                },
                'sheet': {
                    'id': '...',
                    'name': 'HPI Master CSV',
                    'name_python': 'HpiMasterCsv',
                    'dataset_id': '...'
                },
                'ds_sheet_name_python': 'sources.HpiMasterCsv'  # Combined (same as input)
            }

        Raises:
            ValueError: If invalid format, not found, or multiple matches
        """
        # Validate and parse input
        if not name_python or '.' not in name_python:
            raise ValueError(f"Invalid format: '{name_python}'. Expected 'dataset.sheet' notation (e.g., 'sources.HpiMasterCsv')")

        try:
            dataset_py, sheet_py = name_python.split('.', 1)
        except ValueError:
            raise ValueError(f"Invalid format: '{name_python}'. Expected 'dataset.sheet' notation")

        if not dataset_py or not sheet_py:
            raise ValueError(f"Invalid format: '{name_python}'. Both dataset and sheet names must be non-empty")

        try:
            # Query datasheets with join to datasets
            response = (
                self.supabase_client.table("datasheets")
                .select("id, name, name_python, dataset_id, uri, datasets!inner(id, name, name_python)")
                .eq("user_owner", self.user_id)
                .eq("name_python", sheet_py)
                .eq("datasets.name_python", dataset_py)
                .eq("datasets.project_id", self.project_id)
                .eq("datasets.user_owner", self.user_id)
                .execute()
            )

            if not response.data:
                raise ValueError(
                    f"Dataset-sheet combination '{name_python}' not found in this project. "
                    f"Use project_dataset_sheets_list() to see available dataset-sheet combinations."
                )

            if len(response.data) > 1:
                raise ValueError(f"Multiple matches found for '{name_python}'")

            row = response.data[0]

            # Build nested result structure
            return {
                'dataset': {
                    'id': row['datasets']['id'],
                    'name': row['datasets']['name'],
                    'name_python': row['datasets']['name_python']
                },
                'sheet': {
                    'id': row['id'],
                    'name': row['name'],
                    'name_python': row['name_python'],
                    'dataset_id': row['dataset_id'],
                    'uri': row.get('uri')
                },
                'ds_sheet_name_python': name_python
            }

        except Exception as e:
            if "not found" in str(e) or "Multiple matches" in str(e) or "Invalid format" in str(e):
                raise
            raise ValueError(f"Failed to get dataset-sheet combination: {str(e)}")

    def ensure_repo(self) -> None:
        """Ensure git repository exists locally.

        Clones the repository if not present, pulls latest changes if it exists.

        Raises:
            ValueError: If git operations fail
        """
        try:
            # RepoService will get credentials from same working_dir as ProjectService
            repo_service = RepoService(working_dir=self.working_dir)

            # Ensure repo exists locally (clone if needed, pull if exists)
            repo_path = repo_service.ensure_repo()

            logger.success(f"Project {self.project_id} initialized successfully")

        except Exception as e:
            raise ValueError(f"Project initialization failed: {str(e)}")


    def ds_exists(self, dataset_id: str) -> bool:
        """Check if dataset exists and belongs to current user/project.

        Args:
            dataset_id: Dataset UUID to check

        Returns:
            bool: True if dataset exists and user has access
        """
        try:
            response = (
                self.supabase_client.table("datasets")
                .select("id")
                .eq("id", dataset_id)
                .eq("project_id", self.project_id)
                .eq("user_owner", self.user_id)
                .execute()
            )
            return len(response.data) > 0
        except Exception:
            return False


    def sheet_exists(self, sheet_id: str) -> bool:
        """Check if datasheet exists and belongs to current user.

        Args:
            sheet_id: Datasheet UUID to check

        Returns:
            bool: True if datasheet exists and user has access
        """
        try:
            response = (
                self.supabase_client.table("datasheets")
                .select("id")
                .eq("id", sheet_id)
                .eq("user_owner", self.user_id)
                .execute()
            )
            return len(response.data) > 0
        except Exception:
            return False


    def is_initialized(self) -> bool:
        """
        Check if project has been initialized.

        Returns:
            bool: True if project is initialized
        """
        try:
            # Check if project exists and has name
            if self.project_id is None or self.project_name is None:
                return False

            # Check if GitLab repository exists
            repo_service = RepoService(working_dir=self.working_dir)
            return repo_service.repo_exists_locally()
        except Exception:
            return False

    def _get_default_dataset_id(self) -> str:
        """
        Find "exploration" dataset for current project.

        Returns:
            str: Dataset ID for exploration dataset

        Raises:
            ValueError: If exploration dataset not found
        """
        try:
            response = (
                self.supabase_client.table("datasets")
                .select("id")
                .eq("project_id", self.project_id)
                .eq("user_owner", self.user_id)
                .eq("name", "exploration")
                .execute()
            )
            if not response.data:
                raise ValueError("Exploration dataset not found")
            return response.data[0]['id']
        except Exception as e:
            raise ValueError(f"Failed to find default dataset: {str(e)}")

    def get_first_sheet_id(self, dataset_id: str) -> str:
        """
        Get first sheet in specified dataset.

        Args:
            dataset_id: Dataset ID

        Returns:
            str: First sheet ID

        Raises:
            ValueError: If no sheets found
        """
        sheets = self.sheet_list(dataset_id)
        if not sheets:
            raise ValueError(f"No datasheets found in dataset {dataset_id}")
        return sheets[0]['id']

    def interactive_dataset_select(self) -> str:
        """
        Interactive dataset selection from list.

        Returns:
            str: Selected dataset ID

        Raises:
            ValueError: If no datasets found or invalid selection
        """
        datasets = self.ds_list()
        if not datasets:
            raise ValueError("No datasets found in this project")

        print("\nAvailable datasets:")
        print("=" * 50)
        for i, dataset in enumerate(datasets, 1):
            print(f"{i:2d}. {dataset['name']} (ID: {dataset['id']})")

        while True:
            try:
                choice = input(f"\nSelect dataset (1-{len(datasets)}): ").strip()
                if not choice:
                    raise ValueError("Selection cancelled")

                index = int(choice) - 1
                if 0 <= index < len(datasets):
                    return datasets[index]['id']
                else:
                    print(f"Invalid selection. Please enter 1-{len(datasets)}")
            except (ValueError, KeyboardInterrupt):
                raise ValueError("Dataset selection cancelled")

    def interactive_sheet_select(self, dataset_id: str = None) -> str:
        """
        Interactive sheet selection from list.

        Args:
            dataset_id: Dataset ID (if None, show all sheets in project)

        Returns:
            str: Selected sheet ID

        Raises:
            ValueError: If no sheets found or invalid selection
        """
        sheets = self.sheet_list(dataset_id)
        if not sheets:
            context = f"dataset {dataset_id}" if dataset_id else "this project"
            raise ValueError(f"No datasheets found in {context}")

        print("\nAvailable datasheets:")
        print("=" * 50)
        for i, sheet in enumerate(sheets, 1):
            print(f"{i:2d}. {sheet['name']} (ID: {sheet['id']})")

        while True:
            try:
                choice = input(f"\nSelect datasheet (1-{len(sheets)}): ").strip()
                if not choice:
                    raise ValueError("Selection cancelled")

                index = int(choice) - 1
                if 0 <= index < len(sheets):
                    return sheets[index]['id']
                else:
                    print(f"Invalid selection. Please enter 1-{len(sheets)}")
            except (ValueError, KeyboardInterrupt):
                raise ValueError("Datasheet selection cancelled")

    def ds_get(self, id: Optional[str] = None, name: Optional[str] = None, name_python: Optional[str] = None) -> Dict[str, str]:
        """Get a single dataset by id, name, or name_python.

        Args:
            id: Dataset UUID (highest priority)
            name: Dataset display name (medium priority)
            name_python: Dataset Python name in snake_case (lowest priority, e.g., 'my_sources')

        Returns:
            Dict[str, str]: Dict with keys:
                - id: Dataset UUID
                - name: Dataset display name
                - name_python: Python-safe name (snake_case)

        Raises:
            ValueError: If no search parameter provided, dataset not found, or multiple matches found

        Note:
            Parameter priority: id > name > name_python
            Provide only ONE search parameter
        """
        if not any([id, name, name_python]):
            raise ValueError("At least one search parameter (id, name, or name_python) must be provided")

        try:
            query = (
                self.supabase_client.table("datasets")
                .select("id, name, name_python")
                .eq("project_id", self.project_id)
                .eq("user_owner", self.user_id)
            )

            # Apply filter based on priority
            if id:
                query = query.eq("id", id)
                search_param = f"id '{id}'"
            elif name:
                query = query.eq("name", name)
                search_param = f"name '{name}'"
            else:  # name_python
                query = query.eq("name_python", name_python)
                search_param = f"name_python '{name_python}'"

            response = query.execute()

            if not response.data:
                raise ValueError(f"Dataset with {search_param} not found in this project")

            if len(response.data) > 1:
                raise ValueError(f"Multiple datasets found with {search_param}")

            return response.data[0]

        except Exception as e:
            if "not found" in str(e) or "Multiple datasets" in str(e):
                raise
            raise ValueError(f"Failed to get dataset: {str(e)}")

    def sheet_get(self, dataset_id: Optional[str] = None, id: Optional[str] = None, name: Optional[str] = None, name_python: Optional[str] = None) -> Dict[str, str]:
        """Get a single datasheet by id, name, or name_python.

        Args:
            dataset_id: Dataset UUID to filter by (optional, searches all project datasets if None)
            id: Datasheet UUID (highest priority)
            name: Datasheet display name (medium priority)
            name_python: Datasheet Python name in PascalCase (lowest priority, e.g., 'HpiMasterCsv')

        Returns:
            Dict[str, str]: Dict with keys:
                - id: Datasheet UUID
                - name: Datasheet display name
                - name_python: Python-safe name (PascalCase)
                - dataset_id: Parent dataset UUID

        Raises:
            ValueError: If no search parameter provided, datasheet not found, or multiple matches found

        Note:
            Parameter priority: id > name > name_python
            Provide only ONE search parameter (id, name, or name_python)
        """
        if not any([id, name, name_python]):
            raise ValueError("At least one search parameter (id, name, or name_python) must be provided")

        try:
            query = (
                self.supabase_client.table("datasheets")
                .select("id, name, name_python, dataset_id")
                .eq("user_owner", self.user_id)
            )

            # Apply dataset filter if provided
            if dataset_id:
                query = query.eq("dataset_id", dataset_id)
            else:
                # Filter by project through datasets
                datasets = self.ds_list()
                dataset_ids = [ds['id'] for ds in datasets]
                if not dataset_ids:
                    raise ValueError("No datasets found in project")
                query = query.in_("dataset_id", dataset_ids)

            # Apply search filter based on priority
            if id:
                query = query.eq("id", id)
                search_param = f"id '{id}'"
            elif name:
                query = query.eq("name", name)
                search_param = f"name '{name}'"
            else:  # name_python
                query = query.eq("name_python", name_python)
                search_param = f"name_python '{name_python}'"

            response = query.execute()

            context = f"dataset {dataset_id}" if dataset_id else "this project"
            if not response.data:
                raise ValueError(f"Datasheet with {search_param} not found in {context}")

            if len(response.data) > 1:
                raise ValueError(f"Multiple datasheets found with {search_param} in {context}")

            return response.data[0]

        except Exception as e:
            if "not found" in str(e) or "Multiple datasheets" in str(e) or "No datasets found" in str(e):
                raise
            raise ValueError(f"Failed to get datasheet: {str(e)}")

    def is_mounted(self) -> bool:
        """
        Check if mount point is mounted using rclone.

        Returns:
            bool: True if mounted, False otherwise

        Examples:
            >>> project_service = ProjectService()
            >>> if project_service.is_mounted():
            ...     print("Data directory is mounted")
        """
        # First check if path exists
        if not os.path.exists(self.mount_point):
            return False

        if sys.platform != 'win32':
            return os.path.ismount(self.mount_point)

        try:
            # Windows file attributes
            FILE_ATTRIBUTE_REPARSE_POINT = 0x400
            INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF

            # Get file attributes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(self.mount_point)

            # If attributes are invalid, path doesn't exist or can't be accessed
            if attrs == INVALID_FILE_ATTRIBUTES:
                return False

            # Check if it has reparse point attribute (mount/junction)
            is_reparse = bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)

            return is_reparse

        except Exception as e:
            logger.debug(f"Error checking mount status: {str(e)}")
            return False

    def mount(self) -> bool:
        """
        Mount the project data directory using rclone.

        Mounts the GCS bucket path: oryx-forge-gcs:orxy-forge-datasets-dev/{user_id}/{project_id}
        to the configured mount point using rclone with VFS caching.

        Returns:
            bool: True if mount succeeded, False otherwise

        Raises:
            None: Logs errors but doesn't raise exceptions

        Examples:
            >>> project_service = ProjectService()
            >>> if project_service.mount():
            ...     print("Successfully mounted data directory")
        """
        # Check if already mounted
        if self.is_mounted():
            logger.info(f"Mount point {self.mount_point} is already mounted")
            return True

        # Check that mount point does NOT exist (regardless of platform)
        if os.path.exists(self.mount_point):
            logger.error(f"Mount point {self.mount_point} already exists, unable to mount here")
            return False

        # Construct GCS path
        gcs_path = f"oryx-forge-gcs:orxy-forge-datasets-dev/{self.user_id}/{self.project_id}"

        if sys.platform == 'win32':
            # Windows-specific mounting using PowerShell
            # Use Start-Process with -PassThru and immediately exit, don't wait for rclone
            ps_cmd = f'''Start-Process -FilePath "rclone" -ArgumentList "mount","{gcs_path}","{self.mount_point}","--vfs-cache-mode","writes","--vfs-cache-max-age","24h","--log-file",".rclone.log" -WindowStyle Hidden -PassThru | Out-Null'''

            try:
                logger.info(f"Mounting {gcs_path} to {self.mount_point}...")
                result = subprocess.run(
                    ['powershell', '-Command', ps_cmd],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode != 0:
                    logger.error(f"PowerShell mount command failed: {result.stderr}")
                    return False

                # Wait for mount to initialize
                time.sleep(5)

                # Verify mount succeeded by checking if directory now exists
                if os.path.exists(self.mount_point):
                    logger.success(f"Successfully mounted {self.mount_point}")
                    return True
                else:
                    logger.error(f"Mount failed: directory {self.mount_point} does not exist after mount")
                    logger.error(f"Command: {ps_cmd}")
                    logger.error(f"Check .rclone.log for error details")
                    return False

            except subprocess.TimeoutExpired:
                logger.error("rclone mount command timed out")
                return False
            except FileNotFoundError:
                logger.error("PowerShell or rclone command not found")
                return False
            except Exception as e:
                logger.error(f"Error mounting directory: {str(e)}")
                return False

        else:
            # Linux/macOS: Use standard daemon mode
            cmd = [
                'rclone', 'mount',
                gcs_path,
                self.mount_point,
                '--vfs-cache-mode', 'writes',
                '--vfs-cache-max-age', '24h',
                '--daemon'
            ]

            try:
                logger.info(f"Mounting {gcs_path} to {self.mount_point}...")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode != 0:
                    logger.error(f"rclone mount failed: {result.stderr}")
                    return False

                # Wait for daemon to initialize
                time.sleep(2)

                # Verify mount succeeded
                if self.is_mounted():
                    logger.success(f"Successfully mounted {self.mount_point}")
                    return True
                else:
                    logger.error(f"Mount command succeeded but directory is not mounted")
                    return False

            except subprocess.TimeoutExpired:
                logger.error("rclone mount command timed out")
                return False
            except FileNotFoundError:
                logger.error("rclone command not found. Please ensure rclone is installed and in your PATH")
                return False
            except Exception as e:
                logger.error(f"Error mounting directory: {str(e)}")
                return False

    def unmount(self, forced:bool = False) -> bool:
        """
        Unmount the project data directory.

        Uses platform-specific unmount commands:
        - Windows: taskkill /F /IM rclone.exe
        - Linux: fusermount -u
        - macOS: umount

        Returns:
            bool: True if unmount succeeded, False otherwise

        Examples:
            >>> project_service = ProjectService()
            >>> if project_service.unmount():
            ...     print("Successfully unmounted data directory")
        """
        # Check if already unmounted
        if not forced and not self.is_mounted():
            logger.info(f"Mount point {self.mount_point} is not mounted")
            return True

        system = platform.system()

        try:
            if system == "Windows":
                # Windows: Kill all rclone processes
                cmd = ['taskkill', '/F', '/IM', 'rclone.exe']
            elif system == "Linux":
                cmd = ['fusermount', '-u', self.mount_point]
            elif system == "Darwin":  # macOS
                cmd = ['umount', self.mount_point]
            else:
                logger.error(f"Unsupported platform: {system}")
                return False

            logger.info(f"Unmounting {self.mount_point}...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                logger.success(f"Successfully unmounted {self.mount_point}")
                return True
            else:
                # On Windows, taskkill returns error if no process found, which is OK
                if system == "Windows" and "not found" in result.stderr.lower():
                    logger.info(f"No rclone process found (already unmounted)")
                    return True
                logger.error(f"Unmount failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Unmount command timed out")
            return False
        except FileNotFoundError:
            logger.error(f"Unmount command not found for platform: {system}")
            return False
        except Exception as e:
            logger.error(f"Error unmounting directory: {str(e)}")
            return False

    def ensure_mount(self) -> None:
        """
        Ensure the data directory is mounted, mounting if necessary.

        Checks if the mount point is already mounted. If not, attempts to mount it.
        Raises an error if mounting fails.

        Raises:
            ValueError: If mount fails

        Examples:
            >>> project_service = ProjectService()
            >>> project_service.ensure_mount()  # Ensures data directory is accessible
        """
        if not self.is_mounted():
            logger.info(f"Data directory not mounted, attempting to mount...")
            if not self.mount():
                raise ValueError(
                    f"Failed to mount data directory at {self.mount_point}. "
                    f"Please check that rclone is installed and configured correctly."
                )

        logger.success(f"Data directory mounted successfully at {self.mount_point}")



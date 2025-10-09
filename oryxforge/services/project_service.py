"""Project Service for managing datasets, datasheets, and project operations."""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import gcsfs
from supabase import Client
from loguru import logger
from .workflow_service import WorkflowService
from .repo_service import RepoService
from .utils import init_supabase_client
from .iam import CredentialsManager


class ProjectService:
    """
    Service class for project-level operations including datasets, datasheets, and git operations.
    """

    def __init__(self, project_id: Optional[str] = None, user_id: Optional[str] = None, working_dir: Optional[str] = None):
        """
        Initialize project service.

        Gets user_id and project_id from CredentialsManager if not provided.

        Args:
            project_id: Project ID (if None, read from profile)
            user_id: User ID (if None, read from profile)
            working_dir: Working directory for CredentialsManager (if None, use current directory)

        Raises:
            ValueError: If project doesn't exist or profile is not configured
        """
        # Get profile from CredentialsManager if not provided
        if project_id is None or user_id is None:
            creds_manager = CredentialsManager(working_dir=working_dir)
            profile = creds_manager.get_profile()
            self.project_id = project_id or profile['project_id']
            self.user_id = user_id or profile['user_id']
        else:
            self.project_id = project_id
            self.user_id = user_id

        # Initialize Supabase client
        self.supabase_client = init_supabase_client()

        # Validate project exists and belongs to user
        self._validate_project()

        # Initialize GCS filesystem for datasheet operations
        try:
            self.gcs = gcsfs.GCSFileSystem()
            self.gcs_bucket = "orxy-forge-datasets-dev"
        except Exception as e:
            logger.warning(f"Failed to initialize GCS filesystem: {str(e)}")
            self.gcs = None

        # Initialize workflow service for name sanitization
        self.workflow_service = WorkflowService()

    def _validate_project(self) -> None:
        """Validate that project exists and belongs to user."""
        try:
            response = (
                self.supabase_client.table("projects")
                .select("id, name")
                .eq("id", self.project_id)
                .eq("user_owner", self.user_id)
                .execute()
            )
            if not response.data:
                raise ValueError(f"Project {self.project_id} not found or access denied")

            self.project_name = response.data[0]['name']
            logger.debug(f"Validated project: {self.project_name}")

        except Exception as e:
            raise ValueError(f"Failed to validate project: {str(e)}")

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
                    repo_service = RepoService(project_id, str(Path.cwd()))
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

    def ds_create(self, name: str) -> str:
        """Create a new dataset in the current project.

        The name will be automatically converted to a Python-safe name_python (snake_case).

        Args:
            name: Dataset display name (e.g., 'My Data Sources')
                  Must be unique for user/project

        Returns:
            str: Created dataset UUID

        Raises:
            ValueError: If dataset name already exists for this user/project
        """
        try:
            response = (
                self.supabase_client.table("datasets")
                .insert({
                    "name": name,
                    "user_owner": self.user_id,
                    "project_id": self.project_id
                })
                .execute()
            )

            if not response.data:
                raise ValueError("Failed to create dataset")

            dataset_id = response.data[0]['id']
            logger.success(f"Created dataset '{name}' with ID: {dataset_id}")
            return dataset_id

        except Exception as e:
            if "unique_user_dataset_name" in str(e):
                raise ValueError(f"Dataset '{name}' already exists in this project")
            raise ValueError(f"Failed to create dataset: {str(e)}")

    def sheet_create(self, dataset_id: str, name: str) -> Dict[str, str]:
        """Create a new datasheet in the specified dataset.

        The name will be automatically converted to a Python-safe name_python (PascalCase).

        Uses upsert to handle idempotent operations - if a sheet with the same
        (user_owner, dataset_id, name) already exists, returns the existing sheet data.

        Args:
            dataset_id: Dataset UUID
            name: Datasheet display name (e.g., 'HPI Master CSV')

        Returns:
            Dict[str, str]: Dict with keys:
                - id: Datasheet UUID
                - name: Datasheet display name
                - name_python: Python-safe name (PascalCase)
                - dataset_id: Parent dataset UUID

        Raises:
            ValueError: If dataset doesn't exist
        """
        # Validate dataset exists and belongs to user
        if not self.ds_exists(dataset_id):
            raise ValueError(f"Dataset {dataset_id} not found or access denied")

        try:
            response = (
                self.supabase_client.table("datasheets")
                .upsert({
                    "name": name,
                    "user_owner": self.user_id,
                    "dataset_id": dataset_id
                },
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

    def project_init(self) -> None:
        """Initialize project by ensuring git repository exists locally.

        Clones the repository if not present, pulls latest changes if it exists.

        Raises:
            ValueError: If git operations fail
        """
        try:
            repo_service = RepoService(self.project_id, str(Path.cwd()))

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
            repo_service = RepoService(self.project_id, str(Path.cwd()))
            return repo_service.repo_exists()
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


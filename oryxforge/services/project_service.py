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


class ProjectService:
    """
    Service class for project-level operations including datasets, datasheets, and git operations.
    """

    def __init__(self, project_id: str, user_id: str):
        """
        Initialize project service.

        Args:
            project_id: Project ID
            user_id: User ID

        Raises:
            ValueError: If project doesn't exist or isn't initialized
        """
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
        """
        Create a new project with optional repository setup.

        Args:
            name: Project name (must be unique for user)
            user_id: User ID who owns the project
            setup_repo: Whether to create GitLab repository (default: True)

        Returns:
            str: Created project ID

        Raises:
            ValueError: If project creation or repository setup fails
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
        """
        List all datasets for the current project.

        Returns:
            List of dicts with dataset id, name, and name_python
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
        """
        Create a new dataset in the current project.

        Args:
            name: Dataset name (must be unique for user/project)

        Returns:
            str: Created dataset ID

        Raises:
            ValueError: If dataset name already exists
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

    def sheet_create(self, dataset_id: str, name: str) -> str:
        """
        Create a new datasheet in the specified dataset.

        Args:
            dataset_id: Dataset ID
            name: Datasheet name (must be unique for user/dataset)

        Returns:
            str: Created datasheet ID

        Raises:
            ValueError: If dataset doesn't exist or datasheet name already exists
        """
        # Validate dataset exists and belongs to user
        if not self.ds_exists(dataset_id):
            raise ValueError(f"Dataset {dataset_id} not found or access denied")

        try:
            response = (
                self.supabase_client.table("datasheets")
                .insert({
                    "name": name,
                    "user_owner": self.user_id,
                    "dataset_id": dataset_id
                })
                .execute()
            )

            if not response.data:
                raise ValueError("Failed to create datasheet")

            sheet_id = response.data[0]['id']
            logger.success(f"Created datasheet '{name}' with ID: {sheet_id}")
            return sheet_id

        except Exception as e:
            if "unique_user_dataset_datasheet_name" in str(e):
                raise ValueError(f"Datasheet '{name}' already exists in this dataset")
            raise ValueError(f"Failed to create datasheet: {str(e)}")

    def sheet_list(self, dataset_id: str = None) -> List[Dict[str, str]]:
        """
        List datasheets for specified dataset or all datasets in project.

        Args:
            dataset_id: Dataset ID (if None, list all datasheets in project)

        Returns:
            List of dicts with datasheet id, name, name_python, and dataset_id
        """
        try:
            query = (
                self.supabase_client.table("datasheets")
                .select("id, name, name_python, dataset_id")
                .eq("user_owner", self.user_id)
            )

            if dataset_id:
                query = query.eq("dataset_id", dataset_id)
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
        """
        Initialize project with git repository using RepoService.

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
        """
        Check if dataset exists and belongs to current user/project.

        Args:
            dataset_id: Dataset ID to check

        Returns:
            bool: True if dataset exists
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
        """
        Check if datasheet exists and belongs to current user.

        Args:
            sheet_id: Datasheet ID to check

        Returns:
            bool: True if datasheet exists
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

    def find_dataset_by_name(self, name: str) -> str:
        """
        Find dataset ID by name within current project.

        Args:
            name: Dataset name

        Returns:
            str: Dataset ID

        Raises:
            ValueError: If dataset not found
        """
        try:
            response = (
                self.supabase_client.table("datasets")
                .select("id")
                .eq("project_id", self.project_id)
                .eq("user_owner", self.user_id)
                .eq("name", name)
                .execute()
            )
            if not response.data:
                raise ValueError(f"Dataset '{name}' not found in this project")
            return response.data[0]['id']
        except Exception as e:
            raise ValueError(f"Failed to find dataset '{name}': {str(e)}")

    def find_sheet_by_name(self, name: str, dataset_id: str = None) -> str:
        """
        Find sheet ID by name.

        Args:
            name: Datasheet name
            dataset_id: Dataset ID (if None, search all datasets in project)

        Returns:
            str: Datasheet ID

        Raises:
            ValueError: If datasheet not found
        """
        try:
            query = (
                self.supabase_client.table("datasheets")
                .select("id")
                .eq("user_owner", self.user_id)
                .eq("name", name)
            )

            if dataset_id:
                query = query.eq("dataset_id", dataset_id)
            else:
                # Filter by project through datasets
                datasets = self.ds_list()
                dataset_ids = [ds['id'] for ds in datasets]
                if not dataset_ids:
                    raise ValueError(f"No datasets found in project")
                query = query.in_("dataset_id", dataset_ids)

            response = query.execute()
            if not response.data:
                context = f"dataset {dataset_id}" if dataset_id else "this project"
                raise ValueError(f"Datasheet '{name}' not found in {context}")

            return response.data[0]['id']

        except Exception as e:
            raise ValueError(f"Failed to find datasheet '{name}': {str(e)}")

    def get_dataset_by_id(self, dataset_id: str) -> Dict[str, str]:
        """
        Get dataset information by ID.

        Args:
            dataset_id: Dataset ID

        Returns:
            Dict with id, name, and name_python fields

        Raises:
            ValueError: If dataset not found or access denied
        """
        try:
            response = (
                self.supabase_client.table("datasets")
                .select("id, name, name_python")
                .eq("id", dataset_id)
                .eq("project_id", self.project_id)
                .eq("user_owner", self.user_id)
                .execute()
            )
            if not response.data:
                raise ValueError(f"Dataset {dataset_id} not found or access denied")
            return response.data[0]
        except Exception as e:
            raise ValueError(f"Failed to get dataset by ID: {str(e)}")

    def get_dataset_by_name_python(self, name_python: str) -> Dict[str, str]:
        """
        Get dataset information by name_python.

        Args:
            name_python: Dataset Python-safe name

        Returns:
            Dict with id, name, and name_python fields

        Raises:
            ValueError: If dataset not found
        """
        try:
            response = (
                self.supabase_client.table("datasets")
                .select("id, name, name_python")
                .eq("project_id", self.project_id)
                .eq("user_owner", self.user_id)
                .eq("name_python", name_python)
                .execute()
            )
            if not response.data:
                raise ValueError(f"Dataset with name_python '{name_python}' not found in this project")
            return response.data[0]
        except Exception as e:
            raise ValueError(f"Failed to get dataset by name_python: {str(e)}")

    def get_sheet_by_id(self, sheet_id: str) -> Dict[str, str]:
        """
        Get datasheet information by ID.

        Args:
            sheet_id: Datasheet ID

        Returns:
            Dict with id, name, name_python, and dataset_id fields

        Raises:
            ValueError: If datasheet not found or access denied
        """
        try:
            response = (
                self.supabase_client.table("datasheets")
                .select("id, name, name_python, dataset_id")
                .eq("id", sheet_id)
                .eq("user_owner", self.user_id)
                .execute()
            )
            if not response.data:
                raise ValueError(f"Datasheet {sheet_id} not found or access denied")
            return response.data[0]
        except Exception as e:
            raise ValueError(f"Failed to get datasheet by ID: {str(e)}")

    def get_sheet_by_name_python(self, name_python: str, dataset_id: str = None) -> Dict[str, str]:
        """
        Get datasheet information by name_python.

        Args:
            name_python: Datasheet Python-safe name
            dataset_id: Dataset ID (if None, search all datasets in project)

        Returns:
            Dict with id, name, name_python, and dataset_id fields

        Raises:
            ValueError: If datasheet not found
        """
        try:
            query = (
                self.supabase_client.table("datasheets")
                .select("id, name, name_python, dataset_id")
                .eq("user_owner", self.user_id)
                .eq("name_python", name_python)
            )

            if dataset_id:
                query = query.eq("dataset_id", dataset_id)
            else:
                # Filter by project through datasets
                datasets = self.ds_list()
                dataset_ids = [ds['id'] for ds in datasets]
                if not dataset_ids:
                    raise ValueError(f"No datasets found in project")
                query = query.in_("dataset_id", dataset_ids)

            response = query.execute()
            if not response.data:
                context = f"dataset {dataset_id}" if dataset_id else "this project"
                raise ValueError(f"Datasheet with name_python '{name_python}' not found in {context}")

            return response.data[0]

        except Exception as e:
            raise ValueError(f"Failed to get datasheet by name_python: {str(e)}")
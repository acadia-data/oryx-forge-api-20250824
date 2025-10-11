"""IO Service for saving and loading DataFrames as parquet files."""

from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
from loguru import logger

from .project_service import ProjectService


class IOService:
    """
    Service class for DataFrame I/O operations.

    Handles saving and loading pandas DataFrames as parquet files,
    with automatic dataset/sheet metadata management.
    """

    def __init__(self, project_id: Optional[str] = None, user_id: Optional[str] = None, working_dir: Optional[str] = None):
        """
        Initialize IO Service.

        Gets user_id and project_id from CredentialsManager if not provided.

        Args:
            project_id: Project ID (if None, read from profile)
            user_id: User ID (if None, read from profile)
            working_dir: Working directory for CredentialsManager (if None, use current directory)

        Raises:
            ValueError: If project doesn't exist or profile is not configured
        """
        self.ps = ProjectService(project_id=project_id, user_id=user_id, working_dir=working_dir)

    def save_df_pd(self, df: pd.DataFrame, sheet_name: str, dataset_name: str = 'Exploration') -> Dict[str, Any]:
        """
        Save a pandas DataFrame as a parquet file.

        Creates dataset and sheet records if they don't exist, then saves the DataFrame
        to data/.exploration/{dataset_name_python}/{sheet_name_python}.parquet

        Args:
            df: pandas DataFrame to save
            sheet_name: Display name for the sheet (e.g., 'HPI Master')
            dataset_name: Display name for the dataset (default: 'Exploration')

        Returns:
            Dict with keys:
                - message: Success message
                - dataset_id: Dataset UUID
                - dataset_name_python: Python-safe dataset name
                - sheet_id: Sheet UUID
                - sheet_name_python: Python-safe sheet name
                - path: Path where parquet file was saved
                - shape: Tuple of (rows, columns)

        Raises:
            ValueError: If DataFrame is empty or save operation fails
        """
        # Validate DataFrame
        if df.empty:
            raise ValueError("Cannot save empty DataFrame")

        try:
            # Get or create dataset
            dataset = self.ps.ds_create_get(name=dataset_name)
            logger.debug(f"Using dataset: {dataset['name_python']} (ID: {dataset['id']})")

            # Create or get sheet
            sheet = self.ps.sheet_create(dataset_id=dataset['id'], name=sheet_name)
            logger.debug(f"Using sheet: {sheet['name_python']} (ID: {sheet['id']})")

            # Build parquet path
            path = Path(f"data/.exploration/{dataset['name_python']}/{sheet['name_python']}.parquet")

            # Create directory if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            # Save DataFrame
            df.to_parquet(path, engine='pyarrow')
            logger.success(f"Saved DataFrame to {path} (shape: {df.shape})")

            return {
                'message': 'DataFrame saved successfully',
                'dataset_id': dataset['id'],
                'dataset_name_python': dataset['name_python'],
                'sheet_id': sheet['id'],
                'sheet_name_python': sheet['name_python'],
                'path': str(path),
                'shape': df.shape
            }

        except Exception as e:
            logger.error(f"Failed to save DataFrame: {str(e)}")
            raise ValueError(f"Failed to save DataFrame: {str(e)}")

    def load_df_pd(self, name_python: str) -> pd.DataFrame:
        """
        Load a pandas DataFrame from a parquet file.

        Uses dataset.sheet notation to locate the parquet file at
        data/.exploration/{dataset_name_python}/{sheet_name_python}.parquet

        Args:
            name_python: Combined dataset.sheet name (e.g., 'exploration.HpiMaster')

        Returns:
            pandas DataFrame loaded from parquet file

        Raises:
            ValueError: If dataset/sheet combination not found or file doesn't exist
        """
        try:
            # Get dataset and sheet metadata
            record = self.ps.ds_sheet_get(name_python)

            dataset_name_python = record['dataset']['name_python']
            sheet_name_python = record['sheet']['name_python']

            # Build parquet path
            path = Path(f"data/.exploration/{dataset_name_python}/{sheet_name_python}.parquet")

            # Validate file exists
            if not path.exists():
                raise ValueError(
                    f"Parquet file not found at {path}. "
                    f"Make sure the DataFrame has been saved using save_df_pd() first."
                )

            # Load DataFrame
            df = pd.read_parquet(path, engine='pyarrow')
            logger.success(f"Loaded DataFrame from {path} (shape: {df.shape})")

            return df

        except Exception as e:
            if "not found" in str(e):
                raise
            logger.error(f"Failed to load DataFrame: {str(e)}")
            raise ValueError(f"Failed to load DataFrame: {str(e)}")

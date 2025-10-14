"""IO Service for saving and loading DataFrames as parquet files and Plotly charts."""

from pathlib import Path
from typing import Dict, Any, Optional, Union, Callable
import pandas as pd
from loguru import logger
import importlib

from .project_service import ProjectService


class IOService:
    """
    Service class for DataFrame, Plotly chart, and Markdown I/O operations.

    Handles saving and loading:
    - DataFrames as parquet files
    - Plotly charts as HTML files with CDN
    - Markdown documents as .md files

    All with automatic dataset/sheet metadata management.
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

    def _build_relative_uri(self, dataset_name_python: str, sheet_name_python: str, extension: str) -> str:
        """
        Build relative URI for storing in database.

        Returns a portable relative path without mount point prefix.

        Args:
            dataset_name_python: Python-safe dataset name (snake_case)
            sheet_name_python: Python-safe sheet name (PascalCase)
            extension: File extension (e.g., 'parquet', 'html', 'md')

        Returns:
            str: Relative URI (e.g., 'exploration/MySheet.parquet')

        Examples:
            >>> _build_relative_uri('exploration', 'MySheet', 'parquet')
            'exploration/MySheet.parquet'
        """
        return f"{dataset_name_python}/{sheet_name_python}.{extension}"

    def _normalize_uri(self, uri: str) -> str:
        """
        Normalize URI to remove legacy 'data/' prefix if present.

        Provides backward compatibility with old URIs that had 'data/' prefix.

        Args:
            uri: URI from database (may have 'data/' prefix)

        Returns:
            str: Normalized URI without 'data/' prefix

        Examples:
            >>> _normalize_uri('data/exploration/MySheet.parquet')
            'exploration/MySheet.parquet'
            >>> _normalize_uri('exploration/MySheet.parquet')
            'exploration/MySheet.parquet'
        """
        if uri.startswith('data/') or uri.startswith('data\\'):
            return uri[5:]  # Strip 'data/' or 'data\\'
        return uri

    def _resolve_full_path(self, uri: str) -> Path:
        """
        Resolve relative URI to full file system path using mount point.

        Normalizes URI first to handle legacy 'data/' prefix, then prepends mount point.

        Args:
            uri: Relative URI from database

        Returns:
            Path: Full file system path

        Examples:
            >>> # If mount_point = './data'
            >>> _resolve_full_path('exploration/MySheet.parquet')
            Path('./data/exploration/MySheet.parquet')
            >>> # Handles legacy URIs
            >>> _resolve_full_path('data/exploration/MySheet.parquet')
            Path('./data/exploration/MySheet.parquet')
        """
        normalized = self._normalize_uri(uri)
        return self.ps.mount_point_path / normalized

    def _get_uri_from_record(self, name_python: str, file_type: str) -> Path:
        """
        Get full file path from sheet's uri column.

        Retrieves URI from database and resolves it to full file system path.

        Args:
            name_python: Combined dataset.sheet name (e.g., 'exploration.HpiMaster')
            file_type: Type of file for error messages (e.g., 'DataFrame', 'chart', 'markdown')

        Returns:
            Path: Full file system path

        Raises:
            ValueError: If sheet not found or uri not set
        """
        record = self.ps.ds_sheet_get(name_python)
        uri = record['sheet'].get('uri')
        if not uri:
            raise ValueError(
                f"No uri found for sheet {name_python}. "
                f"Make sure the {file_type} has been saved first."
            )
        return self._resolve_full_path(uri)

    def _validate_exploration_dataset(self, dataset_name: str) -> None:
        """
        Validate that dataset is 'exploration'.

        Only exploration datasets can be saved directly. Non-exploration datasets
        should be created using d6tflow tasks.

        Args:
            dataset_name: Dataset display name to validate

        Raises:
            ValueError: If dataset is not 'exploration'
        """
        if dataset_name.lower() != 'exploration':
            raise ValueError(
                f"Cannot save to dataset '{dataset_name}'. "
                f"Only 'Exploration' dataset can be saved directly. "
                f"Non-exploration datasets should be created using d6tflow tasks."
            )

    def _save_file_base(
        self,
        sheet_name: str,
        dataset_name: str,
        extension: str,
        save_callback: Callable[[Path], None],
        sheet_type: str = 'table',
        extra_return_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Base save operation for files (DRY helper for all save methods).

        Handles common logic: validation, dataset/sheet creation, path building,
        directory creation, and calling the specific save callback.

        Args:
            sheet_name: Display name for the sheet (e.g., 'HPI Master')
            dataset_name: Display name for the dataset (default: 'Exploration')
            extension: File extension (e.g., 'parquet', 'html', 'md')
            save_callback: Function that takes Path and saves the file
            sheet_type: Type of sheet (default: 'table', can be 'chart', 'report')
            extra_return_data: Optional extra data to include in return dict

        Returns:
            Dict with keys:
                - message: Success message
                - dataset_id: Dataset UUID
                - dataset_name_python: Python-safe dataset name
                - sheet_id: Sheet UUID
                - sheet_name_python: Python-safe sheet name
                - path: Path where file was saved
                - ...plus any keys from extra_return_data

        Raises:
            ValueError: If dataset validation or save operation fails
        """
        try:
            # Validate dataset name
            self._validate_exploration_dataset(dataset_name)

            # Get or create dataset
            dataset = self.ps.ds_create_get(name=dataset_name)
            logger.debug(f"Using dataset: {dataset['name_python']} (ID: {dataset['id']})")

            # Build relative URI for database and full path for file system
            relative_uri = self._build_relative_uri(dataset['name_python'], sheet_name, extension)
            full_path = self._resolve_full_path(relative_uri)

            # Create or get sheet with uri in metadata
            sheet = self.ps.sheet_create(
                dataset_id=dataset['id'],
                name=sheet_name,
                type=sheet_type,
                metadata={'uri': relative_uri}
            )
            logger.debug(f"Using sheet: {sheet['name_python']} (ID: {sheet['id']})")

            # Create directory if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Call specific save logic
            save_callback(full_path)
            logger.success(f"Saved {extension} file to {full_path}")

            # Build return dict
            result = {
                'message': f'{extension.upper()} file saved successfully',
                'dataset_id': dataset['id'],
                'dataset_name_python': dataset['name_python'],
                'sheet_id': sheet['id'],
                'sheet_name_python': sheet['name_python'],
                'path': str(full_path)
            }

            # Add extra data if provided
            if extra_return_data:
                result.update(extra_return_data)

            return result

        except Exception as e:
            logger.error(f"Failed to save {extension} file: {str(e)}")
            raise ValueError(f"Failed to save {extension} file: {str(e)}")

    def _load_file_base(
        self,
        name_python: str,
        file_type: str,
        load_callback: Callable[[Path], Any]
    ) -> Any:
        """
        Base load operation for files (DRY helper for all load methods).

        Handles common logic: exploration check, path resolution, file validation,
        and calling the specific load callback.

        Args:
            name_python: Combined dataset.sheet name (e.g., 'exploration.HpiMaster')
            file_type: Type of file for error messages (e.g., 'DataFrame', 'chart', 'markdown')
            load_callback: Function that takes Path and returns loaded data

        Returns:
            Data returned by load_callback (or task output for non-exploration datasets)

        Raises:
            ValueError: If dataset/sheet combination not found or file doesn't exist
        """
        # If not exploration dataset, delegate to load_task
        if not name_python.startswith('exploration.'):
            logger.debug(f"Non-exploration dataset detected, using load_task for {name_python}")
            return self.load_task(name_python)

        try:
            # Get full path from uri
            path = self._get_uri_from_record(name_python, file_type)

            # Validate file exists
            if not path.exists():
                raise ValueError(
                    f"{file_type.capitalize()} file not found at {path}. "
                    f"Make sure the {file_type} has been saved first."
                )

            # Load file using callback
            result = load_callback(path)
            logger.success(f"Loaded {file_type} from {path}")

            return result

        except Exception as e:
            if "not found" in str(e):
                raise
            logger.error(f"Failed to load {file_type}: {str(e)}")
            raise ValueError(f"Failed to load {file_type}: {str(e)}")

    def _delete_file_and_sheet(self, name_python: str, file_type: str) -> Dict[str, Any]:
        """
        Delete file and sheet metadata.

        DRY function to handle deletion of file and database record.

        Args:
            name_python: Combined dataset.sheet name (e.g., 'exploration.HpiMaster')
            file_type: Type of file for log messages (e.g., 'parquet', 'HTML', 'markdown')

        Returns:
            Dict with deletion status information

        Raises:
            ValueError: If sheet not found
        """
        # Get dataset and sheet metadata
        record = self.ps.ds_sheet_get(name_python)

        dataset_name_python = record['dataset']['name_python']
        sheet_name_python = record['sheet']['name_python']
        sheet_id = record['sheet']['id']

        # Get path from uri column and resolve to full path
        uri = record['sheet'].get('uri')

        # Delete file if uri exists and file exists
        file_deleted = False
        if uri:
            path = self._resolve_full_path(uri)
            if path.exists():
                path.unlink()
                logger.success(f"Deleted {file_type} file: {path}")
                file_deleted = True
            else:
                logger.warning(f"{file_type.capitalize()} file not found: {path}")
        else:
            logger.warning(f"No uri found for sheet {name_python}")

        # Delete sheet metadata from database
        self.ps.supabase_client.table("datasheets").delete().eq("id", sheet_id).execute()
        logger.success(f"Deleted sheet db entry: {sheet_id}")

        return {
            'file_deleted': file_deleted,
            'sheet_deleted': True,
            'dataset_name_python': dataset_name_python,
            'sheet_name_python': sheet_name_python
        }

    def save_df_pd(self, df: pd.DataFrame, sheet_name: str, dataset_name: str = 'Exploration') -> Dict[str, Any]:
        """
        Save a pandas DataFrame as a parquet file.

        Creates dataset and sheet records if they don't exist, then saves the DataFrame
        to {mount_point}/{dataset_name_python}/{sheet_name_python}.parquet

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
            ValueError: If DataFrame is empty, dataset is not 'Exploration', or save operation fails
        """
        # Validate DataFrame
        if df.empty:
            raise ValueError("Cannot save empty DataFrame")

        # Define save callback
        def save_parquet(path: Path) -> None:
            df.to_parquet(path, engine='pyarrow')

        # Use base save method
        result = self._save_file_base(
            sheet_name=sheet_name,
            dataset_name=dataset_name,
            extension='parquet',
            save_callback=save_parquet,
            sheet_type='table',
            extra_return_data={'shape': df.shape}
        )

        # Update message to be more specific
        result['message'] = 'DataFrame saved successfully'
        return result

    def load_df_pd(self, name_python: str) -> pd.DataFrame:
        """
        Load a pandas DataFrame from a parquet file or d6tflow task.

        Uses dataset.sheet notation. If the name starts with 'exploration.',
        reads the file path from the sheet's uri column. Otherwise, uses
        load_task() to execute a d6tflow task.

        Args:
            name_python: Combined dataset.sheet name (e.g., 'exploration.HpiMaster')

        Returns:
            pandas DataFrame loaded from parquet file or task output

        Raises:
            ValueError: If dataset/sheet combination not found or file doesn't exist
        """
        # Define load callback
        def load_parquet(path: Path) -> pd.DataFrame:
            return pd.read_parquet(path, engine='pyarrow')

        # Use base load method
        return self._load_file_base(
            name_python=name_python,
            file_type="DataFrame",
            load_callback=load_parquet
        )

    def delete_df(self, name_python: str) -> Dict[str, Any]:
        """
        Delete a DataFrame and its metadata.

        Deletes both the parquet file and the sheet record from the database.

        Args:
            name_python: Combined dataset.sheet name (e.g., 'exploration.HpiMaster')

        Returns:
            Dict with keys:
                - message: Success message
                - file_deleted: Whether file was found and deleted
                - sheet_deleted: Whether sheet metadata was deleted
                - dataset_name_python: Dataset name
                - sheet_name_python: Sheet name

        Raises:
            ValueError: If dataset/sheet combination not found in database
        """
        try:
            result = self._delete_file_and_sheet(name_python, "parquet")
            result['message'] = 'DataFrame deleted successfully'
            return result

        except Exception as e:
            if "not found" in str(e):
                raise
            logger.error(f"Failed to delete DataFrame: {str(e)}")
            raise ValueError(f"Failed to delete DataFrame: {str(e)}")

    def save_chart_plotly(self, fig, sheet_name: str, dataset_name: str = 'Exploration') -> Dict[str, Any]:
        """
        Save a Plotly figure as an HTML file.

        Creates dataset and sheet records if they don't exist, then saves the figure
        to {mount_point}/{dataset_name_python}/{sheet_name_python}.html with CDN mode.

        Args:
            fig: Plotly figure object (go.Figure)
            sheet_name: Display name for the sheet (e.g., 'Sales Trends')
            dataset_name: Display name for the dataset (default: 'Exploration')

        Returns:
            Dict with keys:
                - message: Success message
                - dataset_id: Dataset UUID
                - dataset_name_python: Python-safe dataset name
                - sheet_id: Sheet UUID
                - sheet_name_python: Python-safe sheet name
                - path: Path where HTML file was saved

        Raises:
            ValueError: If dataset is not 'Exploration' or save operation fails
        """
        # Define save callback
        def save_html(path: Path) -> None:
            fig.write_html(path, include_plotlyjs='cdn')

        # Use base save method
        result = self._save_file_base(
            sheet_name=sheet_name,
            dataset_name=dataset_name,
            extension='html',
            save_callback=save_html,
            sheet_type='chart'
        )

        # Update message to be more specific
        result['message'] = 'Chart saved successfully'
        return result

    def load_chart_plotly(self, name_python: str, return_html: bool = False) -> Union[str, Dict[str, str], Any]:
        """
        Load a Plotly chart HTML file or d6tflow task output.

        Uses dataset.sheet notation. If the name starts with 'exploration.',
        reads the file path from the sheet's uri column. Otherwise, uses
        load_task() to execute a d6tflow task.

        Args:
            name_python: Combined dataset.sheet name (e.g., 'exploration.SalesTrends')
            return_html: If True, return HTML content as string; if False, return path only (default: False)
                        Note: Only applicable for exploration datasets

        Returns:
            If return_html=False: str path to HTML file
            If return_html=True: Dict with keys:
                - path: Path to HTML file
                - html_content: HTML content as string
            If non-exploration dataset: Output from d6tflow task

        Raises:
            ValueError: If dataset/sheet combination not found or file doesn't exist
        """
        # Define load callback
        def load_html(path: Path) -> Union[str, Dict[str, str]]:
            if return_html:
                with open(path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                return {
                    'path': str(path),
                    'html_content': html_content
                }
            else:
                return str(path)

        # Use base load method
        return self._load_file_base(
            name_python=name_python,
            file_type="chart",
            load_callback=load_html
        )

    def delete_chart(self, name_python: str) -> Dict[str, Any]:
        """
        Delete a Plotly chart and its metadata.

        Deletes both the HTML file and the sheet record from the database.

        Args:
            name_python: Combined dataset.sheet name (e.g., 'exploration.SalesTrends')

        Returns:
            Dict with keys:
                - message: Success message
                - file_deleted: Whether file was found and deleted
                - sheet_deleted: Whether sheet metadata was deleted
                - dataset_name_python: Dataset name
                - sheet_name_python: Sheet name

        Raises:
            ValueError: If dataset/sheet combination not found in database
        """
        try:
            result = self._delete_file_and_sheet(name_python, "HTML")
            result['message'] = 'Chart deleted successfully'
            return result

        except Exception as e:
            if "not found" in str(e):
                raise
            logger.error(f"Failed to delete chart: {str(e)}")
            raise ValueError(f"Failed to delete chart: {str(e)}")

    def save_markdown(self, content: str, sheet_name: str, dataset_name: str = 'Exploration') -> Dict[str, Any]:
        """
        Save markdown content as a .md file.

        Creates dataset and sheet records if they don't exist, then saves the content
        to {mount_point}/{dataset_name_python}/{sheet_name_python}.md

        Args:
            content: Markdown content as string
            sheet_name: Display name for the sheet (e.g., 'Analysis Notes')
            dataset_name: Display name for the dataset (default: 'Exploration')

        Returns:
            Dict with keys:
                - message: Success message
                - dataset_id: Dataset UUID
                - dataset_name_python: Python-safe dataset name
                - sheet_id: Sheet UUID
                - sheet_name_python: Python-safe sheet name
                - path: Path where markdown file was saved
                - length: Length of content in characters

        Raises:
            ValueError: If content is empty, dataset is not 'Exploration', or save operation fails
        """
        # Validate content
        if not content or not content.strip():
            raise ValueError("Cannot save empty markdown content")

        # Define save callback
        def save_md(path: Path) -> None:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

        # Use base save method
        result = self._save_file_base(
            sheet_name=sheet_name,
            dataset_name=dataset_name,
            extension='md',
            save_callback=save_md,
            sheet_type='report',
            extra_return_data={'length': len(content)}
        )

        # Update message to be more specific
        result['message'] = 'Markdown saved successfully'
        return result

    def load_markdown(self, name_python: str) -> Union[str, Any]:
        """
        Load markdown content from a .md file or d6tflow task output.

        Uses dataset.sheet notation. If the name starts with 'exploration.',
        reads the file path from the sheet's uri column. Otherwise, uses
        load_task() to execute a d6tflow task.

        Args:
            name_python: Combined dataset.sheet name (e.g., 'exploration.AnalysisNotes')

        Returns:
            Markdown content as string (for exploration datasets) or task output (for others)

        Raises:
            ValueError: If dataset/sheet combination not found or file doesn't exist
        """
        # Define load callback
        def load_md(path: Path) -> str:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()

        # Use base load method
        return self._load_file_base(
            name_python=name_python,
            file_type="markdown",
            load_callback=load_md
        )

    def delete_markdown(self, name_python: str) -> Dict[str, Any]:
        """
        Delete a markdown file and its metadata.

        Deletes both the .md file and the sheet record from the database.

        Args:
            name_python: Combined dataset.sheet name (e.g., 'exploration.AnalysisNotes')

        Returns:
            Dict with keys:
                - message: Success message
                - file_deleted: Whether file was found and deleted
                - sheet_deleted: Whether sheet metadata was deleted
                - dataset_name_python: Dataset name
                - sheet_name_python: Sheet name

        Raises:
            ValueError: If dataset/sheet combination not found in database
        """
        try:
            result = self._delete_file_and_sheet(name_python, "markdown")
            result['message'] = 'Markdown deleted successfully'
            return result

        except Exception as e:
            if "not found" in str(e):
                raise
            logger.error(f"Failed to delete markdown: {str(e)}")
            raise ValueError(f"Failed to delete markdown: {str(e)}")

    def load_task(self, name_python: str) -> Any:
        """
        Load and execute a d6tflow task, returning its output.

        Dynamically imports the task module based on dataset name and executes
        the task class based on sheet name using d6tflow workflow.

        Args:
            name_python: Combined dataset.sheet name (e.g., 'exploration.HpiMaster')
                        The dataset corresponds to the module in tasks/
                        The sheet corresponds to the task class name

        Returns:
            Output from d6tflow task execution (type varies by task)

        Raises:
            ValueError: If name format is invalid, module not found, or task class not found

        Example:
            >>> io_service.load_task('exploration.HpiMaster')
            # Imports tasks.exploration and executes tasks.HpiMaster
        """
        try:
            # Validate and parse name_python
            if '.' not in name_python:
                raise ValueError(
                    f"Invalid name format: '{name_python}'. "
                    f"Expected format: 'dataset.sheet' (e.g., 'exploration.HpiMaster')"
                )

            parts = name_python.split('.')
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid name format: '{name_python}'. "
                    f"Expected exactly one '.' separator. Got {len(parts) - 1}."
                )

            dataset, sheet = parts
            logger.debug(f"Loading task: dataset='{dataset}', sheet='{sheet}'")

            # Dynamic import of task module
            try:
                import d6tflow
                task_module = importlib.import_module(f'tasks.{dataset}')
                logger.debug(f"Successfully imported module: tasks.{dataset}")
            except ImportError as e:
                raise ValueError(
                    f"Failed to import task module 'tasks.{dataset}': {str(e)}. "
                    f"Make sure the module exists and is accessible."
                )

            # Get task class from module
            try:
                task_class = getattr(task_module, sheet)
                logger.debug(f"Successfully found task class: {sheet}")
            except AttributeError:
                raise ValueError(
                    f"Task class '{sheet}' not found in module 'tasks.{dataset}'. "
                    f"Available attributes: {dir(task_module)}"
                )

            # Create workflow and load output
            try:
                flow = d6tflow.Workflow(task=task_class)
                if not flow.complete(cascade=False):
                    flow.run()
                output = flow.outputLoad(task_class)
                logger.success(f"Successfully loaded task output for {name_python}")
                return output
            except Exception as e:
                raise ValueError(
                    f"Failed to execute d6tflow workflow for {name_python}: {str(e)}"
                )

        except ValueError:
            # Re-raise ValueError as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading task {name_python}: {str(e)}")
            raise ValueError(f"Failed to load task {name_python}: {str(e)}")

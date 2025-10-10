"""Import Service for importing files into OryxForge projects."""

from pathlib import Path
from typing import Dict, Any
import sys
from jinja2 import Template
from loguru import logger

# Handle tomllib for Python 3.11+ or tomli for older versions
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        raise ImportError("tomli package is required for Python < 3.11. Install it with: pip install tomli")

from .utils import init_supabase_client
from .project_service import ProjectService
from ..agents.claude import ClaudeAgent


class ImportService:
    """
    Service class for importing files into OryxForge projects.

    Uses ClaudeAgent to process files and create datasheets.
    """

    def __init__(self, file_id: str):
        """
        Initialize Import Service.

        Args:
            file_id: ID of the file in data_sources table

        Raises:
            ValueError: If file_id not found in data_sources
        """
        self.file_id = file_id
        self.supabase_client = init_supabase_client()
        self.bucket_name = "data-source-files"

        # Get file data from data_sources
        response = self.supabase_client.table("data_sources").select("*").eq("id", file_id).execute()

        if not response.data:
            raise ValueError(f"No file found with file_id: {file_id}")

        self.file = response.data[0]

        # Initialize ProjectService
        self.project_service = ProjectService(
            project_id=self.file['project_id'],
            user_id=self.file['user_owner']
        )

    def filepath(self) -> Path:
        """
        Construct file path from file.uri.

        Returns:
            Path object for the file

        Raises:
            ValueError: If URI format is not supported
        """
        uri = self.file['uri']

        if uri.startswith("local://"):
            # Extract path after "local://"
            file_path = uri.replace("local://", "")
            return Path(file_path)
        elif uri.startswith("supabase://"):
            # Construct path in data/.import directory
            file_path = f"data/.import/{self.file['name']}"
            return Path(file_path)
        else:
            raise ValueError(f"Unsupported URI format: {uri}")

    def exists_local(self) -> bool:
        """
        Check if file exists locally.

        Returns:
            True if file exists locally, False otherwise
        """
        return self.filepath().exists()

    def download(self) -> None:
        """
        Download file from Supabase storage if needed.

        Only downloads if URI contains "supabase:"
        """
        uri = self.file['uri']

        if "supabase:" in uri:
            fpath = self.filepath()
            fpath.parent.mkdir(parents=True, exist_ok=True)

            # Download the file content
            file_response = self.supabase_client.storage.from_(self.bucket_name).download(self.file['uri'])

            # Write the file to disk
            with open(fpath, "wb") as f:
                f.write(file_response)

            logger.info(f"Downloaded file to {fpath}")

    def save_insight(self, datasheet_id: str, prompt: str, result) -> Dict[str, Any]:
        """
        Save agent insight to insights table.

        Args:
            datasheet_id: ID of the datasheet
            prompt: The prompt sent to the agent
            result: ResultMessage from ClaudeAgent

        Returns:
            Dict containing the saved insight data
        """
        insight_data = {
            "user_owner": self.file['user_owner'],
            "project_id": self.file['project_id'],
            "datasheet_id": datasheet_id,
            "result": result.result,
            "prompt": prompt,
            "cost_usd": result.total_cost_usd,
            "duration_ms": result.duration_ms
        }

        response = self.supabase_client.table("insights").insert(insight_data).execute()
        logger.info(f"Saved insight: {response.data[0]['id']}")
        return response.data[0]

    def _render_prompt(self, file_path: str, dataset: str, sheet: str) -> str:
        """
        Render the import prompt from template using Jinja2.

        Args:
            file_path: Path to the file to import
            dataset: Dataset name (e.g., "Sources")
            sheet: Sheet name (file name)

        Returns:
            Rendered prompt string
        """
        # Read template from TOML file
        template_path = Path(__file__).parent.parent / "prompts" / "templates.toml"

        with open(template_path, 'rb') as f:
            templates = tomllib.load(f)

        template_str = templates['Import']['prompt']

        # Render using Jinja2
        template = Template(template_str)
        prompt = template.render(
            file_path=file_path,
            dataset=dataset,
            sheet=sheet
        )

        return prompt

    def import_file(self) -> Dict[str, Any]:
        """
        Import file using ClaudeAgent.

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
            ValueError: If import fails
        """
        # Set status to processing
        self.supabase_client.table("data_sources").update({
            "status": {
                "flag": "processing",
                "msg": "Import queued"
            }
        }).eq("id", self.file_id).execute()

        logger.info(f"Starting import for file_id: {self.file_id}")

        try:
            # Get Sources dataset
            sources_dataset = self.project_service.ds_get(name="Sources")
            dataset_id = sources_dataset['id']

            # Create datasheet first (using file name and linking to source)
            sheet_data = self.project_service.sheet_create(
                dataset_id=dataset_id,
                name=self.file['name'],
                source_id=self.file_id
            )

            logger.success(f"Datasheet ready: {sheet_data['id']}")

            # Download file if needed
            self.download()

            # Construct file path
            file_path = str(self.filepath())

            # Render prompt using name_python from dataset and sheet
            prompt = self._render_prompt(
                file_path,
                sources_dataset['name_python'],
                sheet_data['name_python']
            )

            # Call ClaudeAgent
            logger.info("Calling ClaudeAgent to process file")
            result = ClaudeAgent.query_run(
                query_text=prompt,
                verbose=True
            )

            # Save insight
            self.save_insight(sheet_data['id'], prompt, result)

            # Set status to ready
            self.supabase_client.table("data_sources").update({
                "status": {
                    "flag": "ready",
                    "msg": "File imported successfully"
                }
            }).eq("id", self.file_id).execute()

            return {
                "message": "File imported successfully",
                "file_id": self.file_id,
                "file_name": self.file['name'],
                "dataset_id": dataset_id,
                "sheet_id": sheet_data['id'],
                "sheet_name": sheet_data['name_python'],
                "dataset_name": sources_dataset['name_python'],
                "agent_result": result
            }

        except Exception as e:
            # Set status to error
            self.supabase_client.table("data_sources").update({
                "status": {
                    "flag": "error",
                    "msg": str(e)
                }
            }).eq("id", self.file_id).execute()

            logger.error(f"Import failed: {str(e)}")
            raise ValueError(f"Import failed: {str(e)}")

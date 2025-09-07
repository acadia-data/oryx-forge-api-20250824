import os
import pandas as pd
from typing import Dict, Any, Union, List
from supabase import Client
import pathlib
import gcsfs
import uuid


class FileService:
    """
    Service class for handling file operations and previews.
    """
    
    def __init__(self, supabase_client: Client, user_owner: str, project_id: str, data_source_id: str, bucket_name: str = "data-source-files"):
        self.supabase_client = supabase_client
        self.user_owner = user_owner
        self.project_id = project_id
        self.data_source_id = data_source_id
        self.bucket_name = bucket_name
        # Initialize GCS filesystem - will use default credentials from environment
        try:
            self.gcs = gcsfs.GCSFileSystem()
            self.gcs_bucket = "orxy-forge-datasets-dev"
            # Validate bucket access
            self._validate_gcs_access()
        except Exception as e:
            raise ValueError(f"Failed to initialize GCS filesystem: {str(e)}")
    
    def _validate_gcs_access(self):
        """
        Validate that we can access the GCS bucket.
        
        Raises:
            ValueError: If bucket access fails
        """
        try:
            # Check if bucket exists and is accessible
            if not self.gcs.exists(f"gcs://{self.gcs_bucket}"):
                raise ValueError(f"GCS bucket {self.gcs_bucket} does not exist or is not accessible")
        except Exception as e:
            raise ValueError(f"Failed to validate GCS bucket access: {str(e)}")
    
    def get_data_source_record(self) -> Dict[str, Any]:
        """
        Retrieve data source record from Supabase.
        
        Returns:
            The data source record
            
        Raises:
            ValueError: If no data source is found
        """
        r = (
            self.supabase_client.table("data_sources")
            .select("*")
            .eq("id", self.data_source_id)
            .execute()
        )

        if not r.data:
            raise ValueError(f"No data source found for data_source_id: {self.data_source_id}")
        
        return r.data[0]
    
    def download_file(self, source_record) -> str:
        """
        Download file from Supabase storage.
        
        Args:
            fileid: The file ID to download
            data_dir: Directory to save the file
            
        Returns:
            Path to the downloaded file
        """

        fpath = f"data/supabase/{source_record['project_id']}/{source_record['id']}/{source_record['name']}"
        fpath = pathlib.Path(fpath)
        fpath.parent.mkdir(parents=True, exist_ok=True)

        # Download the file content
        file_response = self.supabase_client.storage.from_(self.bucket_name).download(source_record['uri'])
        
        # Write the file to disk
        with open(fpath, "wb") as f:
            f.write(file_response)
        
        return fpath
    
    def read_file_preview(self, source_record: dict, file_path: str) -> Dict[str, Any]:
        """
        Read file and return preview data based on file type.
        
        Args:
            file_path: Path to the file to read
            file_type: Type of the file (csv, excel, parquet)
            
        Returns:
            Preview data dictionary
            
        Raises:
            ValueError: If file type is unsupported
        """
        file_type = source_record.get("type", "").lower()

        if file_type == "csv":
            df_data = pd.read_csv(file_path)
            return {"data": df_data.head(100)}
        elif file_type == "excel":
            # Read all sheets
            df_data = pd.read_excel(file_path, sheet_name=None)
            preview_data = {sheetname: df.head(100) for sheetname, df in df_data.items()}
            return preview_data

        elif file_type == "parquet":
            df_data = pd.read_parquet(file_path)
            return {"data": df_data.head(100)}
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def read_file_for_import(self, source_record: dict, file_path: str, selected_sheets: Dict[str, str]) -> Dict[str, pd.DataFrame]:
        """
        Read file and return dataframes for import based on selected sheets.
        
        Args:
            source_record: The data source record
            file_path: Path to the file to read
            selected_sheets: Mapping of source sheet names to target names
            
        Returns:
            Dictionary mapping target names to dataframes
            
        Raises:
            ValueError: If file type is unsupported
        """
        file_type = source_record.get("type", "").lower()

        if file_type == "csv":
            # For CSV, take the first selected sheet name as the target
            target_name = list(selected_sheets.values())[0]
            df_data = pd.read_csv(file_path)
            return {target_name: df_data}
        elif file_type == "excel":
            # Read selected sheets only
            df_data = pd.read_excel(file_path, sheet_name=list(selected_sheets.keys()))
            # Map to target names
            result = {}
            for source_name, target_name in selected_sheets.items():
                if source_name in df_data:
                    result[target_name] = df_data[source_name]
            return result
        elif file_type == "parquet":
            # For parquet, take the first selected sheet name as the target
            target_name = list(selected_sheets.values())[0]
            df_data = pd.read_parquet(file_path)
            return {target_name: df_data}
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def save_dataframe_to_gcs(self, df: pd.DataFrame, project_id: str, dataset_id: str, datasheet_name: str) -> str:
        """
        Save dataframe to Google Cloud Storage as parquet file.
        
        Args:
            df: The dataframe to save
            project_id: The project ID
            dataset_id: The dataset ID
            datasheet_name: The name of the datasheet
            
        Returns:
            The GCS path where the file was saved
        """
        gcs_path = f"gcs://{self.gcs_bucket}/{project_id}/{dataset_id}/{datasheet_name}.parquet"
        
        # Save to GCS
        with self.gcs.open(gcs_path, 'wb') as f:
            df.to_parquet(f, index=False)
        
        return gcs_path
    
    def create_dataset_record(self, dataset_name: str) -> str:
        """
        Create a new dataset record in Supabase.
        
        Args:
            dataset_name: The name of the dataset
            
        Returns:
            The created dataset ID
        """
        response = (
            self.supabase_client.table("datasets")
            .insert({
                "name": dataset_name,
                "user_owner": self.user_owner,
                "project_id": self.project_id
            })
            .execute()
        )
        
        if not response.data:
            raise ValueError("Failed to create dataset record")
        
        return response.data[0]['id']
    
    def create_datasheet_record(self, dataset_id: str, datasheet_name: str, gcs_path: str) -> str:
        """
        Create a new datasheet record in Supabase.
        
        Args:
            dataset_id: The dataset ID
            datasheet_name: The name of the datasheet
            gcs_path: The GCS path where the data is stored
            
        Returns:
            The created datasheet ID
        """
        response = (
            self.supabase_client.table("datasheets")
            .insert({
                "name": datasheet_name,
                "user_owner": self.user_owner,
                "dataset_id": dataset_id,
                "gcs_path": gcs_path
            })
            .execute()
        )
        
        if not response.data:
            raise ValueError("Failed to create datasheet record")
        
        return response.data[0]['id']
    
    def update_data_source_status(self, status: str = "ready") -> None:
        """
        Update the status of a data source record.
        
        Args:
            status: The new status
        """
        response = (
            self.supabase_client.table("data_sources")
            .update({"status": status})
            .eq("id", self.data_source_id)
            .execute()
        )
        
        if not response.data:
            raise ValueError(f"Failed to update data source {self.data_source_id}")
    
    def cleanup_file(self, file_path: str) -> None:
        """
        Remove temporary file from disk.
        
        Args:
            file_path: Path to the file to remove
        """
        if os.path.exists(file_path):
            os.remove(file_path)
    
    def preview_data_source(self) -> Dict[str, Any]:
        """
        Main method to preview a data source from Supabase storage.
        
        Returns:
            Preview data dictionary
            
        Raises:
            ValueError: If data source cannot be processed
        """

        file_path = None

        # Get the data source record
        source_record = self.get_data_source_record()

        # Download file
        file_path = self.download_file(source_record)
        
        # Read and return preview data
        return self.read_file_preview(source_record, file_path)
    
    def import_file(self, selected_sheets: Dict[str, str], dataset_name: str = None) -> Dict[str, Any]:
        """
        Main method to import a file from Supabase storage to GCS and create records.
        
        Args:
            selected_sheets: Mapping of source sheet names to target names
            dataset_name: Optional custom dataset name
            
        Returns:
            Dictionary with import results including dataset and datasheet IDs
            
        Raises:
            ValueError: If import cannot be processed
        """
        file_path = None
        
        try:
            # Get the data source record
            source_record = self.get_data_source_record()
            
            # Download file
            file_path = self.download_file(source_record)
            
            # Read file data for import
            dataframes = self.read_file_for_import(source_record, file_path, selected_sheets)
            
            # Create dataset if needed
            if dataset_name:
                dataset_id = self.create_dataset_record(dataset_name)
            else:
                # Use existing dataset from data source
                dataset_id = source_record.get('dataset_id')
                if not dataset_id:
                    raise ValueError("No dataset_id found in data source and no dataset_name provided")
            
            # Create datasheets and save to GCS
            datasheet_ids = {}
            for datasheet_name, df in dataframes.items():
                # Save to GCS
                gcs_path = self.save_dataframe_to_gcs(df, self.project_id, dataset_id, datasheet_name)
                
                # Create datasheet record
                datasheet_id = self.create_datasheet_record(dataset_id, datasheet_name, gcs_path)
                datasheet_ids[datasheet_name] = datasheet_id
            
            # Update data source status
            self.update_data_source_status("ready")
            
            return {
                "status": "success",
                "dataset_id": dataset_id,
                "datasheet_ids": datasheet_ids,
                "message": f"Successfully imported {len(dataframes)} datasheets"
            }
            
        finally:
            # Clean up temporary file
            if file_path:
                self.cleanup_file(file_path)
            

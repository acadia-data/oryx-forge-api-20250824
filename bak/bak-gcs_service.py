
import gcsfs
# Initialize GCS filesystem for datasheet operations
try:
    self.gcs = gcsfs.GCSFileSystem()
    self.gcs_bucket = "orxy-forge-datasets-dev"
except Exception as e:
    logger.warning(f"Failed to initialize GCS filesystem: {str(e)}")
    self.gcs = None

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

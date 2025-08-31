#!/usr/bin/env python3
"""
Example script demonstrating how to use FileService directly.
This shows how the business logic can be called programmatically
without going through the FastAPI endpoint.
"""

import sys
import os

# Add the current directory to Python path so we can import services
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.file_service import FileService
from supabase import create_client
import adtiam


def main():
    """Example usage of FileService."""
    
    # Load credentials (same as in app.py)
    adtiam.load_creds('adt-db')
    
    # Create Supabase client
    supabase_client = create_client(
        adtiam.creds['db']['supabase']['url'], 
        adtiam.creds['db']['supabase']['key-admin']
    )
    
    # Create FileService instance
    file_service = FileService(supabase_client)
    
    # Example: Preview a file directly
    try:
        fileid = "your-file-id-here"  # Replace with actual file ID
        
        print(f"Previewing file: {fileid}")
        preview_data = file_service.preview_file(fileid)
        
        print("Preview data:")
        print(preview_data)
        
    except ValueError as e:
        print(f"Business logic error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def example_individual_methods():
    """Example of using individual service methods."""
    
    adtiam.load_creds('adt-db')
    supabase_client = create_client(
        adtiam.creds['db']['supabase']['url'], 
        adtiam.creds['db']['supabase']['key-admin']
    )
    
    file_service = FileService(supabase_client)
    
    try:
        fileid = "your-file-id-here"
        
        # Get data source record
        print("Getting data source record...")
        source_record = file_service.get_data_source_record(fileid)
        print(f"Source record: {source_record}")
        
        # You can also test individual components
        file_type = source_record.get("type", "").lower()
        print(f"File type: {file_type}")
        
        # Note: download_file and read_file_preview would require actual file operations
        # so they're better tested with mocks in unit tests
        
    except ValueError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    print("=== FileService Direct Usage Example ===\n")
    
    print("1. Using the main preview_file method:")
    main()
    
    print("\n" + "="*50 + "\n")
    
    print("2. Using individual methods:")
    example_individual_methods()

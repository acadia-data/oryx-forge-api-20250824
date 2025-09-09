import pytest
import pandas as pd
import tempfile
import os
import uuid
from pathlib import Path
from services.file_service import FileService

class TestFileServiceIntegration:
    """Integration tests for FileService core functionality"""
    
    @pytest.fixture(autouse=True)
    def setup_test_data(self, test_supabase_client, authenticated_session):
        """Setup test data for each test"""
        self.supabase = test_supabase_client
        self.user_id = authenticated_session.user.id
        self.test_data_sources = []
        self.test_projects = []
        self.test_datasets = []
        self.temp_files = []
        
        # Create test project
        self.test_project = self._create_test_project()
        self.test_projects.append(self.test_project)
        
        yield
        
        # Cleanup after each test
        self._cleanup_test_data()
    
    def _create_test_project(self):
        """Create a test project for the user"""
        project_name = f"test_project_{uuid.uuid4()}"
        response = self.supabase.table("projects").insert({
            "name": project_name,
            "user_owner": self.user_id
        }).execute()
        return response.data[0]
    
    def _create_test_data_source(self, file_type="csv", content=None):
        """Create a test data source with uploaded file - supports multiple content types"""
        # Create test file based on content type
        if isinstance(content, pd.DataFrame):
            # Parquet file from DataFrame
            test_file_path = self._create_parquet_file(content)
            actual_file_type = "parquet"  # Override file_type for DataFrame content
        elif isinstance(content, list):
            # Excel file with multiple sheets
            test_file_path = self._create_excel_file(content)
            actual_file_type = "excel"  # Override file_type for list content
        else:
            # CSV or other text-based files
            test_file_path = self._create_text_file(file_type, content)
            actual_file_type = file_type
        
        self.temp_files.append(test_file_path)
        
        # Upload to Supabase storage
        file_uri = self._upload_test_file(test_file_path)
        
        # Create data source record
        data_source_name = f"test_data_source_{uuid.uuid4()}"
        data_source = {
            "name": data_source_name,
            "type": actual_file_type,  # Use the actual file type
            "uri": file_uri,
            "user_owner": self.user_id,
            "project_id": self.test_project['id'],
            "status": "ready"
        }
        
        response = self.supabase.table("data_sources").insert(data_source).execute()
        data_source_record = response.data[0]
        self.test_data_sources.append(data_source_record)
        return data_source_record
    
    def _create_text_file(self, file_type, content):
        """Create text-based file (CSV, TXT, etc.)"""
        if content is None:
            # Default CSV content
            content = "name,age,city\nJohn,25,New York\nJane,30,London\nBob,35,Paris"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{file_type}', delete=False) as f:
            f.write(content)
            return f.name
    
    def _create_excel_file(self, sheets_data):
        """Create Excel file with multiple sheets"""
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            with pd.ExcelWriter(f.name, engine='openpyxl') as writer:
                for sheet_name, df in sheets_data:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            return f.name
    
    def _create_parquet_file(self, df):
        """Create Parquet file from DataFrame"""
        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as f:
            df.to_parquet(f.name, index=False)
            return f.name
    
    def _upload_test_file(self, file_path):
        """Upload test file to Supabase storage"""
        file_name = Path(file_path).name
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Upload to storage
        response = self.supabase.storage.from_("data-source-files").upload(
            f"{self.user_id}/{self.test_project['id']}/{file_name}",
            file_content
        )
        return f"{self.user_id}/{self.test_project['id']}/{file_name}"
    
    def _cleanup_test_data(self):
        """Clean up all test data"""
        # Clean up data sources
        for data_source in self.test_data_sources:
            try:
                self.supabase.table("data_sources").delete().eq("id", data_source['id']).execute()
                # Clean up storage file
                self.supabase.storage.from_("data-source-files").remove([data_source['uri']])
            except Exception as e:
                print(f"Failed to cleanup data source {data_source['id']}: {e}")
        
        # Clean up projects
        for project in self.test_projects:
            try:
                self.supabase.table("projects").delete().eq("id", project['id']).execute()
            except Exception as e:
                print(f"Failed to cleanup project {project['id']}: {e}")
        
        # Clean up temp files
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"Failed to cleanup temp file {temp_file}: {e}")
    
    def _generate_test_data(self, data_type, **kwargs):
        """Generate test data based on type and parameters"""
        if data_type == "csv":
            return self._generate_csv_data(**kwargs)
        elif data_type == "excel":
            return self._generate_excel_data(**kwargs)
        elif data_type == "parquet":
            return self._generate_parquet_data(**kwargs)
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def _generate_csv_data(self, rows=3, columns=None, **kwargs):
        """Generate CSV test data with specified structure"""
        if columns is None:
            columns = ['name', 'age', 'city']
        
        data = []
        for i in range(rows):
            row = {}
            for col in columns:
                if col == 'name':
                    row[col] = f'Person{i+1}'
                elif col == 'age':
                    row[col] = 20 + i
                elif col == 'city':
                    row[col] = f'City{i+1}'
                else:
                    row[col] = f'{col}_value_{i+1}'
            data.append(row)
        
        return pd.DataFrame(data)

    def _generate_excel_data(self, sheets_config=None, **kwargs):
        """Generate Excel test data with multiple sheets"""
        if sheets_config is None:
            sheets_config = [
                {'name': 'Sheet1', 'columns': ['name', 'age'], 'rows': 2},
                {'name': 'Sheet2', 'columns': ['product', 'price'], 'rows': 2}
            ]
        
        sheets_data = []
        for sheet_config in sheets_config:
            df = self._generate_csv_data(
                rows=sheet_config['rows'],
                columns=sheet_config['columns']
            )
            sheets_data.append((sheet_config['name'], df))
        
        return sheets_data

    def _generate_parquet_data(self, rows=2, columns=None, **kwargs):
        """Generate Parquet test data"""
        if columns is None:
            columns = ['id', 'value']
        
        data = []
        for i in range(rows):
            row = {}
            for col in columns:
                if col == 'id':
                    row[col] = i + 1
                elif col == 'value':
                    row[col] = (i + 1) * 100
                else:
                    row[col] = f'{col}_value_{i+1}'
            data.append(row)
        
        return pd.DataFrame(data)
    
    def _assert_dataframe_structure(self, actual_df, expected_df):
        """Assert DataFrame structure matches expected structure"""
        # Validate columns
        assert list(actual_df.columns) == list(expected_df.columns), \
            f"Column mismatch: expected {list(expected_df.columns)}, got {list(actual_df.columns)}"
        
        # Validate data types
        for col in expected_df.columns:
            assert actual_df[col].dtype == expected_df[col].dtype, \
                f"Column {col} type mismatch: expected {expected_df[col].dtype}, got {actual_df[col].dtype}"
        
        # Validate row count (for preview, we expect head(100) so actual might be less)
        assert len(actual_df) <= len(expected_df), \
            f"Row count mismatch: expected <= {len(expected_df)}, got {len(actual_df)}"
        
        # Validate that we have at least some data
        assert len(actual_df) > 0, "DataFrame should not be empty"

    def _assert_file_preview_structure(self, preview_data, expected_sheets_info):
        """Assert file preview structure matches expected sheets info"""
        # Validate all expected sheets exist
        expected_sheet_names = [sheet['name'] for sheet in expected_sheets_info]
        actual_sheet_names = list(preview_data.keys())
        
        assert set(actual_sheet_names) == set(expected_sheet_names), \
            f"Sheet mismatch: expected {expected_sheet_names}, got {actual_sheet_names}"
        
        # Validate each sheet
        for sheet_info in expected_sheets_info:
            sheet_name = sheet_info['name']
            expected_df = sheet_info['data']
            
            assert sheet_name in preview_data
            actual_df = preview_data[sheet_name]
            
            self._assert_dataframe_structure(actual_df, expected_df)

    def _assert_import_results(self, import_result, expected_sheets_info):
        """Assert import results match expected sheets info"""
        assert import_result["status"] == "success"
        assert "dataset_id" in import_result
        assert "datasheet_ids" in import_result
        
        # Validate all expected target names exist in results
        expected_target_names = [sheet['target_name'] for sheet in expected_sheets_info]
        actual_target_names = list(import_result["datasheet_ids"].keys())
        
        assert set(actual_target_names) == set(expected_target_names), \
            f"Target name mismatch: expected {expected_target_names}, got {actual_target_names}"

    def test_file_service_initialization_and_data_retrieval(self):
        """Test FileService initialization and data source record retrieval"""
        # Test initialization
        data_source = self._create_test_data_source("csv")
        
        file_service = FileService(
            self.supabase,
            self.user_id,
            self.test_project['id'],
            data_source['id']
        )
        
        # Verify initialization
        assert file_service.supabase_client == self.supabase
        assert file_service.user_owner == self.user_id
        assert file_service.project_id == self.test_project['id']
        assert file_service.data_source_id == data_source['id']
        
        # Test successful data retrieval
        result = file_service.get_data_source_record()
        assert result['id'] == data_source['id']
        assert result['name'] == data_source['name']
        assert result['type'] == data_source['type']
        assert result['user_owner'] == self.user_id
        
        # Test error case for non-existent data source
        non_existent_id = str(uuid.uuid4())
        file_service_invalid = FileService(
            self.supabase,
            self.user_id,
            self.test_project['id'],
            non_existent_id
        )
        
        with pytest.raises(ValueError, match="No data source found"):
            file_service_invalid.get_data_source_record()
    
    def test_file_download_and_preview_workflow(self):
        """Test complete file download and preview workflow for all supported formats"""
        # Test data for different file types
        test_cases = [
            {
                "type": "csv",
                "content": "name,age,city\nJohn,25,New York\nJane,30,London\nBob,35,Paris",
                "expected_columns": ["name", "age", "city"],
                "expected_rows": 3
            },
            {
                "type": "parquet",
                "dataframe": pd.DataFrame({'name': ['John', 'Jane'], 'age': [25, 30], 'city': ['NYC', 'LA']}),
                "expected_columns": ["name", "age", "city"],
                "expected_rows": 2
            }
        ]
        
        for test_case in test_cases:
            # Create data source
            if test_case["type"] == "csv":
                data_source = self._create_test_data_source("csv", test_case["content"])
            else:  # parquet
                data_source = self._create_test_data_source("parquet", test_case["dataframe"])
            
            file_service = FileService(
                self.supabase,
                self.user_id,
                self.test_project['id'],
                data_source['id']
            )
            
            # Test download
            source_record = file_service.get_data_source_record()
            file_path = file_service.download_file(source_record)
            
            assert os.path.exists(file_path)
            assert str(file_path).endswith(data_source['name'])
            
            # Test preview
            preview_data = file_service.read_file_preview(source_record, file_path)
            
            assert "data" in preview_data
            assert len(preview_data["data"]) == test_case["expected_rows"]
            assert preview_data["data"].columns.tolist() == test_case["expected_columns"]
            
            # Test cleanup
            file_service.cleanup_file(file_path)
            assert not os.path.exists(file_path)
    
    def test_excel_file_processing_workflow(self):
        """Test Excel file processing with multiple sheets"""
        # Define test data with metadata for validation
        sheets_data = [
            {
                'name': 'Sheet1',
                'data': pd.DataFrame({'name': ['John', 'Jane'], 'age': [25, 30]}),
                'target_name': 'users'
            },
            {
                'name': 'Sheet2', 
                'data': pd.DataFrame({'product': ['A', 'B'], 'price': [10, 20]}),
                'target_name': 'products'
            },
            {
                'name': 'Sheet3',
                'data': pd.DataFrame({'category': ['X', 'Y'], 'count': [5, 8]}),
                'target_name': 'categories'
            }
        ]
        
        # Create Excel file from structured data
        excel_sheets = [(sheet['name'], sheet['data']) for sheet in sheets_data]
        data_source = self._create_test_data_source("excel", excel_sheets)
        
        file_service = FileService(
            self.supabase,
            self.user_id,
            self.test_project['id'],
            data_source['id']
        )
        
        # Test complete workflow
        source_record = file_service.get_data_source_record()
        file_path = file_service.download_file(source_record)
        
        # Test preview with dynamic validation
        preview_data = file_service.read_file_preview(source_record, file_path)
        
        # Validate all sheets exist
        expected_sheet_names = [sheet['name'] for sheet in sheets_data]
        assert set(preview_data.keys()) == set(expected_sheet_names)
        
        # Validate each sheet dynamically
        for sheet_info in sheets_data:
            sheet_name = sheet_info['name']
            expected_df = sheet_info['data']
            
            assert sheet_name in preview_data
            actual_df = preview_data[sheet_name]
            
            # Validate structure dynamically
            self._assert_dataframe_structure(actual_df, expected_df)
        
        # Test file import functionality with dynamic validation
        selected_sheets = {sheet['name']: sheet['target_name'] for sheet in sheets_data[:2]}  # Test first 2 sheets
        dataframes = file_service.read_file_for_import(source_record, file_path, selected_sheets)
        
        # Validate import results dynamically
        expected_target_names = [sheet['target_name'] for sheet in sheets_data[:2]]
        assert set(dataframes.keys()) == set(expected_target_names)
        
        for sheet_info in sheets_data[:2]:
            target_name = sheet_info['target_name']
            expected_df = sheet_info['data']
            
            assert target_name in dataframes
            actual_df = dataframes[target_name]
            
            # Validate imported data structure
            self._assert_dataframe_structure(actual_df, expected_df)
        
        # Cleanup
        file_service.cleanup_file(file_path)
    
    def test_error_handling_and_unsupported_formats(self):
        """Test error handling for various scenarios"""
        # Test unsupported file type by creating a CSV data source but with unsupported content
        data_source = self._create_test_data_source("csv", "plain text content")
        
        file_service = FileService(
            self.supabase,
            self.user_id,
            self.test_project['id'],
            data_source['id']
        )
        
        source_record = file_service.get_data_source_record()
        file_path = file_service.download_file(source_record)
        
        # Test that CSV reading works even with plain text (pandas will handle it)
        preview_data = file_service.read_file_preview(source_record, file_path)
        assert preview_data is not None
        
        # Test cleanup when file doesn't exist
        file_service.cleanup_file("/path/to/nonexistent/file")  # Should not raise exception
        
        # Test cleanup when file exists
        file_service.cleanup_file(file_path)
        assert not os.path.exists(file_path)
        
        # Test unsupported file type by manually modifying the source record
        data_source2 = self._create_test_data_source("csv", "name,age\nJohn,25")
        file_service2 = FileService(
            self.supabase,
            self.user_id,
            self.test_project['id'],
            data_source2['id']
        )
        
        source_record2 = file_service2.get_data_source_record()
        file_path2 = file_service2.download_file(source_record2)
        
        # Manually modify the type to test unsupported type error
        source_record2['type'] = 'unsupported'
        
        with pytest.raises(ValueError, match="Unsupported file type"):
            file_service2.read_file_preview(source_record2, file_path2)
        
        # Cleanup
        file_service2.cleanup_file(file_path2)
    
    def test_complete_preview_workflow(self):
        """Test complete preview workflow for different file types"""
        test_files = [
            ("csv", "name,age\nJohn,25\nJane,30"),
            ("parquet", pd.DataFrame({'id': [1, 2], 'value': [100, 200]}))
        ]
        
        for file_type, content in test_files:
            data_source = self._create_test_data_source(file_type, content)
            
            file_service = FileService(
                self.supabase,
                self.user_id,
                self.test_project['id'],
                data_source['id']
            )
            
            # Test complete preview workflow
            preview_data = file_service.preview_data_source()
            
            assert "data" in preview_data
            assert len(preview_data["data"]) > 0
            assert isinstance(preview_data["data"], pd.DataFrame)
    
    def test_database_record_management(self):
        """Test dataset and datasheet record creation and management"""
        data_source = self._create_test_data_source("csv")
        
        file_service = FileService(
            self.supabase,
            self.user_id,
            self.test_project['id'],
            data_source['id']
        )
        
        # Test dataset creation
        dataset_name = f"test_dataset_{uuid.uuid4()}"
        dataset_id = file_service.create_dataset_record(dataset_name)
        
        assert dataset_id is not None
        
        # Verify dataset was created
        response = self.supabase.table("datasets").select("*").eq("id", dataset_id).execute()
        assert len(response.data) == 1
        dataset_record = response.data[0]
        assert dataset_record['name'] == dataset_name
        assert dataset_record['user_owner'] == self.user_id
        assert dataset_record['project_id'] == self.test_project['id']
        
        self.test_datasets.append(dataset_record)
        
        # Test datasheet creation
        datasheet_name = f"test_datasheet_{uuid.uuid4()}"
        gcs_path = f"gcs://test-bucket/{self.test_project['id']}/{dataset_id}/{datasheet_name}.parquet"
        
        datasheet_id = file_service.create_datasheet_record(dataset_id, datasheet_name, gcs_path)
        
        assert datasheet_id is not None
        
        # Verify datasheet was created
        response = self.supabase.table("datasheets").select("*").eq("id", datasheet_id).execute()
        assert len(response.data) == 1
        datasheet_record = response.data[0]
        assert datasheet_record['name'] == datasheet_name
        assert datasheet_record['user_owner'] == self.user_id
        assert datasheet_record['dataset_id'] == dataset_id
        assert datasheet_record['uri'] == gcs_path
        
        # Test data source status update
        file_service.update_data_source_status("processing")
        response = self.supabase.table("data_sources").select("*").eq("id", data_source['id']).execute()
        assert response.data[0]['status'] == "processing"
        
        # Update back to ready
        file_service.update_data_source_status("ready")
        response = self.supabase.table("data_sources").select("*").eq("id", data_source['id']).execute()
        assert response.data[0]['status'] == "ready"
    
    def test_file_processing_workflow_all_formats(self):
        """Test file processing workflow for all supported formats with dynamic validation"""
        test_configs = [
            {
                'type': 'csv',
                'data': self._generate_csv_data(rows=3, columns=['name', 'age', 'city']),
                'expected_sheets': [{'name': 'data', 'target_name': 'csv_data'}]
            },
            {
                'type': 'parquet', 
                'data': self._generate_parquet_data(rows=2, columns=['id', 'value']),
                'expected_sheets': [{'name': 'data', 'target_name': 'parquet_data'}]
            },
            {
                'type': 'excel',
                'data': self._generate_excel_data([
                    {'name': 'Users', 'columns': ['name', 'age'], 'rows': 2},
                    {'name': 'Products', 'columns': ['product', 'price'], 'rows': 2}
                ]),
                'expected_sheets': [
                    {'name': 'Users', 'target_name': 'imported_users'},
                    {'name': 'Products', 'target_name': 'imported_products'}
                ]
            }
        ]
        
        for config in test_configs:
            # Create data source
            data_source = self._create_test_data_source(config['type'], config['data'])
            
            file_service = FileService(
                self.supabase,
                self.user_id,
                self.test_project['id'],
                data_source['id']
            )
            
            # Test complete workflow
            source_record = file_service.get_data_source_record()
            file_path = file_service.download_file(source_record)
            
            # Test preview with dynamic validation
            preview_data = file_service.read_file_preview(source_record, file_path)
            
            if config['type'] == 'excel':
                # For Excel, validate multiple sheets
                expected_sheets_info = []
                for sheet_config in config['expected_sheets']:
                    # Find the corresponding sheet data
                    sheet_data = next(s for s in config['data'] if s[0] == sheet_config['name'])[1]
                    expected_sheets_info.append({
                        'name': sheet_config['name'],
                        'data': sheet_data
                    })
                self._assert_file_preview_structure(preview_data, expected_sheets_info)
            else:
                # For CSV/Parquet, validate single sheet
                expected_df = config['data']
                assert "data" in preview_data
                self._assert_dataframe_structure(preview_data["data"], expected_df)
            
            # Test import functionality
            selected_sheets = {sheet['name']: sheet['target_name'] for sheet in config['expected_sheets']}
            dataframes = file_service.read_file_for_import(source_record, file_path, selected_sheets)
            
            # Validate import results
            expected_target_names = [sheet['target_name'] for sheet in config['expected_sheets']]
            assert set(dataframes.keys()) == set(expected_target_names)
            
            for sheet_config in config['expected_sheets']:
                target_name = sheet_config['target_name']
                assert target_name in dataframes
                
                # Get expected data for validation
                if config['type'] == 'excel':
                    expected_df = next(s for s in config['data'] if s[0] == sheet_config['name'])[1]
                else:
                    expected_df = config['data']
                
                self._assert_dataframe_structure(dataframes[target_name], expected_df)
            
            # Cleanup
            file_service.cleanup_file(file_path)

"""
Handles file operations for OryxForge MCP server.
Provides tools for reading, writing, and managing data files.
"""

import os
import base64
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
from mcp.types import Tool, TextContent

class FileHandler:
    """Handles file operations and data file management."""
    
    def __init__(self, data_directory: str = "data"):
        self.data_directory = Path(data_directory)
        self.data_directory.mkdir(exist_ok=True)
    
    def get_tools(self) -> List[Tool]:
        """Returns the tools this handler provides."""
        return [
            Tool(
                name="read_data_file",
                description="Read and preview a data file (CSV, Excel, Parquet)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Name of the file to read"
                        },
                        "preview_rows": {
                            "type": "integer", 
                            "description": "Number of rows to preview (default: 10)",
                            "default": 10
                        }
                    },
                    "required": ["filename"]
                }
            ),
            Tool(
                name="list_data_files",
                description="List all available data files",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="upload_data_file",
                description="Upload a new data file",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Name for the uploaded file"
                        },
                        "file_content": {
                            "type": "string",
                            "description": "Base64 encoded file content"
                        }
                    },
                    "required": ["filename", "file_content"]
                }
            ),
            Tool(
                name="get_file_info",
                description="Get information about a specific file",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Name of the file to get info for"
                        }
                    },
                    "required": ["filename"]
                }
            )
        ]
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle tool calls for file operations."""
        
        if tool_name == "read_data_file":
            return await self._read_data_file(
                arguments["filename"],
                arguments.get("preview_rows", 10)
            )
        elif tool_name == "list_data_files":
            return await self._list_data_files()
        elif tool_name == "upload_data_file":
            return await self._upload_data_file(
                arguments["filename"],
                arguments["file_content"]
            )
        elif tool_name == "get_file_info":
            return await self._get_file_info(arguments["filename"])
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    async def _read_data_file(self, filename: str, preview_rows: int) -> List[TextContent]:
        """Read and preview a data file."""
        file_path = self.data_directory / filename
        
        if not file_path.exists():
            return [TextContent(
                type="text",
                text=f"Error: File '{filename}' not found in data directory"
            )]
        
        try:
            # Determine file type and read accordingly
            if filename.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif filename.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            elif filename.endswith('.parquet'):
                df = pd.read_parquet(file_path)
            else:
                return [TextContent(
                    type="text",
                    text=f"Error: Unsupported file type for '{filename}'. Supported: .csv, .xlsx, .xls, .parquet"
                )]
            
            # Create preview
            preview = df.head(preview_rows)
            summary = f"File: {filename}\nShape: {df.shape}\nColumns: {list(df.columns)}\nData types:\n{df.dtypes}\n\n"
            preview_text = preview.to_string(index=False)
            
            return [TextContent(
                type="text",
                text=summary + "Preview:\n" + preview_text
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error reading file '{filename}': {str(e)}"
            )]
    
    async def _list_data_files(self) -> List[TextContent]:
        """List all available data files."""
        files = []
        total_size = 0
        
        for file_path in self.data_directory.iterdir():
            if file_path.is_file() and file_path.suffix in ['.csv', '.xlsx', '.xls', '.parquet']:
                size = file_path.stat().st_size
                total_size += size
                files.append(f"- {file_path.name} ({self._format_size(size)})")
        
        if not files:
            return [TextContent(
                type="text",
                text="No data files found in the data directory"
            )]
        
        file_list = "\n".join(files)
        return [TextContent(
            type="text",
            text=f"Available data files ({len(files)} files, {self._format_size(total_size)} total):\n{file_list}"
        )]
    
    async def _upload_data_file(self, filename: str, file_content: str) -> List[TextContent]:
        """Upload a new data file."""
        try:
            # Decode base64 content
            file_bytes = base64.b64decode(file_content)
            
            # Save to data directory
            file_path = self.data_directory / filename
            with open(file_path, 'wb') as f:
                f.write(file_bytes)
            
            # Verify the file can be read
            if filename.endswith('.csv'):
                pd.read_csv(file_path, nrows=1)
            elif filename.endswith(('.xlsx', '.xls')):
                pd.read_excel(file_path, nrows=1)
            elif filename.endswith('.parquet'):
                pd.read_parquet(file_path)
            
            return [TextContent(
                type="text",
                text=f"✅ Successfully uploaded '{filename}' ({self._format_size(len(file_bytes))})"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error uploading file '{filename}': {str(e)}"
            )]
    
    async def _get_file_info(self, filename: str) -> List[TextContent]:
        """Get detailed information about a file."""
        file_path = self.data_directory / filename
        
        if not file_path.exists():
            return [TextContent(
                type="text",
                text=f"Error: File '{filename}' not found"
            )]
        
        try:
            stat = file_path.stat()
            info = f"File: {filename}\n"
            info += f"Size: {self._format_size(stat.st_size)}\n"
            info += f"Modified: {pd.Timestamp(stat.st_mtime, unit='s')}\n"
            info += f"Extension: {file_path.suffix}\n"
            
            # Try to get data info
            if filename.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif filename.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            elif filename.endswith('.parquet'):
                df = pd.read_parquet(file_path)
            else:
                return [TextContent(type="text", text=info + "\nUnsupported file type for data analysis")]
            
            info += f"Shape: {df.shape}\n"
            info += f"Columns: {list(df.columns)}\n"
            info += f"Data types:\n{df.dtypes.to_string()}\n"
            info += f"Memory usage: {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
            
            return [TextContent(type="text", text=info)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error analyzing file '{filename}': {str(e)}"
            )]
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"

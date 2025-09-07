"""
MCP Server for OryxForge integration.
Provides tools and resources for code generation and data processing.
"""

import asyncio
import logging
from pathlib import Path
from typing import List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, Resource

from .handlers import FileHandler, CodeGenerationHandler, DataProcessingHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OryxForgeMCPServer:
    """Main MCP Server for OryxForge."""
    
    def __init__(self, data_directory: str = "data", output_directory: str = "generated_workflows"):
        self.server = Server("oryxforge-mcp")
        self.data_directory = data_directory
        self.output_directory = output_directory
        
        # Initialize handlers
        self.file_handler = FileHandler(data_directory)
        self.code_generation_handler = CodeGenerationHandler(output_directory)
        self.data_processing_handler = DataProcessingHandler(data_directory)
        
        # Register tools and resources
        self._register_tools()
        self._register_resources()
    
    def _register_tools(self):
        """Register all available tools."""
        all_tools = []
        
        # Add tools from all handlers
        all_tools.extend(self.file_handler.get_tools())
        all_tools.extend(self.code_generation_handler.get_tools())
        all_tools.extend(self.data_processing_handler.get_tools())
        
        # Register tools with the server
        for tool in all_tools:
            self.server.register_tool(tool)
        
        logger.info(f"Registered {len(all_tools)} tools")
    
    def _register_resources(self):
        """Register available resources."""
        # Register data files as resources
        data_path = Path(self.data_directory)
        if data_path.exists():
            for file_path in data_path.iterdir():
                if file_path.is_file() and file_path.suffix in ['.csv', '.xlsx', '.xls', '.parquet']:
                    resource = Resource(
                        uri=f"file://{file_path.absolute()}",
                        name=file_path.name,
                        description=f"Data file: {file_path.name}",
                        mimeType=self._get_mime_type(file_path.suffix)
                    )
                    self.server.register_resource(resource)
        
        # Register generated workflows as resources
        output_path = Path(self.output_directory)
        if output_path.exists():
            for file_path in output_path.iterdir():
                if file_path.is_file() and file_path.suffix == '.py':
                    resource = Resource(
                        uri=f"file://{file_path.absolute()}",
                        name=file_path.stem,
                        description=f"Generated workflow: {file_path.stem}",
                        mimeType="text/x-python"
                    )
                    self.server.register_resource(resource)
    
    def _get_mime_type(self, extension: str) -> str:
        """Get MIME type for file extension."""
        mime_types = {
            '.csv': 'text/csv',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.parquet': 'application/octet-stream',
            '.py': 'text/x-python'
        }
        return mime_types.get(extension, 'application/octet-stream')
    
    async def handle_tool_call(self, tool_name: str, arguments: dict) -> List[str]:
        """Handle tool calls by routing to appropriate handler."""
        try:
            # Route to appropriate handler based on tool name
            if tool_name in [tool.name for tool in self.file_handler.get_tools()]:
                result = await self.file_handler.handle_tool_call(tool_name, arguments)
            elif tool_name in [tool.name for tool in self.code_generation_handler.get_tools()]:
                result = await self.code_generation_handler.handle_tool_call(tool_name, arguments)
            elif tool_name in [tool.name for tool in self.data_processing_handler.get_tools()]:
                result = await self.data_processing_handler.handle_tool_call(tool_name, arguments)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
            
            # Convert TextContent to strings
            return [content.text for content in result]
            
        except Exception as e:
            logger.error(f"Error handling tool call {tool_name}: {str(e)}")
            return [f"Error: {str(e)}"]
    
    async def run(self):
        """Run the MCP server."""
        logger.info("Starting OryxForge MCP Server...")
        
        # Set up tool call handler
        self.server.set_tool_call_handler(self.handle_tool_call)
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream)

async def main():
    """Main entry point."""
    # Create server instance
    server = OryxForgeMCPServer()
    
    # Run the server
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())

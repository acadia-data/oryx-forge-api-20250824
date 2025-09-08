"""MCP server CLI commands for oryxforge tools."""

import click
import inspect
import sys
import os
import json
from pathlib import Path
from . import mcp as mcp_tools


def handle_mcp_request(request, registered_tools):
    """Handle MCP JSON-RPC request and return response."""
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params", {})
    
    try:
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "oryxforge",
                        "version": "0.1.0"
                    }
                }
            }
        
        elif method == "tools/list":
            tools = []
            for tool_name, tool in registered_tools.items():
                # FastMCP uses 'fn' attribute for the actual function
                func = tool.fn if hasattr(tool, 'fn') else None
                description = tool.description if hasattr(tool, 'description') else "No description"
                
                if func:
                    sig = inspect.signature(func)
                    doc = description or func.__doc__ or "No description"
                    
                    # Build input schema from function signature
                    properties = {}
                    required = []
                    for param_name, param in sig.parameters.items():
                        if param_name == 'self':
                            continue
                        
                        param_type = "string"  # Default to string
                        if param.annotation != inspect.Parameter.empty:
                            if param.annotation == int:
                                param_type = "integer"
                            elif param.annotation == float:
                                param_type = "number"
                            elif param.annotation == bool:
                                param_type = "boolean"
                            elif hasattr(param.annotation, '__origin__'):
                                if param.annotation.__origin__ == list:
                                    param_type = "array"
                        
                        properties[param_name] = {
                            "type": param_type,
                            "description": f"Parameter {param_name}"
                        }
                        
                        if param.default == inspect.Parameter.empty:
                            required.append(param_name)
                    
                    tools.append({
                        "name": tool_name,
                        "description": doc,
                        "inputSchema": {
                            "type": "object",
                            "properties": properties,
                            "required": required
                        }
                    })
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools}
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name not in registered_tools:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": f"Tool '{tool_name}' not found"}
                }
            
            tool = registered_tools[tool_name]
            if not hasattr(tool, 'fn'):
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": "Tool function not available"}
                }
            
            try:
                result = tool.fn(**arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": str(result)}]
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": f"Tool execution error: {str(e)}"}
                }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found"}
            }
    
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
        }


@click.group()
def mcp():
    """MCP server commands"""
    pass


@mcp.command()
@click.option('--transport', default='stdio', help='Transport type (stdio, ws)')
@click.option('--host', default='localhost', help='Server host (for ws transport)')
@click.option('--port', default=3000, type=int, help='Server port (for ws transport)')
@click.option('--protocol', is_flag=True, help='Run in MCP protocol mode (JSON-RPC over stdio)')
def serve(transport, host, port, protocol):
    """Start the MCP server"""
    click.echo(f"Starting OryxForge MCP server with {transport} transport...")
    click.echo(f"Transport: {transport}")
    click.echo(f"Working directory: {Path.cwd()}")
    click.echo(f"Tasks directory: {Path.cwd() / 'tasks'}")
    
    # Get tools from FastMCP instance tool manager (load once for both modes)
    registered_tools = mcp_tools.mcp._tool_manager._tools
    tool_count = len(registered_tools)
    
    if transport == 'stdio':
        if protocol:
            # MCP Protocol mode - handle JSON-RPC messages
            click.echo("MCP Server ready - JSON-RPC protocol mode", err=True)
            click.echo(f"Registered {tool_count} tools", err=True)
            for tool_name in registered_tools.keys():
                click.echo(f"- {tool_name}", err=True)
            
            # Handle JSON-RPC messages from stdin
            while True:
                try:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    
                    try:
                        request = json.loads(line.strip())
                        response = handle_mcp_request(request, registered_tools)
                        if response:
                            print(json.dumps(response), flush=True)
                    except json.JSONDecodeError:
                        # Invalid JSON - send error response
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {"code": -32700, "message": "Parse error"}
                        }
                        print(json.dumps(error_response), flush=True)
                except (KeyboardInterrupt, EOFError):
                    break
        else:
            # Interactive mode
            click.echo("MCP Server ready - Tools available via stdio interface")
            
            for tool_name, tool in registered_tools.items():
                click.echo(f"Registered tool: {tool_name}")
            
            click.echo(f"Registered {tool_count} tools")
            
            # Simple interactive loop for demonstration
            click.echo("\nAvailable commands:")
            click.echo("- list: Show all tools")
            click.echo("- call <tool_name> <args>: Call a tool")
            click.echo("- quit: Exit server")
            
            while True:
                try:
                    cmd = input("\nmcp> ").strip()
                    if not cmd:
                        continue
                        
                    if cmd == "quit":
                        break
                    elif cmd == "list":
                        click.echo("Available tools:")
                        for tool_name in registered_tools.keys():
                            click.echo(f"  - {tool_name}")
                    elif cmd.startswith("call "):
                        parts = cmd.split(" ", 2)
                        if len(parts) >= 2:
                            tool_name = parts[1]
                            if tool_name in registered_tools:
                                try:
                                    # Simple tool execution (would need proper JSON-RPC in real MCP)
                                    tool = registered_tools[tool_name]
                                    if hasattr(tool, 'fn'):
                                        result = tool.fn()
                                    else:
                                        result = "Tool execution not implemented for this tool type"
                                    click.echo(f"Result: {result}")
                                except Exception as e:
                                    click.echo(f"Error: {e}")
                            else:
                                click.echo(f"Unknown tool: {tool_name}")
                        else:
                            click.echo("Usage: call <tool_name>")
                    else:
                        click.echo("Unknown command. Try 'list', 'call <tool>', or 'quit'")
                except (KeyboardInterrupt, EOFError):
                    break
                    
            click.echo("\nMCP Server stopped")
    
    elif transport == 'ws':
        click.echo(f"WebSocket transport not yet implemented")
        sys.exit(1)

    elif transport == 'http':
        click.echo(f"Host: {host}:{port}")
        click.echo(f"HTTP transport not yet implemented")
        sys.exit(1)

    else:
        click.echo(f"Unknown transport: {transport}")
        sys.exit(1)


@mcp.command()
def list_tools():
    """List available MCP tools"""
    click.echo("Available MCP tools:")
    click.echo("=" * 50)
    
    # Get tools from FastMCP instance tool manager
    registered_tools = mcp_tools.mcp._tool_manager._tools
    tool_count = len(registered_tools)
    
    for tool_name, tool in registered_tools.items():
        # Get function signature and doc from the tool
        func = tool.func if hasattr(tool, 'func') else None
        if func:
            sig = inspect.signature(func)
            doc = func.__doc__ or "No description"
        else:
            sig = ""
            doc = tool.description if hasattr(tool, 'description') else "No description"
        
        click.echo(f"• {tool_name}{sig}")
        click.echo(f"  {doc}")
        click.echo()
    
    if tool_count == 0:
        click.echo("No MCP tools found")
    else:
        click.echo(f"Total: {tool_count} tools")


@mcp.command()
def version():
    """Show version information"""
    try:
        import mcp
        mcp_version = mcp.__version__
    except AttributeError:
        mcp_version = "unknown"
    
    click.echo(f"OryxForge MCP Server")
    click.echo(f"MCP Library Version: {mcp_version}")


if __name__ == '__main__':
    mcp()
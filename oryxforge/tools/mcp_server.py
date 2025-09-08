from oryxforge.tools.mcp import mcp as app
import click

@click.group()
def mcp():
    """MCP server commands"""
    pass


@mcp.command()
def serve():
    """Start the MCP server"""
    app.run()


if __name__ == "__main__":
    app.run()

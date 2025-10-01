import click


@click.group()
def mcp():
    """MCP server commands"""
    pass


@mcp.command()
def serve():
    """Start the MCP server"""
    from oryxforge.tools.mcp import mcp as app
    app.run()


if __name__ == "__main__":
    from oryxforge.tools.mcp import mcp as app
    app.run()

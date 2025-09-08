"""Main CLI entry point for oryxforge."""

import click


@click.group()
@click.version_option()
def cli():
    """OryxForge CLI - Task management and workflow tools"""
    pass


# Try to import and add MCP commands if available
try:
    from ..tools.mcp_server import mcp
    cli.add_command(mcp)
except ImportError:
    # MCP dependencies not installed, skip MCP commands
    pass


# Add other command groups here as they're developed
# Example:
# try:
#     from .tasks import tasks
#     cli.add_command(tasks)
# except ImportError:
#     pass


if __name__ == '__main__':
    cli()
"""Main CLI entry point for oryxforge."""

import click


@click.group()
@click.version_option()
def cli():
    """OryxForge CLI - Task management and workflow tools"""
    pass


# Import and add all command groups (always required)
from ..tools.mcp_server import mcp
from .admin import admin, git
from .agent import agent
from .dev import dev

cli.add_command(mcp)
cli.add_command(admin)
cli.add_command(agent)
cli.add_command(dev)
cli.add_command(git)


# Add other command groups here as they're developed
# Example:
# try:
#     from .tasks import tasks
#     cli.add_command(tasks)
# except ImportError:
#     pass


if __name__ == '__main__':
    cli()
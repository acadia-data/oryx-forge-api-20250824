"""Utility functions for CLI commands."""

import click
from functools import wraps


def handle_errors(func):
    """Decorator to handle common CLI errors with consistent messaging."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            click.echo(f"❌ Error: {str(e)}", err=True)
            raise click.Abort()
        except Exception as e:
            click.echo(f"❌ Unexpected error: {str(e)}", err=True)
            raise click.Abort()
    return wrapper

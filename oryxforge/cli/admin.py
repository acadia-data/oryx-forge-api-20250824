"""Admin CLI commands for oryxforge project and user management."""

import click
import os
from pathlib import Path
from typing import Optional
from ..services.cli_service import CLIService
from ..services.project_service import ProjectService


@click.group()
def admin():
    """Administrative commands for project and user management."""
    pass


@admin.group()
def userid():
    """User ID management commands."""
    pass


@userid.command('set')
@click.argument('user_id')
def set_userid(user_id: str):
    """
    Set the user ID for CLI operations.

    Args:
        user_id: UUID of the user from Supabase auth.users table
    """
    try:
        cli_service = CLIService.__new__(CLIService)
        cli_service._CLIService__init__ = lambda: None  # Skip normal init
        cli_service.set_user_config(user_id)
        click.echo(f"✅ User ID set successfully: {user_id}")
    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {str(e)}", err=True)
        raise click.Abort()


@userid.command('get')
def get_userid():
    """
    Get the current user ID from configuration.
    """
    try:
        user_id = CLIService.get_configured_user_id()

        if user_id:
            click.echo(f"Current user ID: {user_id}")
        else:
            click.echo("No user ID configured. Run 'oryxforge admin userid set <userid>' to set one.")

    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {str(e)}", err=True)
        raise click.Abort()


@admin.group()
def projects():
    """Project management commands."""
    pass


@projects.command('list')
def list_projects():
    """List all projects for the current user."""
    try:
        cli_service = CLIService()
        projects_list = cli_service.projects_list()

        if not projects_list:
            click.echo("No projects found for this user.")
            return

        click.echo("\nProjects for user:")
        click.echo("=" * 50)
        for project in projects_list:
            click.echo(f"ID: {project['id'][:8]}...  Name: {project['name']}")

    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {str(e)}", err=True)
        raise click.Abort()


@projects.command('create')
@click.argument('name')
def create_project(name: str):
    """
    Create a new project.

    Args:
        name: Project name (must be unique for user)
    """
    try:
        cli_service = CLIService()
        project_id = cli_service.projects_create(name)
        click.echo(f"✅ Created project '{name}' with ID: {project_id}")

    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {str(e)}", err=True)
        raise click.Abort()


@admin.command('pull')
@click.option('--id', 'project_id', help='Project ID to pull')
@click.option('--cwd', 'target_dir', default='.', help='Target directory (default: current directory)')
def pull_project(project_id: Optional[str], target_dir: str):
    """
    Pull project and activate it locally.

    If project ID is not provided, shows interactive project selection.
    """
    try:
        cli_service = CLIService()

        # Get project ID interactively if not provided
        if not project_id:
            click.echo("No project ID provided. Please select from available projects:")
            try:
                project_id = cli_service.interactive_project_select()
            except ValueError as e:
                click.echo(f"❌ {str(e)}", err=True)
                raise click.Abort()

        # Validate project exists
        if not cli_service.project_exists(project_id):
            click.echo(f"❌ Project {project_id} not found or access denied", err=True)
            raise click.Abort()

        # Initialize project service
        project_service = ProjectService(project_id, cli_service.user_id)

        # Check if project is initialized, initialize if needed
        if not project_service.is_initialized():
            click.echo("Project not initialized. Initializing...")
            project_service.project_init()

        # Pull git repository
        target_path = Path(target_dir).resolve()
        project_service.git_pull(str(target_path))

        # Change to target directory for activation
        original_cwd = Path.cwd()
        os.chdir(target_path)

        try:
            # Activate project
            cli_service_in_project = CLIService(cli_service.user_id, str(target_path))
            cli_service_in_project.project_activate(project_id)

            # Auto-activate default dataset and first sheet
            try:
                default_dataset_id = project_service.get_default_dataset_id()
                cli_service_in_project.dataset_activate(default_dataset_id)
                click.echo(f"✅ Activated default dataset: scratchpad")

                # Get first sheet in default dataset
                first_sheet_id = project_service.get_first_sheet_id(default_dataset_id)
                cli_service_in_project.sheet_activate(first_sheet_id)
                click.echo(f"✅ Activated first datasheet")

            except ValueError as e:
                click.echo(f"⚠️  Warning: Could not auto-activate dataset/sheet: {str(e)}")

            click.echo(f"✅ Project pulled and activated in: {target_path}")

        finally:
            # Restore original working directory
            os.chdir(original_cwd)

    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {str(e)}", err=True)
        raise click.Abort()


@admin.group()
def dataset():
    """Dataset management commands."""
    pass


@dataset.command('activate')
@click.option('--id', 'dataset_id', help='Dataset ID to activate')
@click.option('--name', 'dataset_name', help='Dataset name to activate')
def activate_dataset(dataset_id: Optional[str], dataset_name: Optional[str]):
    """
    Activate a dataset by ID or name.

    If neither ID nor name is provided, shows interactive selection.
    """
    try:
        cli_service = CLIService()

        # Get active project for context
        active_config = cli_service.get_active()
        if 'project_id' not in active_config:
            click.echo("❌ No active project. Run 'oryxforge admin pull' first.", err=True)
            raise click.Abort()

        project_service = ProjectService(active_config['project_id'], cli_service.user_id)

        # Determine dataset ID
        if dataset_id:
            # Validate dataset exists
            if not project_service.ds_exists(dataset_id):
                click.echo(f"❌ Dataset {dataset_id} not found or access denied", err=True)
                raise click.Abort()
        elif dataset_name:
            # Find dataset by name
            try:
                dataset_id = project_service.find_dataset_by_name(dataset_name)
            except ValueError as e:
                click.echo(f"❌ {str(e)}", err=True)
                # Show available datasets
                datasets = project_service.ds_list()
                if datasets:
                    click.echo("\nAvailable datasets:")
                    for ds in datasets:
                        click.echo(f"  - {ds['name']}")
                raise click.Abort()
        else:
            # Interactive selection
            click.echo("No dataset specified. Please select from available datasets:")
            try:
                dataset_id = project_service.interactive_dataset_select()
            except ValueError as e:
                click.echo(f"❌ {str(e)}", err=True)
                raise click.Abort()

        # Activate dataset
        cli_service.dataset_activate(dataset_id)
        click.echo(f"✅ Activated dataset: {dataset_id}")

    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {str(e)}", err=True)
        raise click.Abort()


@admin.group()
def sheet():
    """Datasheet management commands."""
    pass


@sheet.command('activate')
@click.option('--id', 'sheet_id', help='Datasheet ID to activate')
@click.option('--name', 'sheet_name', help='Datasheet name to activate')
def activate_sheet(sheet_id: Optional[str], sheet_name: Optional[str]):
    """
    Activate a datasheet by ID or name.

    If neither ID nor name is provided, shows interactive selection.
    """
    try:
        cli_service = CLIService()

        # Get active project for context
        active_config = cli_service.get_active()
        if 'project_id' not in active_config:
            click.echo("❌ No active project. Run 'oryxforge admin pull' first.", err=True)
            raise click.Abort()

        project_service = ProjectService(active_config['project_id'], cli_service.user_id)

        # Get active dataset if available
        active_dataset_id = active_config.get('dataset_id')

        # Determine sheet ID
        if sheet_id:
            # Validate sheet exists
            if not project_service.sheet_exists(sheet_id):
                click.echo(f"❌ Datasheet {sheet_id} not found or access denied", err=True)
                raise click.Abort()
        elif sheet_name:
            # Find sheet by name
            try:
                sheet_id = project_service.find_sheet_by_name(sheet_name, active_dataset_id)
            except ValueError as e:
                click.echo(f"❌ {str(e)}", err=True)
                # Show available sheets
                sheets = project_service.sheet_list(active_dataset_id)
                if sheets:
                    context = "active dataset" if active_dataset_id else "project"
                    click.echo(f"\nAvailable datasheets in {context}:")
                    for sheet in sheets:
                        click.echo(f"  - {sheet['name']}")
                raise click.Abort()
        else:
            # Interactive selection
            context = "active dataset" if active_dataset_id else "project"
            click.echo(f"No datasheet specified. Please select from available datasheets in {context}:")
            try:
                sheet_id = project_service.interactive_sheet_select(active_dataset_id)
            except ValueError as e:
                click.echo(f"❌ {str(e)}", err=True)
                raise click.Abort()

        # Activate sheet
        cli_service.sheet_activate(sheet_id)
        click.echo(f"✅ Activated datasheet: {sheet_id}")

    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {str(e)}", err=True)
        raise click.Abort()


# Additional utility commands
@admin.command('status')
def show_status():
    """Show current configuration status."""
    try:
        cli_service = CLIService()

        # Show user info
        config = cli_service.get_user_config()
        click.echo(f"User ID: {config.get('userid', 'Not set')}")

        # Show active project info
        active_config = cli_service.get_active()
        if active_config:
            click.echo(f"Active Project: {active_config.get('project_id', 'None')}")
            click.echo(f"Active Dataset: {active_config.get('dataset_id', 'None')}")
            click.echo(f"Active Datasheet: {active_config.get('sheet_id', 'None')}")
        else:
            click.echo("No active project configuration found")

        # Show working directory
        click.echo(f"Working Directory: {Path.cwd()}")

    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {str(e)}", err=True)
        raise click.Abort()


@admin.command('config')
@click.option('--global', 'show_global', is_flag=True, help='Show global configuration')
@click.option('--project', 'show_project', is_flag=True, help='Show project configuration')
def show_config(show_global: bool, show_project: bool):
    """Show configuration files content."""
    try:
        cli_service = CLIService()

        if show_global or (not show_global and not show_project):
            click.echo("Global Configuration:")
            click.echo("=" * 30)
            if cli_service.config_file.exists():
                click.echo(f"File: {cli_service.config_file}")
                click.echo(cli_service.config_file.read_text())
            else:
                click.echo("No global configuration file found")
            click.echo()

        if show_project or (not show_global and not show_project):
            click.echo("Project Configuration:")
            click.echo("=" * 30)
            if cli_service.project_config_file.exists():
                click.echo(f"File: {cli_service.project_config_file}")
                click.echo(cli_service.project_config_file.read_text())
            else:
                click.echo("No project configuration file found")

    except Exception as e:
        click.echo(f"❌ Unexpected error: {str(e)}", err=True)
        raise click.Abort()


if __name__ == '__main__':
    admin()
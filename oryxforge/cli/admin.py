"""Admin CLI commands for oryxforge project and user management."""

import click
import os
from pathlib import Path
from typing import Optional
from .utils import handle_errors
from ..services.cli_service import CLIService
from ..services.project_service import ProjectService


@click.group()
def admin():
    """Administrative commands for project and user management."""
    pass


@admin.group()
def profile():
    """Profile management commands (user_id and project_id)."""
    pass


@profile.command('set')
@click.option('--userid', required=True, help='User ID from web UI profile dropdown')
@click.option('--projectid', required=True, help='Project ID to activate')
@handle_errors
def set_profile(userid: str, projectid: str):
    """
    Set the user profile (user_id and project_id) for CLI operations.

    Args:
        userid: UUID of the user from Supabase auth.users table
        projectid: UUID of the project to activate
    """
    from ..services.iam import CredentialsManager
    from pathlib import Path

    creds_manager = CredentialsManager(working_dir=str(Path.cwd()))
    creds_manager.set_profile(user_id=userid, project_id=projectid)
    click.echo(f"✅ Profile set successfully")
    click.echo(f"   User ID: {userid}")
    click.echo(f"   Project ID: {projectid}")


@profile.command('get')
@handle_errors
def get_profile():
    """
    Get the current profile (user_id and project_id) from configuration.
    """
    from ..services.iam import CredentialsManager
    from pathlib import Path

    try:
        creds_manager = CredentialsManager(working_dir=str(Path.cwd()))
        profile_data = creds_manager.get_profile()
        click.echo(f"Current profile:")
        click.echo(f"  User ID: {profile_data['user_id']}")
        click.echo(f"  Project ID: {profile_data['project_id']}")
    except ValueError as e:
        click.echo(f"No profile configured.\n{str(e)}")


@profile.command('clear')
@handle_errors
def clear_profile():
    """
    Clear the current profile configuration.
    """
    from ..services.iam import CredentialsManager
    from pathlib import Path

    creds_manager = CredentialsManager(working_dir=str(Path.cwd()))
    creds_manager.clear_profile()
    click.echo("✅ Profile cleared")


@admin.group()
def projects():
    """Project management commands."""
    pass


@projects.command('list')
@handle_errors
def list_projects():
    """List all projects for the current user."""
    cli_service = CLIService()
    projects_list = cli_service.projects_list()

    if not projects_list:
        click.echo("No projects found for this user.")
        return

    click.echo("\nProjects for user:")
    click.echo("=" * 50)
    for project in projects_list:
        click.echo(f"ID: {project['id']}  Name: {project['name']}")


@projects.command('create')
@click.argument('name')
@handle_errors
def create_project(name: str):
    """
    Create a new project.

    Args:
        name: Project name (must be unique for user)
    """
    cli_service = CLIService()
    project_id = cli_service.projects_create(name)
    click.echo(f"✅ Created project '{name}' with ID: {project_id}")


@admin.command('pull')
@click.option('--id', 'project_id', help='Project ID to pull')
@click.option('--cwd', 'target_dir', default='.', help='Target directory (default: current directory)')
@handle_errors
def pull_project(project_id: Optional[str], target_dir: str):
    """
    Pull project and activate it locally.

    If project ID is not provided, shows interactive project selection.
    """
    cli_service = CLIService()

    # Get project ID interactively if not provided
    if not project_id:
        click.echo("No project ID provided. Please select from available projects:")
        project_id = cli_service.interactive_project_select()

    # Validate project exists
    if not cli_service.project_exists(project_id):
        raise ValueError(f"Project {project_id} not found or access denied")

    # Initialize project service (uses CredentialsManager from current directory)
    project_service = ProjectService(project_id=project_id, user_id=cli_service.user_id)

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
 
        # Auto-activate default dataset and first sheet
        try:
            default_dataset_id = project_service._get_default_dataset_id()
            cli_service_in_project.dataset_activate(default_dataset_id)
            click.echo(f"✅ Activated default dataset: exploration")

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


@admin.group()
def datasets():
    """Dataset management commands."""
    pass


@datasets.command('list')
@handle_errors
def list_datasets():
    """List all datasets for the current project."""
    from ..services.iam import CredentialsManager

    # Get profile for user_id and project_id
    creds_manager = CredentialsManager(working_dir=str(Path.cwd()))
    profile = creds_manager.get_profile()

    # Initialize ProjectService
    project_service = ProjectService(
        project_id=profile['project_id'],
        user_id=profile['user_id']
    )

    # Get datasets list
    datasets = project_service.ds_list()

    if not datasets:
        click.echo("No datasets found for this project.")
        return

    click.echo("\nDatasets:")
    click.echo("=" * 80)
    for dataset in datasets:
        click.echo(f"ID: {dataset['id']}")
        click.echo(f"  Name: {dataset['name']}")
        click.echo(f"  Python Name: {dataset['name_python']}")
        click.echo("-" * 80)


@datasets.command('activate')
@click.option('--id', 'dataset_id', help='Dataset ID to activate')
@click.option('--name', 'dataset_name', help='Dataset name to activate')
@handle_errors
def activate_dataset(dataset_id: Optional[str], dataset_name: Optional[str]):
    """
    Activate a dataset by ID or name.

    If neither ID nor name is provided, shows interactive selection.
    """
    cli_service = CLIService()

    # Get active project for context
    active_config = cli_service.get_active()
    if 'project_id' not in active_config:
        raise ValueError("No active project. Run 'oryxforge admin pull' first.")

    project_service = ProjectService(project_id=active_config['project_id'], user_id=cli_service.user_id)

    # Determine dataset ID
    if dataset_id:
        # Validate dataset exists
        if not project_service.ds_exists(dataset_id):
            raise ValueError(f"Dataset {dataset_id} not found or access denied")
    elif dataset_name:
        # Find dataset by name
        try:
            dataset = project_service.ds_get(name=dataset_name)
            dataset_id = dataset['id']
        except ValueError as e:
            # Show available datasets
            datasets = project_service.ds_list()
            if datasets:
                click.echo("\nAvailable datasets:")
                for ds in datasets:
                    click.echo(f"  - {ds['name']}")
            raise e
    else:
        # Interactive selection
        click.echo("No dataset specified. Please select from available datasets:")
        dataset_id = project_service.interactive_dataset_select()

    # Activate dataset
    cli_service.dataset_activate(dataset_id)
    click.echo(f"✅ Activated dataset: {dataset_id}")


@admin.group()
def mode():
    """Project mode management commands."""
    pass


@mode.command('set')
@click.argument('mode_value', type=click.Choice(['explore', 'edit', 'plan'], case_sensitive=False))
@handle_errors
def set_mode(mode_value: str):
    """
    Set the project mode.

    MODE_VALUE: Project mode (explore, edit, or plan)

    Examples:
        oryxforge admin mode set explore
        oryxforge admin mode set edit
        oryxforge admin mode set plan
    """
    cli_service = CLIService()

    # Validate mode using CLIService constants
    mode_lower = mode_value.lower()
    if mode_lower not in CLIService.VALID_MODES:
        raise ValueError(f"Invalid mode '{mode_value}'. Must be one of: {', '.join(sorted(CLIService.VALID_MODES))}")

    cli_service.mode_set(mode_lower)
    click.echo(f"✅ Project mode set to '{mode_lower}'")


@mode.command('get')
@handle_errors
def get_mode():
    """
    Get the current project mode.

    Example:
        oryxforge admin mode get
    """
    cli_service = CLIService()
    current_mode = cli_service.mode_get()

    if current_mode:
        click.echo(f"Current project mode: {current_mode}")
    else:
        click.echo("No project mode set.")
        click.echo(f"Available modes: {', '.join(sorted(CLIService.VALID_MODES))}")
        click.echo("Set a mode with: oryxforge admin mode set <mode>")


@admin.group()
def sheets():
    """Datasheet management commands."""
    pass


@sheets.command('list')
@click.option('--dataset-id', help='Dataset ID to filter sheets by')
@handle_errors
def list_sheets(dataset_id: Optional[str]):
    """
    List all datasheets for the current project.

    Optionally filter by dataset using --dataset-id.
    """
    from ..services.iam import CredentialsManager

    # Get profile for user_id and project_id
    creds_manager = CredentialsManager(working_dir=str(Path.cwd()))
    profile = creds_manager.get_profile()

    # Initialize ProjectService
    project_service = ProjectService(
        project_id=profile['project_id'],
        user_id=profile['user_id']
    )

    # Get sheets list (optionally filtered by dataset_id)
    sheets = project_service.sheet_list(dataset_id=dataset_id)

    if not sheets:
        context = f"dataset {dataset_id}" if dataset_id else "this project"
        click.echo(f"No datasheets found in {context}.")
        return

    context_msg = f"Datasheets for dataset {dataset_id}" if dataset_id else "All Datasheets"
    click.echo(f"\n{context_msg}:")
    click.echo("=" * 80)
    for sheet in sheets:
        click.echo(f"ID: {sheet['id']}")
        click.echo(f"  Name: {sheet['name']}")
        click.echo(f"  Python Name: {sheet['name_python']}")
        click.echo(f"  Dataset ID: {sheet['dataset_id']}")
        click.echo("-" * 80)


@sheets.command('activate')
@click.option('--id', 'sheet_id', help='Datasheet ID to activate')
@click.option('--name', 'sheet_name', help='Datasheet name to activate')
@handle_errors
def activate_sheet(sheet_id: Optional[str], sheet_name: Optional[str]):
    """
    Activate a datasheet by ID or name.

    If neither ID nor name is provided, shows interactive selection.
    """
    cli_service = CLIService()

    # Get active project for context
    active_config = cli_service.get_active()
    if 'project_id' not in active_config:
        raise ValueError("No active project. Run 'oryxforge admin pull' first.")

    project_service = ProjectService(project_id=active_config['project_id'], user_id=cli_service.user_id)

    # Get active dataset if available
    active_dataset_id = active_config.get('dataset_id')

    # Determine sheet ID
    if sheet_id:
        # Validate sheet exists
        if not project_service.sheet_exists(sheet_id):
            raise ValueError(f"Datasheet {sheet_id} not found or access denied")
    elif sheet_name:
        # Find sheet by name
        try:
            sheet = project_service.sheet_get(dataset_id=active_dataset_id, name=sheet_name)
            sheet_id = sheet['id']
        except ValueError as e:
            # Show available sheets
            sheets = project_service.sheet_list(active_dataset_id)
            if sheets:
                context = "active dataset" if active_dataset_id else "project"
                click.echo(f"\nAvailable datasheets in {context}:")
                for sheet in sheets:
                    click.echo(f"  - {sheet['name']}")
            raise e
    else:
        # Interactive selection
        context = "active dataset" if active_dataset_id else "project"
        click.echo(f"No datasheet specified. Please select from available datasheets in {context}:")
        sheet_id = project_service.interactive_sheet_select(active_dataset_id)

    # Activate sheet
    cli_service.sheet_activate(sheet_id)
    click.echo(f"✅ Activated datasheet: {sheet_id}")


# Additional utility commands
@admin.command('status')
@handle_errors
def show_status():
    """Show current configuration status."""
    from ..services.iam import CredentialsManager

    # Show profile info
    try:
        creds_manager = CredentialsManager(working_dir=str(Path.cwd()))
        profile = creds_manager.get_profile()
        click.echo(f"User ID: {profile.get('user_id', 'Not set')}")
        click.echo(f"Project ID: {profile.get('project_id', 'Not set')}")
    except ValueError:
        click.echo("User ID: Not set")
        click.echo("Project ID: Not set")
        click.echo("\nNo profile configured. Run 'oryxforge admin profile set --userid <userid> --projectid <projectid>'")
        return

    # Show active dataset/sheet/mode info
    cli_service = CLIService()
    active_config = cli_service.get_active()
    if active_config:
        click.echo(f"Active Dataset: {active_config.get('dataset_id', 'None')}")
        click.echo(f"Active Datasheet: {active_config.get('sheet_id', 'None')}")
        click.echo(f"Project Mode: {active_config.get('mode', 'None')}")

    # Show working directory
    click.echo(f"Working Directory: {Path.cwd()}")


@admin.command('config')
@click.option('--project', 'show_project', is_flag=True, help='Show project configuration')
@handle_errors
def show_config(show_project: bool):
    """Show configuration files content."""
    cli_service = CLIService()

    click.echo("Project Configuration:")
    click.echo("=" * 30)
    if cli_service.project_config_file.exists():
        click.echo(f"File: {cli_service.project_config_file}")
        click.echo(cli_service.project_config_file.read_text())
    else:
        click.echo("No project configuration file found")


@projects.command('import')
@click.argument('filepath', type=click.Path(exists=True))
@handle_errors
def import_file(filepath: str):
    """
    Import a file into the active project's "Sources" dataset.

    FILEPATH: Path to the file to import (CSV, Excel, or Parquet)

    The command imports to the "Sources" dataset in the active project configured via:
        oryxforge admin profile set --userid <userid> --projectid <projectid>

    Examples:
        # First set profile (one-time setup)
        oryxforge admin profile set --userid "aaa" --projectid "bbb"

        # Import file to Sources dataset
        oryxforge admin projects import data.csv
    """
    cli_service = CLIService()

    # Import the file and get detailed result
    result = cli_service.import_file(path=filepath)

    click.echo(f"✅ {result['message']}")

    # Ask if user wants to activate the imported sheet
    if click.confirm(f'\nDo you want to activate the imported sheet "{result["file_name"]}"?', default=True):
        try:
            # Activate the Sources dataset
            cli_service.dataset_activate(result['dataset_id'])

            # Activate the sheet
            cli_service.sheet_activate(result['sheet_id'])

            click.echo(f"✅ Activated dataset '{result['dataset_name']}' and sheet '{result['file_name']}'")
        except Exception as e:
            click.echo(f"⚠️  Warning: Could not activate sheet: {str(e)}", err=True)


@admin.group()
def data():
    """Data management commands."""
    pass


@data.command('list')
@handle_errors
def list_data():
    """
    List all datasets and datasheets in the current project.

    Shows a table with dataset names, sheet names, and combined Python notation
    (dataset.sheet) for easy reference.

    Requires an active profile. Configure with:
        oryxforge admin profile set --userid <userid> --projectid <projectid>

    Example:
        oryxforge admin data list
    """
    # Initialize ProjectService (reads from .oryxforge profile)
    project_service = ProjectService()

    # Get dataframe
    df = project_service.ds_sheet_list(format='df')

    if df.empty:
        click.echo("No datasets or datasheets found in this project.")
        return

    # Print as markdown table
    click.echo("\nDatasets and Datasheets:")
    click.echo("=" * 80)
    click.echo(df.to_markdown(index=False))
    click.echo("=" * 80)
    click.echo(f"\nTotal: {len(df)} datasheet(s)")


@admin.group()
def agent():
    """AI agent commands for interactive data analysis."""
    pass


@agent.command('chat')
@click.argument('message')
@handle_errors
def chat_command(message: str):
    """
    Chat with the AI agent for interactive data analysis.

    MESSAGE: Your question or request for the AI agent

    The agent will analyze your request, determine the appropriate data operations,
    and generate code to perform the analysis.

    Examples:
        # Analyze data in the active sheet
        oryxforge agent chat "show me summary statistics"

        # Create a new analysis
        oryxforge agent chat "create a chart of sales by region"

        # Edit existing analysis
        oryxforge agent chat "add a trend line to the chart"

    Prerequisites:
        - Profile must be configured: oryxforge admin profile set --userid <id> --projectid <id>
        - Dataset and sheet should be activated (optional but recommended)
        - Mode can be set: oryxforge admin mode set explore
    """
    cli_service = CLIService()

    try:
        # Process chat message
        result = cli_service.chat(message=message)

        # Display agent response
        click.echo("\n" + "=" * 80)
        click.echo("AI Agent Response:")
        click.echo("=" * 80)
        click.echo(result['message'])
        click.echo("=" * 80)

        # Display metadata
        click.echo(f"\n📊 Target: {result['target_dataset']}.{result['target_sheet']}")
        click.echo(f"💰 Cost: ${result['cost_usd']:.4f}")
        click.echo(f"⏱️  Duration: {result['duration_ms']}ms")

    except ValueError as e:
        click.echo(f"\n❌ {str(e)}", err=True)
        click.echo("\nPlease clarify your request or check your configuration.", err=True)
        raise click.Abort()


if __name__ == '__main__':
    admin()
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
def config():
    """Configuration management commands."""
    pass


@config.command('show')
@handle_errors
def show_config():
    """Show configuration file content."""
    cli_service = CLIService()
    config_file = cli_service.config_service.config_file

    click.echo("Project Configuration:")
    click.echo("=" * 30)
    if config_file.exists():
        click.echo(f"File: {config_file}")
        click.echo(config_file.read_text())
    else:
        click.echo("No project configuration file found")


@config.group()
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

    # Strip whitespace from UUID parameters
    userid = userid.strip()
    projectid = projectid.strip()

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
@click.option('--userid', required=True, help='User ID')
@handle_errors
def create_project(name: str, userid: str):
    """
    Create a new project (no profile required).

    Args:
        name: Project name (must be unique for user)
        userid: User ID from Supabase auth.users table
    """
    # Strip whitespace from UUID parameter
    userid = userid.strip()

    # Call ProjectService.create_project directly (classmethod, no profile needed)
    project_id = ProjectService.create_project(name, userid, setup_repo=True)
    click.echo(f"✅ Created project '{name}' with ID: {project_id}")
    click.echo(f"\nNext steps:")
    click.echo(f"  1. Pull project: oryxforge admin pull --projectid {project_id} --userid {userid}")
    click.echo(f"  OR use 'init' to create and pull in one step:")
    click.echo(f"     oryxforge admin projects init '{name}' --userid {userid}")


@projects.command('init')
@click.argument('name')
@click.option('--userid', required=True, help='User ID')
@click.option('--target', help='Target directory (default: auto-generate from project name)')
@handle_errors
def init_project(name: str, userid: str, target: Optional[str]):
    """
    Create a new project and initialize it locally (create + pull in one step).

    This is the recommended way to set up a new project. It creates the project
    in the database, creates the GitLab repository, clones it locally, and sets
    up the configuration file.

    Args:
        name: Project name (must be unique for user)
        userid: User UUID (from Supabase auth.users table)
        target: Optional target directory (default: auto-generate from project name)

    Examples:
        oryxforge admin projects init "My Project" --userid <user-id>
        oryxforge admin projects init "My Project" --userid <user-id> --target ./my-folder
    """
    # Strip whitespace from UUID parameter
    userid = userid.strip()

    # Step 1: Create project in DB + GitLab
    click.echo(f"Creating project '{name}'...")
    project_id = ProjectService.create_project(name, userid, setup_repo=True)
    click.echo(f"✅ Created project with ID: {project_id}")

    # Step 2: Initialize locally (clone + config)
    click.echo(f"\nInitializing project locally...")
    target_dir = ProjectService.project_init(
        project_id=project_id,
        user_id=userid,
        target_dir=target
    )

    click.echo(f"\n✅ Project '{name}' is ready!")
    click.echo(f"   Location: {target_dir}")
    click.echo(f"\nNext steps:")
    click.echo(f"  cd {target_dir}")
    click.echo(f"  # Start working on your project!")


@admin.command('pull')
@click.option('--projectid', required=True, help='Project ID to pull')
@click.option('--userid', required=True, help='User ID')
@click.option('--target', help='Target directory (default: auto-generate from project name)')
@handle_errors
def pull_project(projectid: str, userid: str, target: Optional[str]):
    """
    Pull/clone a project repository and set up local config.

    Creates a new directory for the project, clones the repository, and sets up
    the .oryxforge.cfg file inside the project directory.

    Args:
        projectid: Project UUID to pull
        userid: User UUID (from Supabase auth.users table)
        target: Optional target directory (default: auto-generate from project name)

    Examples:
        oryxforge admin pull --projectid <project-id> --userid <user-id>
        oryxforge admin pull --projectid <project-id> --userid <user-id> --target ./my-folder
    """
    # Strip whitespace from UUID parameters
    projectid = projectid.strip()
    userid = userid.strip()

    # Use project_init workflow
    target_dir = ProjectService.project_init(
        project_id=projectid,
        user_id=userid,
        target_dir=target
    )

    click.echo(f"✅ Project pulled to: {target_dir}")
    click.echo(f"\nNext steps:")
    click.echo(f"  cd {target_dir}")
    click.echo(f"  # Start working on your project!")


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


@config.group()
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
        oryxforge admin config mode set explore
        oryxforge admin config mode set edit
        oryxforge admin config mode set plan
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
        oryxforge admin config mode get
    """
    cli_service = CLIService()
    current_mode = cli_service.mode_get()

    if current_mode:
        click.echo(f"Current project mode: {current_mode}")
    else:
        click.echo("No project mode set.")
        click.echo(f"Available modes: {', '.join(sorted(CLIService.VALID_MODES))}")
        click.echo("Set a mode with: oryxforge admin config mode set <mode>")


@config.group()
def mount():
    """Mount point configuration commands."""
    pass


@mount.command('set')
@click.argument('mount_point')
@handle_errors
def set_mount_point(mount_point: str):
    """
    Set the mount point for the project data directory.

    MOUNT_POINT: Absolute path to use as mount point (e.g., 'D:\\data' on Windows, '/mnt/data' on Linux)

    The mount point will be saved in the project configuration and used automatically
    when initializing ProjectService.

    Examples:
        # Windows
        oryxforge admin config mount set "D:\\data"

        # Linux/macOS
        oryxforge admin config mount set "/mnt/data"
    """
    cli_service = CLIService()
    cli_service.mount_point_set(mount_point)
    click.echo(f"✅ Mount point set to: {mount_point}")


@mount.command('get')
@handle_errors
def get_mount_point():
    """
    Get the configured mount point.

    Example:
        oryxforge admin config mount get
    """
    cli_service = CLIService()
    mount_point = cli_service.mount_point_get()

    if mount_point:
        click.echo(f"Current mount point: {mount_point}")
    else:
        click.echo("No mount point configured. Using default: ./data")
        click.echo("Set a mount point with: oryxforge admin config mount set <path>")


@mount.command('suggest')
@click.argument('base_path')
@handle_errors
def suggest_mount_point(base_path: str):
    """
    Suggest a mount point with user/project hierarchy.

    Takes a base path and automatically appends /{user_id}/{project_id}/data
    to create a project-specific mount point.

    BASE_PATH: Base directory for mount points (e.g., 'D:\\data\\oryx-forge')

    This creates an organized structure:
    - Each user has their own subdirectory
    - Each project has its own subdirectory under the user
    - Data is mounted in a 'data' subdirectory

    Examples:
        # Windows - suggest path
        oryxforge admin config mount suggest "D:\\data\\oryx-forge"

        # Linux/macOS - suggest path
        oryxforge admin config mount suggest "/mnt/oryx-forge"

    Prerequisites:
        - Profile must be configured with userid and projectid
    """
    cli_service = CLIService()

    try:
        # Get suggested path
        suggested_path = cli_service.mount_point_suggest(base_path)

        # Display suggestion
        click.echo(f"Suggested mount point: {suggested_path}")

        # Ask if user wants to set it
        if click.confirm(f'\nDo you want to set this as your mount point?', default=True):
            # Create parent directories
            parent_dir = Path(suggested_path).parent
            parent_dir.mkdir(parents=True, exist_ok=True)
            click.echo(f"Created directory: {parent_dir}")

            cli_service.mount_point_set(suggested_path)
            click.echo(f"✅ Mount point set to: {suggested_path}")

            # Ask if user wants to mount it now
            if click.confirm(f'\nDo you want to mount the data directory now?', default=True):
                # Initialize ProjectService with mount_ensure=False to prevent auto-mount
                project_service = ProjectService(mount_ensure=False)

                # Attempt to mount
                if project_service.mount():
                    click.echo(f"✅ Successfully mounted data directory at {project_service.mount_point}")
                else:
                    click.echo(f"❌ Failed to mount data directory", err=True)
        else:
            click.echo("\nMount point not set. You can set it later with:")
            click.echo(f"  oryxforge admin config mount set \"{suggested_path}\"")

    except ValueError as e:
        click.echo(f"\n❌ {str(e)}", err=True)
        raise click.Abort()


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


@admin.group()
def sources():
    """Data source management commands."""
    pass


@sources.command('import')
@click.argument('filepath', type=click.Path(exists=True))
@handle_errors
def import_file(filepath: str):
    """
    Import a file into the active project's "Sources" dataset.

    FILEPATH: Path to the file to import (CSV, Excel, or Parquet)

    The command imports to the "Sources" dataset in the active project configured via:
        oryxforge admin config profile set --userid <userid> --projectid <projectid>

    Examples:
        # First set profile (one-time setup)
        oryxforge admin config profile set --userid "aaa" --projectid "bbb"

        # Import file to Sources dataset
        oryxforge admin sources import data.csv
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


@sources.command('list')
@handle_errors
def list_sources():
    """
    List all imported data sources for the current project.

    Shows sources imported through the 'admin sources import' command.
    """
    cli_service = CLIService()
    sources_list = cli_service.sources_list()

    if not sources_list:
        click.echo("No data sources found for this project.")
        return

    click.echo("\nData Sources:")
    click.echo("=" * 80)
    for source in sources_list:
        click.echo(f"Name: {source['name']}")
        click.echo(f"  Type: {source['file_type']}")
        click.echo(f"  Rows: {source.get('row_count', 'N/A')}")
        click.echo(f"  Imported: {source['created_at']}")
        click.echo("-" * 80)


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


@admin.command('mount')
@handle_errors
def mount_project():
    """
    Mount the project data directory using rclone.

    Mounts the GCS bucket for the current project to the configured mount point.
    The data directory will be accessible as a local filesystem.

    Prerequisites:
        - Profile must be configured: oryxforge admin config profile set --userid <id> --projectid <id>
        - rclone must be installed and configured
        - (Optional) Mount point configured: oryxforge admin config mount set <path>

    Example:
        oryxforge admin mount
    """
    # Initialize ProjectService with mount_ensure=False to prevent auto-mount
    project_service = ProjectService(mount_ensure=False)

    # Attempt to mount
    if project_service.mount():
        click.echo(f"✅ Successfully mounted data directory at {project_service.mount_point}")
        click.echo(f"   GCS path: oryx-forge-gcs:orxy-forge-datasets-dev/{project_service.user_id}/{project_service.project_id}")
    else:
        click.echo(f"❌ Failed to mount data directory", err=True)
        raise click.Abort()


@admin.command('unmount')
@handle_errors
def unmount_project():
    """
    Unmount the project data directory.

    Unmounts the rclone-mounted data directory for the current project.

    Prerequisites:
        - Profile must be configured: oryxforge admin config profile set --userid <id> --projectid <id>
        - Data directory must be currently mounted

    Example:
        oryxforge admin unmount
    """
    # Initialize ProjectService with mount_ensure=False to prevent auto-mount
    project_service = ProjectService(mount_ensure=False)

    # Attempt to unmount
    if project_service.unmount():
        click.echo(f"✅ Successfully unmounted data directory at {project_service.mount_point}")
    else:
        click.echo(f"❌ Failed to unmount data directory", err=True)
        raise click.Abort()


# Git command group (separate from admin, accessible as 'oryxforge git')
@click.group()
def git():
    """Git repository management commands."""
    pass


@git.command('push')
@click.option('--message', '-m', help='Commit message (default: edits <timestamp>)')
@handle_errors
def push_command(message: str = None):
    """
    Commit and push all changes (modified and untracked) to remote repository.

    Stages all changes (modified files, new files, and deletions), creates a commit,
    and pushes to the remote GitLab repository.

    Equivalent to: git add -A && git commit -m <message> && git push

    Args:
        message: Optional commit message. If not provided, defaults to "edits <UTC timestamp>"

    Examples:
        # Push with auto-generated timestamp message
        oryxforge git push

        # Push with custom message
        oryxforge git push -m "Updated analysis"
        oryxforge git push --message "Fixed bug in data processing"

    Prerequisites:
        - Must be run from within a project directory
        - Project must be configured with .oryxforge.cfg
        - Git repository must exist (created via 'oryxforge admin projects init')
    """
    from datetime import datetime
    from ..services.repo_service import RepoService

    # Default message with UTC timestamp
    if not message:
        message = f"edits {datetime.utcnow().isoformat()}"

    repo_service = RepoService()
    commit_hash = repo_service.push(message)

    click.echo(f"✅ Successfully pushed commit: {commit_hash[:8]}")
    click.echo(f"   Message: {message}")


@git.command('pull')
@handle_errors
def pull_command():
    """
    Pull latest changes from remote repository.

    Fetches changes from the remote GitLab repository and merges them into
    the current branch (main/master).

    Equivalent to: git pull origin main

    Examples:
        # Pull latest changes
        oryxforge git pull

    Prerequisites:
        - Must be run from within a project directory
        - Project must be configured with .oryxforge.cfg
        - Git repository must exist locally

    Note:
        This performs a fast-forward merge. If there are local uncommitted changes
        that conflict with remote changes, the pull may fail. Consider committing
        or stashing local changes first.
    """
    from ..services.repo_service import RepoService

    repo_service = RepoService()
    repo_service.pull()

    click.echo(f"✅ Successfully pulled latest changes")


if __name__ == '__main__':
    admin()
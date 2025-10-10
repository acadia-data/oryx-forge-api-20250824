"""Development and debugging CLI commands for oryxforge."""

import click
import json
from pathlib import Path
from .utils import handle_errors
from ..services.cli_service import CLIService
from ..services.chat_service import ChatService
from ..services.iam import CredentialsManager


@click.group()
def dev():
    """Development and debugging commands."""
    pass


@dev.command('intent')
@click.argument('message')
@handle_errors
def intent_classify(message: str):
    """
    Test intent classification without saving to database.

    MESSAGE: User message to classify

    This command runs only the intent classification step to help debug
    and validate the intent classification logic without side effects.

    Examples:
        # Test new analysis intent
        oryxforge dev intent "show me summary statistics"

        # Test edit intent
        oryxforge dev intent "add a trend line"

        # Test with different modes
        oryxforge admin mode set explore
        oryxforge dev intent "create a chart of sales"
    """
    # Get credentials
    creds_manager = CredentialsManager(working_dir=str(Path.cwd()))
    try:
        profile = creds_manager.get_profile()
    except ValueError as e:
        click.echo(f"\n❌ {str(e)}", err=True)
        raise click.Abort()

    # Get mode and active context
    cli_service = CLIService()
    mode = cli_service.mode_get() or 'explore'
    active_config = cli_service.get_active()

    # Call ChatService.intent() directly
    chat_service = ChatService(profile['user_id'], profile['project_id'])

    try:
        result = chat_service.intent(
            message_user=message,
            mode=mode,
            ds_active=active_config.get('dataset_id'),
            sheet_active=active_config.get('sheet_id'),
            chat_history=[]  # Empty for debug command
        )

        # Display results
        click.echo("\n" + "=" * 80)
        click.echo("Intent Classification Result:")
        click.echo("=" * 80)

        click.echo(f"\nAction: {result['action']}")
        click.echo(f"Confidence: {result.get('confidence', 'N/A')}")

        if result.get('inputs'):
            click.echo(f"\nInputs ({len(result['inputs'])} sources):")
            for inp in result['inputs']:
                click.echo(f"  - {inp['dataset']}.{inp['sheet']}")
        else:
            click.echo("\nInputs: None")

        if result.get('targets'):
            click.echo(f"\nTargets ({len(result['targets'])} destination):")
            for target in result['targets']:
                is_new_marker = " (NEW)" if target.get('is_new') else " (EXISTING)"
                click.echo(f"  - {target['dataset']}.{target['sheet']}{is_new_marker}")
        else:
            click.echo("\nTargets: None")

        # Show raw JSON for debugging
        click.echo("\nRaw JSON:")
        click.echo("-" * 80)
        click.echo(json.dumps(result, indent=2))
        click.echo("=" * 80)

    except ValueError as e:
        click.echo(f"\n❌ Intent classification failed: {str(e)}", err=True)
        raise click.Abort()


if __name__ == '__main__':
    dev()

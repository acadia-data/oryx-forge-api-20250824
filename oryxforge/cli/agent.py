"""Agent CLI commands for AI-powered data analysis."""

import click
from pathlib import Path
from .utils import handle_errors
from ..services.cli_service import CLIService


@click.group()
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
        - Profile must be configured: oryxforge admin config profile set --userid <id> --projectid <id>
        - Dataset and sheet should be activated (optional but recommended)
        - Mode can be set: oryxforge admin config mode set explore
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
    agent()

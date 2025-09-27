# OryxForge Admin CLI Guide

This guide covers the administrative commands for managing users, projects, datasets, and datasheets in OryxForge.

## Installation

Install OryxForge with admin CLI support:

```bash
pip install oryxforge
```

## Setup

Before using the admin CLI, you need to configure your environment:

```bash
# Set Supabase credentials
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_ANON_KEY="your-anon-key-here"
```

## User Configuration

### Set User ID

Configure your user ID for CLI operations:

```bash
oryxforge admin userid set "550e8400-e29b-41d4-a716-446655440000"
```

The user ID must exist in your Supabase `auth.users` table. This configuration is stored globally in `~/.oryxforge/cfg.ini`.

### Get User ID

View the currently configured user ID:

```bash
oryxforge admin userid get
```

Output examples:
```
Current user ID: 550e8400-e29b-41d4-a716-446655440000
```

If no user ID is configured:
```
No user ID configured. Run 'oryxforge admin userid set <userid>' to set one.
```

## Project Management

### List Projects

List all projects for the current user:

```bash
oryxforge admin projects list
```

Output example:
```
Projects for user:
==================================================
ID: abc123...  Name: My Data Project
ID: def456...  Name: Customer Analysis
```

### Create Project

Create a new project:

```bash
oryxforge admin projects create "My New Project"
```

This creates the same database entries as the frontend web interface.

### Pull and Activate Project

Pull a project and set it up locally:

```bash
# Interactive mode - shows project selection
oryxforge admin pull

# Specify project ID directly
oryxforge admin pull --id abc123

# Specify target directory
oryxforge admin pull --id abc123 --cwd /path/to/project
```

The pull command:
- Validates the project exists and is accessible
- Initializes the project if needed (creates git repo, updates database)
- Pulls the git repository to the specified directory
- Activates the project locally
- Auto-activates the default "scratchpad" dataset and first datasheet

## Dataset Management

### Activate Dataset

Activate a dataset for the current project:

```bash
# By dataset ID
oryxforge admin dataset activate --id def456

# By dataset name
oryxforge admin dataset activate --name scratchpad

# Interactive mode - shows dataset selection
oryxforge admin dataset activate
```

If neither `--id` nor `--name` is provided, an interactive selection menu is shown.

## Datasheet Management

### Activate Datasheet

Activate a datasheet (also called "sheet"):

```bash
# By datasheet ID
oryxforge admin sheet activate --id ghi789

# By datasheet name
oryxforge admin sheet activate --name data

# Interactive mode - shows datasheet selection
oryxforge admin sheet activate
```

Interactive mode shows datasheets from the currently active dataset, or all datasheets in the project if no dataset is active.

## Status and Configuration

### Show Status

Display current configuration status:

```bash
oryxforge admin status
```

Output example:
```
User ID: 550e8400-e29b-41d4-a716-446655440000
Active Project: abc123...
Active Dataset: def456...
Active Datasheet: ghi789...
Working Directory: /home/user/my-project
```

### Show Configuration Files

View configuration file contents:

```bash
# Show both global and project config
oryxforge admin config

# Show only global config
oryxforge admin config --global

# Show only project config
oryxforge admin config --project
```

## Configuration Files

### Global Configuration

Location: `~/.oryxforge/cfg.ini`

```ini
[user]
userid = 550e8400-e29b-41d4-a716-446655440000
```

### Project Configuration

Location: `<project_directory>/.oryxforge`

```ini
[active]
project_id = abc123...
dataset_id = def456...
sheet_id = ghi789...

[project]
name = My Data Project
initialized = true
```

## Workflow Examples

### Complete Setup Workflow

```bash
# 1. Set user ID
oryxforge admin userid set "your-user-id"

# 2. Create project
oryxforge admin projects create "Data Analysis Project"

# 3. Set up project directory
mkdir my-project && cd my-project

# 4. Pull and activate project (interactive)
oryxforge admin pull

# 5. Verify setup
oryxforge admin status
```

### Switch Between Projects

```bash
# List available projects
oryxforge admin projects list

# Switch to different project directory
cd /path/to/other/project

# Pull different project
oryxforge admin pull --id other-project-id

# Verify switch
oryxforge admin status
```

### Work with Datasets and Sheets

```bash
# See current active items
oryxforge admin status

# Switch to different dataset
oryxforge admin dataset activate --name view

# Switch to different datasheet
oryxforge admin sheet activate --name results

# Verify changes
oryxforge admin status
```

## Error Handling

The CLI provides clear error messages for common issues:

```bash
# No user ID configured
$ oryxforge admin projects list
❌ Error: No user ID configured. Run 'oryxforge admin userid set <userid>' first.

# Project not found
$ oryxforge admin pull --id invalid
❌ Error: Project 'invalid' not found or access denied.

# Dataset not found
$ oryxforge admin dataset activate --name nonexistent
❌ Error: Dataset 'nonexistent' not found in current project.
Available datasets: scratchpad, view
```

## Interactive Mode

When IDs or names are not provided, commands enter interactive mode:

```bash
$ oryxforge admin dataset activate

Available datasets:
==================================================
 1. scratchpad (ID: def456...)
 2. view (ID: ghi789...)

Select dataset (1-2): 1
✅ Activated dataset: def456...
```

## Integration with Other Tools

The admin CLI works alongside other OryxForge tools:

- **MCP Server**: Use `oryxforge mcp serve` for task management
- **API**: Project configuration is compatible with the REST API
- **Web Interface**: Projects created via CLI appear in the web interface

## Best Practices

1. **Set up environment variables**: Always configure Supabase credentials before using CLI commands
2. **Use project directories**: Keep each project in its own directory for clear organization
3. **Check status regularly**: Use `oryxforge admin status` to verify your current configuration
4. **Use interactive modes**: Let the CLI guide you with interactive selection when unsure
5. **Version control**: The `.oryxforge` config file can be committed to track project state

## Troubleshooting

### Command not found
```bash
pip install oryxforge
# or
pip install --upgrade oryxforge
```

### Authentication errors
- Verify `SUPABASE_URL` and `SUPABASE_ANON_KEY` environment variables
- Ensure your user ID exists in the Supabase auth.users table

### Permission errors
- Check that your user ID has access to the projects/datasets you're trying to access
- Verify Supabase Row Level Security (RLS) policies

### Git errors during project init
- Ensure git is installed and available in PATH
- Check that you have write permissions in the target directory

For additional help, run any command with `--help`:

```bash
oryxforge admin --help
oryxforge admin projects --help
oryxforge admin pull --help
```
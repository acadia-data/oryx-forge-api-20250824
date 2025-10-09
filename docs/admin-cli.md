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

## Profile Configuration

### Set Profile

Configure your user profile (user_id and project_id) for CLI operations:

```bash
oryxforge admin profile set --userid "550e8400-e29b-41d4-a716-446655440000" --projectid "abc123-project-id"
```

Both the user ID and project ID must exist in your Supabase database.

### Get Profile

View the currently configured profile:

```bash
oryxforge admin profile get
```

Output example:
```
Current profile:
  User ID: 550e8400-e29b-41d4-a716-446655440000
  Project ID: abc123-project-id
```

If no profile is configured:
```
No profile configured.
No profile configured. Set profile with:
  oryxforge admin profile set --userid <userid> --projectid <projectid>
Or use CredentialsManager.set_profile(user_id, project_id)
```

### Clear Profile

Clear the current profile configuration:

```bash
oryxforge admin profile clear
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

Stores profile (user_id and project_id) and active configuration (dataset_id and sheet_id) in the project directory.

## Workflow Examples

### Complete Setup Workflow

```bash
# 1. Set up project directory
mkdir my-project && cd my-project

# 2. Set profile (user_id and project_id)
oryxforge admin profile set --userid "your-user-id" --projectid "your-project-id"

# 3. Verify profile
oryxforge admin profile get

# 4. Check status
oryxforge admin status
```

### Create New Project Workflow

```bash
# 1. First, create user profile in global config (one-time setup)
oryxforge admin profile set --userid "your-user-id" --projectid "temp-project-id"

# 2. Create a new project
oryxforge admin projects create "Data Analysis Project"
# Note the project ID returned

# 3. Set up project directory
mkdir my-project && cd my-project

# 4. Set profile with the new project ID
oryxforge admin profile set --userid "your-user-id" --projectid "new-project-id"

# 5. Verify setup
oryxforge admin status
```

### Switch Between Projects

```bash
# Switch to different project directory
cd /path/to/other/project

# Update profile with different project ID
oryxforge admin profile set --userid "your-user-id" --projectid "other-project-id"

# Verify switch
oryxforge admin profile get
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
5. **Version control**: The project config file can be committed to track project state

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
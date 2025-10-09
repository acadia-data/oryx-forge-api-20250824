# OryxForge Admin CLI Guide

This guide covers the administrative commands for managing users, projects, datasets, and datasheets in OryxForge.

## Installation

Install OryxForge with admin CLI support:

```bash
pip install oryxforge
```

## Setup

Before using the admin CLI, you need to configure your environment:

## Profile Configuration

### Set Profile

Configure your user profile (user_id and project_id) for CLI operations. This needs to happen in the directory that you want to work in, as it is project specific.

```bash
oryxforge admin profile set --userid "550e8400-e29b-41d4-a716-446655440000" --projectid "abc123-project-id"
```

Both the user ID and project ID must exist in your Supabase database. You can get this from the oryx forge UI.

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

## File Import

### Import File to Sources Dataset

Import a data file into your project:

```bash
oryxforge admin projects import data.csv
```

The import command:
- Automatically processes and cleans the file using AI
- Creates a new datasheet in the "Sources" dataset
- Supports CSV, Excel (.xlsx, .xls), and Parquet files

**Prerequisites:**
- Profile must be configured with `--userid` and `--projectid`

**Example workflow:**
```bash
# 1. Set profile (one-time setup)
oryxforge admin profile set --userid "your-user-id" --projectid "your-project-id"

# 2. Import a CSV file
oryxforge admin projects import sales_data.csv

# 3. Import an Excel file
oryxforge admin projects import customer_data.xlsx

# 4. Import a Parquet file
oryxforge admin projects import events.parquet
```

**Supported File Types:**
- **CSV** (`.csv`): Comma-separated values
- **Excel** (`.xlsx`, `.xls`): Microsoft Excel files (imports first sheet only)
- **Parquet** (`.parquet`): Apache Parquet columnar format

The import automatically handles:
- Data type detection
- Column name cleaning
- Missing value handling
- For Excel files: Removes empty rows/columns, detects headers and footers

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

### Import and Analyze Data

```bash
# 1. Set up profile (one-time setup)
oryxforge admin profile set --userid "your-user-id" --projectid "your-project-id"

# 2. Import a data file
oryxforge admin projects import customer_data.csv

# 3. Check import status
oryxforge admin status

# 4. The file is now available as a datasheet in the "Sources" dataset
# You can activate it and work with it
oryxforge admin dataset activate --name Sources
oryxforge admin sheet activate --name customer_data.csv
```

## Troubleshooting

### Command not found
```bash
pip install oryxforge
# or
pip install --upgrade oryxforge
```

### Permission errors
- Check that your user ID has access to the projects/datasets you're trying to access

### Git errors during project init
- Ensure git is installed and available in PATH
- Check that you have write permissions in the target directory

For additional help, run any command with `--help`:

```bash
oryxforge admin --help
oryxforge admin projects --help
oryxforge admin pull --help
```
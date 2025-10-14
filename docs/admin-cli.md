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

## Project Mode Management

### Set Project Mode

Configure the project mode to control how the AI agent interprets your requests and responds to your commands:

```bash
# Set to explore mode
oryxforge admin mode set explore

# Set to edit mode
oryxforge admin mode set edit

# Set to plan mode
oryxforge admin mode set plan
```

**Available Modes:**

#### Explore Mode (Default)
**When to use:** Initial data discovery, trying different visualizations, answering new questions

In explore mode, the AI assumes you want to **create new outputs** for most requests:
- "Show me sales by region" → Creates a new visualization
- "What is the average order value?" → Creates a new analysis
- "Make a bar chart" → Creates a new chart
- When in doubt, the AI defaults to creating something **new**

**Intent interpretation:**
- Almost all requests are treated as **"new"** explorations
- Only explicit edit commands (with clear references like "change this chart's color") are treated as edits
- Best for: Brainstorming, exploring different views, asking multiple questions

#### Edit Mode
**When to use:** Refining existing work, making adjustments to visualizations, iterating on analysis

In edit mode, the AI is more careful about when to create new outputs vs. modify existing ones:
- "Show Q2 also" → **Edits** existing chart by adding Q2 data (uses "also" keyword)
- "Change the bars to blue" → **Edits** existing chart properties
- "Sort by profit instead" → **Edits** existing table (parameter change)
- "Make it a line chart instead" → Creates **new** chart (output type changed)
- "Show me revenue trends" → Creates **new** analysis (trigger words)

**Intent interpretation:**
- Request changes **output type** (table→chart, bar→line) → **New** exploration
- Request contains **"show me", "create", "what is"** → **New** exploration
- Request uses **"also", "too", "as well"** → **Edit** existing work
- Request references existing work with **"change", "update", "add to this"** → **Edit**
- Task type changes (import→analysis, one topic→different topic) → **New** exploration

**Best for:** Refining visualizations, adding elements, adjusting filters/colors/properties

#### Plan Mode
**When to use:** Designing multi-step workflows, planning data pipelines, strategic analysis

In plan mode, the AI focuses on helping you structure and organize complex tasks:
- Breaking down complex analyses into steps
- Planning data transformation workflows
- Designing multi-stage explorations
- Creating reusable analysis patterns

**Best for:** Strategic planning, workflow design, complex multi-step analyses

---

### Understanding Intent Classification

The mode affects how ambiguous requests are interpreted. Here are key examples:

**Scenario: You have a bar chart showing Q1 sales**

| Your Request | Explore Mode | Edit Mode |
|--------------|--------------|-----------|
| "show Q2 also" | New chart (safer default) | Edit existing chart (adds Q2 data) |
| "make it a line chart" | New line chart | New line chart (type changed) |
| "change bars to blue" | Edit colors | Edit colors |
| "show me profit trends" | New analysis | New analysis (trigger words) |
| "sort by revenue instead" | New output (safer default) | Edit sorting (parameter change) |

**Key Trigger Words:**
- **"also", "too", "as well"** → Strong signal to **edit** (adding to existing)
- **"show me", "what is", "create"** → Strong signal for **new** output
- **"instead"** with type change → **New** (e.g., "line chart instead of bar")
- **"instead"** with parameter → **Edit** in edit mode (e.g., "Q2 instead of Q1")

### When Output Type Changes → Always New

**These always create new explorations, regardless of mode:**
- Table → Any chart type
- Chart → Table
- Bar chart → Line chart
- Any fundamental output format change

**Example:** "Convert this to a pie chart" always creates a **new** pie chart, even in edit mode.

### Get Project Mode

View the currently configured project mode:

```bash
oryxforge admin mode get
```

Output example:
```
Current project mode: explore
```

If no mode is set:
```
No project mode set.
Available modes: edit, explore, plan
Set a mode with: oryxforge admin mode set <mode>
```

## Dataset Management

### Activate Dataset

Activate a dataset for the current project:

```bash
# By dataset ID
oryxforge admin datasets activate --id def456

# By dataset name
oryxforge admin datasets activate --name Exploration

# Interactive mode - shows dataset selection
oryxforge admin datasets activate
```

If neither `--id` nor `--name` is provided, an interactive selection menu is shown.

## Datasheet Management

### Activate Datasheet

Activate a datasheet (also called "sheet"):

```bash
# By datasheet ID
oryxforge admin sheets activate --id ghi789

# By datasheet name
oryxforge admin sheets activate --name data

# Interactive mode - shows datasheet selection
oryxforge admin sheets activate
```

Interactive mode shows datasheets from the currently active dataset, or all datasheets in the project if no dataset is active.

## File Import

### List All Datasets and Datasheets

View all datasets and datasheets in the current project as a table:

```bash
oryxforge admin data list
```

Output example:
```
Datasets and Datasheets:
================================================================================
| name_dataset | name_sheet       | name_python           |
|:-------------|:-----------------|:----------------------|
| Sources      | HPI Master CSV   | sources.HpiMasterCsv  |
| Sources      | Customer Data    | sources.CustomerData  |
| Exploration  | Analysis Results | exploration.Analysis  |
| Exploration  | Summary Stats    | exploration.Summary   |
================================================================================
Total: 4 datasheet(s)
```

The `name_python` column shows the combined Python notation (dataset.sheet) that can be used
to reference sheets in code and AI agent requests.

**Prerequisites:**
- Profile must be configured with `--userid` and `--projectid`

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

## Configuration Management

### Set Mount Point

Configure a custom mount point for your project's data directory:

```bash
# Windows
oryxforge admin config mount-set "D:\data"

# Linux/macOS
oryxforge admin config mount-set "/mnt/data"
```

The mount point configuration:
- Saves the mount point path in project configuration (`.oryxforge.cfg`)
- Automatically used by all services that need to access the data directory
- Stored in cross-platform POSIX format for compatibility
- Must be an absolute path

**Path Requirements:**
- **Windows:** Must be absolute with drive letter (e.g., `D:\data`) or UNC path (e.g., `\\server\share`)
- **Linux/macOS:** Must be an absolute path (e.g., `/mnt/data`)

**Example:**
```bash
# Set custom mount point
oryxforge admin config mount-set "D:\oryx-data"

# Verify configuration
oryxforge admin config mount-get
```

### Get Mount Point

View the configured mount point:

```bash
oryxforge admin config mount-get
```

Output example:
```
Current mount point: D:/oryx-data
```

If no mount point is configured:
```
No mount point configured. Using default: ./data
Set a mount point with: oryxforge admin config mount-set <path>
```

### Suggest Mount Point with Project Hierarchy

Automatically generate a mount point path with organized user/project hierarchy:

```bash
# Windows
oryxforge admin config mount-suggest "D:\data\oryx-forge"

# Linux/macOS
oryxforge admin config mount-suggest "/mnt/oryx-forge"
```

**What it does:**
- Takes your base path (e.g., `D:\data\oryx-forge`)
- Automatically appends `/{user_id}/{project_id}/data`
- Creates parent directories automatically when setting the mount point
- Creates an organized hierarchy for multiple projects
- Outputs in cross-platform POSIX format
- Optionally mounts the data directory immediately

**Example workflow:**
```bash
$ oryxforge admin config mount-suggest "D:\data\oryx-forge"
Suggested mount point: D:/data/oryx-forge/{user-id}/{project-id}/data

Do you want to set this as your mount point? [Y/n]: y
Created directory: D:\data\oryx-forge\{user-id}\{project-id}
✅ Mount point set to: D:/data/oryx-forge/{user-id}/{project-id}/data

Do you want to mount the data directory now? [Y/n]: y
✅ Successfully mounted data directory at D:/data/oryx-forge/{user-id}/{project-id}/data
```

**Directory structure created:**
```
D:\data\oryx-forge\
└── {user-id}\
    ├── {project-id-1}\
    │   └── data\              (mount point for project 1)
    └── {project-id-2}\
        └── data\              (mount point for project 2)
```

**Benefits:**
- **Organized**: Automatic hierarchy prevents path conflicts
- **Multi-project**: Easy to manage multiple projects on same machine
- **No manual IDs**: Don't need to type or remember user/project IDs
- **Cross-platform**: Works on Windows, Linux, and macOS

**Prerequisites:**
- Profile must be configured with `oryxforge admin profile set --userid <id> --projectid <id>`

## Data Mount Management

### Mount Project Data Directory

Mount the project's GCS bucket to the configured mount point using rclone:

```bash
oryxforge admin mount
```

The mount command:
- Mounts to the configured mount point (or `./data` if not configured)
- Makes your project's cloud storage accessible as a local filesystem
- Runs in the background for seamless access
- Provides fast read/write performance with intelligent caching

**Prerequisites:**
- Profile must be configured with `--userid` and `--projectid`
- [rclone](https://rclone.org/downloads/) must be installed and configured with your cloud storage
- (Optional) Mount point configured with `oryxforge admin config mount-set <path>`

**Platform Support:**
- Windows, Linux, and macOS

**Example workflow:**
```bash
# 1. Set profile (one-time setup)
oryxforge admin profile set --userid "your-user-id" --projectid "your-project-id"

# 2. (Optional) Configure custom mount point
oryxforge admin config mount-set "D:\oryx-data"

# 3. Mount the data directory
oryxforge admin mount

# 4. Access your data files
ls D:\oryx-data
cat D:\oryx-data\myfile.csv

# 5. Write files to the mount
cp local-file.csv D:\oryx-data\
```

### Unmount Project Data Directory

Unmount the rclone-mounted data directory:

```bash
oryxforge admin unmount
```

The unmount command:
- Safely unmounts the data directory
- Ensures all cached writes are flushed to cloud storage

**Prerequisites:**
- Profile must be configured
- Data directory must be currently mounted

**Example:**
```bash
# Unmount when done working
oryxforge admin unmount
```

### Troubleshooting Mount Issues

**"rclone command not found"**
- Install rclone from https://rclone.org/downloads/
- Ensure rclone is in your system PATH

**"Mount failed" or "Access denied"**
- Verify rclone is configured with your cloud storage credentials
- Check that your user has access to the project's cloud storage

**Mount appears successful but directory is empty**
- Check cloud storage permissions
- Verify your profile is configured correctly with `oryxforge admin profile get`

**Windows-specific issues**
- Install WinFsp from https://winfsp.dev/ (required for mounting on Windows)

**Linux-specific issues**
- Install FUSE: `sudo apt-get install fuse` (Ubuntu/Debian) or `sudo yum install fuse` (CentOS/RHEL)

**macOS-specific issues**
- Install macFUSE from https://osxfuse.github.io/ (required for mounting on macOS)

## Status and Configuration

### Show Status

Display current configuration status:

```bash
oryxforge admin status
```

Output example:
```
User ID: 550e8400-e29b-41d4-a716-446655440000
Project ID: abc123...
Active Dataset: def456...
Active Datasheet: ghi789...
Project Mode: explore
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

# Set project mode
oryxforge admin mode set explore

# Switch to different dataset
oryxforge admin datasets activate --name view

# Switch to different datasheet
oryxforge admin sheets activate --name results

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
oryxforge admin datasets activate --name Sources
oryxforge admin sheets activate --name customer_data.csv
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
oryxforge admin mode --help
oryxforge admin mode set --help
oryxforge admin mode get --help
```

## Command Reference

### Profile Commands
- `oryxforge admin profile set --userid <id> --projectid <id>` - Set user profile
- `oryxforge admin profile get` - View current profile
- `oryxforge admin profile clear` - Clear profile configuration

### Configuration Commands
- `oryxforge admin config mount-set <path>` - Set mount point for data directory
- `oryxforge admin config mount-get` - Get configured mount point
- `oryxforge admin config mount-suggest <base_path>` - Suggest mount point with user/project hierarchy

### Project Commands
- `oryxforge admin projects list` - List all projects
- `oryxforge admin projects create <name>` - Create new project
- `oryxforge admin projects import <filepath>` - Import data file
- `oryxforge admin pull [--id <id>] [--cwd <path>]` - Pull and activate project

### Mount Commands
- `oryxforge admin mount` - Mount project data directory
- `oryxforge admin unmount` - Unmount project data directory

### Mode Commands
- `oryxforge admin mode set <mode>` - Set project mode (explore/edit/plan)
- `oryxforge admin mode get` - Get current project mode

### Dataset Commands
- `oryxforge admin datasets list` - List all datasets
- `oryxforge admin datasets activate [--id <id>] [--name <name>]` - Activate dataset

### Datasheet Commands
- `oryxforge admin sheets list [--dataset-id <id>]` - List datasheets
- `oryxforge admin sheets activate [--id <id>] [--name <name>]` - Activate datasheet

### Data Commands
- `oryxforge admin data list` - List all datasets and datasheets as a table

### Utility Commands
- `oryxforge admin status` - Show current configuration status
- `oryxforge admin show-config` - Show configuration file contents
```
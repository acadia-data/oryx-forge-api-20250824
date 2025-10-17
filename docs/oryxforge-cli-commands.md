# OryxForge CLI Guide

This guide covers the commands for managing users, projects, datasets, datasheets, and AI-powered data analysis in OryxForge.

## Installation

Install OryxForge with CLI support:

```bash
pip install oryxforge
```

## Command Structure

The OryxForge CLI is organized into logical command groups:

```
oryxforge/
├── agent/
│   └── chat                      # AI-powered data analysis
│
└── admin/
    ├── pull                      # Pull/clone project repository
    ├── mount                     # Mount data directory
    ├── unmount                   # Unmount data directory
    ├── status                    # Show current status
    │
    ├── config/                   # Configuration settings
    │   ├── show                  # Show config file
    │   ├── profile {set,get,clear}
    │   ├── mode {set,get}
    │   └── mount {set,get,suggest}
    │
    ├── projects/
    │   ├── list
    │   ├── create
    │   └── init                  # Create + pull in one step
    │
    ├── sources/                  # Data source imports
    │   ├── import
    │   └── list
    │
    ├── datasets/
    │   ├── list
    │   └── activate
    │
    ├── sheets/
    │   ├── list
    │   └── activate
    │
    └── data/
        └── list                  # Combined datasets + sheets view
```

## Quick Start

### Option 1: Initialize New Project (Recommended)

```bash
# Create new project and set it up locally in one step
oryxforge admin projects init "My Project" --userid "your-user-id"

# This creates the project, clones the repository, and sets up configuration
# You'll get a new folder: ./my-project/

cd my-project
oryxforge admin data list
oryxforge admin config mode set explore
oryxforge admin sources import data.csv
oryxforge agent chat "show me summary statistics"
```

### Option 2: Pull Existing Project



```bash
# create a top level folder and initialize credentials there
mkdir oryx-forge-projects
cd oryx-forge-projects
oryxforge admin config profile set --userid "your-user-id" --projectid "ignore"

# list projects
oryxforge admin projects list

# Pull an existing project by ID
oryxforge admin pull --projectid "project-id" --userid "your-user-id"

cd project-folder
oryxforge admin sources import data/data.csv
oryxforge agent chat "show me summary statistics for data.csv"
```

## Configuration Management

All configuration commands are under `oryxforge admin config`.

### Profile Configuration

Profile settings store your user ID and project ID for CLI operations.

#### Set Profile

```bash
oryxforge admin config profile set --userid "your-user-id" --projectid "your-project-id"
```

Both the user ID and project ID must exist in your Supabase database. You can get these from the OryxForge web UI, userid is in the user profile and project id is in the project settings.

#### Get Profile

View the currently configured profile:

```bash
oryxforge admin config profile get
```

Output example:
```
Current profile:
  User ID: your-user-id
  Project ID: your-project-id
```

#### Clear Profile

Clear the current profile configuration:

```bash
oryxforge admin config profile clear
```

### Project Mode Management

Project mode controls how the AI agent interprets your requests.

#### Set Project Mode

```bash
# Set to explore mode
oryxforge admin config mode set explore

# Set to edit mode
oryxforge admin config mode set edit

# Set to plan mode
oryxforge admin config mode set plan
```

**Available Modes:**

##### Explore Mode (Default)
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

##### Edit Mode
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

##### Plan Mode
**When to use:** Designing multi-step workflows, planning data pipelines, strategic analysis

In plan mode, the AI focuses on helping you structure and organize complex tasks:
- Breaking down complex analyses into steps
- Planning data transformation workflows
- Designing multi-stage explorations
- Creating reusable analysis patterns

**Best for:** Strategic planning, workflow design, complex multi-step analyses

#### Get Project Mode

View the currently configured project mode:

```bash
oryxforge admin config mode get
```

Output example:
```
Current project mode: explore
```

### Mount Point Configuration

Configure where project data is mounted locally.

#### Set Mount Point

```bash
# Windows
oryxforge admin config mount set "D:\\data"

# Linux/macOS
oryxforge admin config mount set "/mnt/data"
```

The mount point configuration:
- Saves the mount point path in project configuration (`.oryxforge.cfg`)
- Automatically used by all services that need to access the data directory
- Stored in cross-platform POSIX format for compatibility
- Must be an absolute path

#### Get Mount Point

```bash
oryxforge admin config mount get
```

Output example:
```
Current mount point: D:/oryx-data
```

#### Suggest Mount Point with Project Hierarchy

Automatically generate a mount point path with organized user/project hierarchy:

```bash
# Windows
oryxforge admin config mount suggest "D:\\data\\oryx-forge"

# Linux/macOS
oryxforge admin config mount suggest "/mnt/oryx-forge"
```

**What it does:**
- Takes your base path (e.g., `D:\\data\\oryx-forge`)
- Automatically appends `/{user_id}/{project_id}/data`
- Creates parent directories automatically when setting the mount point
- Creates an organized hierarchy for multiple projects
- Outputs in cross-platform POSIX format
- Optionally mounts the data directory immediately

**Example workflow:**
```bash
$ oryxforge admin config mount suggest "D:\\data\\oryx-forge"
Suggested mount point: D:/data/oryx-forge/{user-id}/{project-id}/data

Do you want to set this as your mount point? [Y/n]: y
Created directory: D:\\data\\oryx-forge\\{user-id}\\{project-id}
✅ Mount point set to: D:/data/oryx-forge/{user-id}/{project-id}/data

Do you want to mount the data directory now? [Y/n]: y
✅ Successfully mounted data directory at D:/data/oryx-forge/{user-id}/{project-id}/data
```

**Directory structure created:**
```
D:\\data\\oryx-forge\\
└── {user-id}\\
    ├── {project-id-1}\\
    │   └── data\\              (mount point for project 1)
    └── {project-id-2}\\
        └── data\\              (mount point for project 2)
```

#### Show Configuration

View the current configuration file content:

```bash
oryxforge admin config show
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

### Create New Project (Recommended: Use `init` instead)

Create a new project in the database and on GitLab:

```bash
oryxforge admin projects create "My New Project" --userid "your-user-id"
```

This creates:
- Database entry for the project
- GitLab repository for the project

**Next steps after `create`:**
```bash
# Pull the project to set it up locally
oryxforge admin pull --projectid "your-project-id" --userid "your-user-id"
```

### Initialize New Project (Create + Pull in One Step)

**Recommended:** Use `init` to create and set up a project in one command:

```bash
# Create project and set it up locally
oryxforge admin projects init "My New Project" --userid "your-user-id"

# With custom target directory
oryxforge admin projects init "My New Project" --userid "your-user-id" --target ./my-folder
```

The `init` command:
1. Creates project in database
2. Creates GitLab repository
3. Clones repository to local directory
4. Sets up `.oryxforge.cfg` configuration file inside the project directory

**Output:**
```bash
Creating project 'My New Project'...
✅ Created project with ID: abc-123

Initializing project locally...
✅ Project 'My New Project' is ready!
   Location: ./my-new-project

Next steps:
  cd ./my-new-project
  # Start working on your project!
```

### Pull Existing Project

Clone an existing project repository and set it up locally:

```bash
# Pull by project ID
oryxforge admin pull --projectid "project-id" --userid "your-user-id"

# Specify custom target directory
oryxforge admin pull --projectid "project-id" --userid "your-user-id" --target ./my-folder
```

The `pull` command:
- Clones the GitLab repository to a new folder (default: auto-generated from project name)
- Sets up `.oryxforge.cfg` configuration file inside the project directory
- Makes the project ready for local development

**Example:**
```bash
# Pull project
oryxforge admin pull --projectid "your-project-id" --userid "your-user-id"

# Output: ✅ Project pulled to: ./project-name
cd ./project-name
# Start working!
```

## Data Source Management

Manage imported data files in the "Sources" dataset.

### Import File

Import a data file into your project:

```bash
oryxforge admin sources import data.csv
```

The import command:
- Automatically processes and cleans the file using AI
- Creates a new datasheet in the "Sources" dataset
- Supports CSV, Excel (.xlsx, .xls), and Parquet files

**Supported File Types:**
- **CSV** (`.csv`): Comma-separated values
- **Excel** (`.xlsx`, `.xls`): Microsoft Excel files (imports first sheet only)
- **Parquet** (`.parquet`): Apache Parquet columnar format

The import automatically handles:
- Data type detection
- Column name cleaning
- Missing value handling
- For Excel files: Removes empty rows/columns, detects headers and footers

**Example workflow:**
```bash
# 1. Set profile (one-time setup)
oryxforge admin config profile set --userid "your-user-id" --projectid "your-project-id"

# 2. Import a CSV file
oryxforge admin sources import sales_data.csv

# 3. Import an Excel file
oryxforge admin sources import customer_data.xlsx

# 4. Import a Parquet file
oryxforge admin sources import events.parquet
```

### List Data Sources

View all imported data sources for the current project:

```bash
oryxforge admin sources list
```

Output example:
```
Data Sources:
================================================================================
Name: sales_data.csv
  Type: auto
  Rows: 1500
  Imported: 2025-01-15 10:30:45
--------------------------------------------------------------------------------
Name: customer_data.xlsx
  Type: auto
  Rows: 850
  Imported: 2025-01-14 15:20:10
--------------------------------------------------------------------------------
```

## Dataset Management

### List Datasets

List all datasets for the current project:

```bash
oryxforge admin datasets list
```

Output example:
```
Datasets:
================================================================================
ID: def456...
  Name: Sources
  Python Name: sources
--------------------------------------------------------------------------------
ID: ghi789...
  Name: Exploration
  Python Name: exploration
--------------------------------------------------------------------------------
```

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

### List Datasheets

List all datasheets for the current project:

```bash
# List all datasheets in the project
oryxforge admin sheets list

# List datasheets filtered by dataset
oryxforge admin sheets list --dataset-id def456
```

Output example:
```
All Datasheets:
================================================================================
ID: abc123...
  Name: data
  Python Name: data
  Dataset ID: def456...
--------------------------------------------------------------------------------
```

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

## Data Views

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
- (Optional) Mount point configured with `oryxforge admin config mount set <path>`

**Platform Support:**
- Windows, Linux, and macOS

**Example workflow:**
```bash
# 1. Set profile (one-time setup)
oryxforge admin config profile set --userid "your-user-id" --projectid "your-project-id"

# 2. (Optional) Configure custom mount point
oryxforge admin config mount set "D:\\oryx-data"

# 3. Mount the data directory
oryxforge admin mount

# 4. Access your data files
ls D:\\oryx-data
cat D:\\oryx-data\\myfile.csv

# 5. Write files to the mount
cp local-file.csv D:\\oryx-data\\
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

### Troubleshooting Mount Issues

**"rclone command not found"**
- Install rclone from https://rclone.org/downloads/
- Ensure rclone is in your system PATH

**"Mount failed" or "Access denied"**
- Verify rclone is configured with your cloud storage credentials
- Check that your user has access to the project's cloud storage

**Mount appears successful but directory is empty**
- Check cloud storage permissions
- Verify your profile is configured correctly with `oryxforge admin config profile get`

**Windows-specific issues**
- Install WinFsp from https://winfsp.dev/ (required for mounting on Windows)

**Linux-specific issues**
- Install FUSE: `sudo apt-get install fuse` (Ubuntu/Debian) or `sudo yum install fuse` (CentOS/RHEL)

**macOS-specific issues**
- Install macFUSE from https://osxfuse.github.io/ (required for mounting on macOS)

## Status and Utilities

### Show Status

Display current configuration status:

```bash
oryxforge admin status
```

Output example:
```
User ID: your-user-id
Project ID: your-project-id
Active Dataset: def456...
Active Datasheet: ghi789...
Project Mode: explore
Working Directory: /home/user/my-project
```

## AI Agent Commands

All AI agent commands are under `oryxforge agent`.

### Chat with the AI Agent

Chat with the AI agent for interactive data analysis:

```bash
oryxforge agent chat "show me summary statistics"
```

**MESSAGE**: Your question or request for the AI agent

The agent will analyze your request, determine the appropriate data operations,
and generate code to perform the analysis.

**Examples:**
```bash
# Analyze data in the active sheet
oryxforge agent chat "show me summary statistics"

# Create a new analysis
oryxforge agent chat "create a chart of sales by region"

# Edit existing analysis
oryxforge agent chat "add a trend line to the chart"
```

**Prerequisites:**
- Profile must be configured: `oryxforge admin config profile set --userid <id> --projectid <id>`
- Dataset and sheet should be activated (optional but recommended)
- Mode can be set: `oryxforge admin config mode set explore`

**Output example:**
```
================================================================================
AI Agent Response:
================================================================================
I've created a summary statistics table showing mean, median, std, min, and max
for all numeric columns in your dataset.
================================================================================

📊 Target: exploration.Summary
💰 Cost: $0.0042
⏱️  Duration: 1250ms
```

## Workflow Examples

### Complete Setup Workflow

```bash
# 1. Set up project directory
mkdir my-project && cd my-project

# 2. Set profile (user_id and project_id)
oryxforge admin config profile set --userid "your-user-id" --projectid "your-project-id"

# 3. Verify profile
oryxforge admin config profile get

# 4. Check status
oryxforge admin status
```

### Create New Project Workflow

```bash
# Recommended: Use init to create and set up in one step
oryxforge admin projects init "Data Analysis Project" --userid "your-user-id"

# You'll get a new folder with the project
cd data-analysis-project

# Verify setup
oryxforge admin status

# Alternative: Create then pull separately
oryxforge admin projects create "Data Analysis Project" --userid "your-user-id"
# Note the project ID returned
oryxforge admin pull --projectid "project-id" --userid "your-user-id"
cd data-analysis-project
```

### Switch Between Projects

```bash
# Switch to different project directory
cd /path/to/other/project

# Verify switch
oryxforge admin config profile get
oryxforge admin status
```

### Work with Datasets and Sheets

```bash
# See current active items
oryxforge admin status

# Set project mode
oryxforge admin config mode set explore

# Switch to different dataset
oryxforge admin datasets activate --name Exploration

# Switch to different datasheet
oryxforge admin sheets activate --name results

# Verify changes
oryxforge admin status
```

### Import and Analyze Data

```bash
# 1. Set up profile (one-time setup)
oryxforge admin config profile set --userid "your-user-id" --projectid "your-project-id"

# 2. Import a data file
oryxforge admin sources import customer_data.csv

# 3. Check import status
oryxforge admin status

# 4. The file is now available as a datasheet in the "Sources" dataset
# You can activate it and work with it
oryxforge admin datasets activate --name Sources
oryxforge admin sheets activate --name customer_data.csv

# 5. Chat with the AI agent
oryxforge agent chat "show me the distribution of customer ages"
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
oryxforge --help
oryxforge admin --help
oryxforge admin config --help
oryxforge admin config profile --help
oryxforge admin config mode --help
oryxforge agent --help
oryxforge agent chat --help
```

## Command Reference

### Configuration Commands
- `oryxforge admin config show` - Show configuration file content
- `oryxforge admin config profile set --userid <id> --projectid <id>` - Set user profile
- `oryxforge admin config profile get` - View current profile
- `oryxforge admin config profile clear` - Clear profile configuration
- `oryxforge admin config mode set <mode>` - Set project mode (explore/edit/plan)
- `oryxforge admin config mode get` - Get current project mode
- `oryxforge admin config mount set <path>` - Set mount point for data directory
- `oryxforge admin config mount get` - Get configured mount point
- `oryxforge admin config mount suggest <base_path>` - Suggest mount point with user/project hierarchy

### Project Commands
- `oryxforge admin projects list` - List all projects
- `oryxforge admin projects create <name> --userid <id>` - Create new project (DB + GitLab only)
- `oryxforge admin projects init <name> --userid <id> [--target <path>]` - Create and initialize project locally (recommended)
- `oryxforge admin pull --projectid <id> --userid <id> [--target <path>]` - Clone existing project repository

### Source Commands
- `oryxforge admin sources import <filepath>` - Import data file
- `oryxforge admin sources list` - List all data sources

### Mount Commands
- `oryxforge admin mount` - Mount project data directory
- `oryxforge admin unmount` - Unmount project data directory

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

### Agent Commands
- `oryxforge agent chat <message>` - Chat with the AI agent for interactive data analysis

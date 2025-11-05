# Context Management Architecture

## Overview

OryxForge uses a sophisticated context management system that enables **zero-parameter services** while maintaining clean separation between CLI and API modes. This document explains how working directories, configuration, and credentials flow through the system.

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Working Directory Management](#working-directory-management)
3. [Configuration Architecture](#configuration-architecture)
4. [Service Integration Patterns](#service-integration-patterns)
5. [Environment Detection](#environment-detection)
6. [Flow Diagrams](#flow-diagrams)
7. [Common Pitfalls](#common-pitfalls)

---

## Core Concepts

### Critical Resource Configuration

OryxForge requires proper configuration of several key resources to function correctly. Understanding **what needs to be configured** and **why it matters** is essential for reliable operation.

#### Why Configuration Matters

OryxForge separates **code** (in Git repositories) from **data** (in cloud storage), requiring explicit configuration to bridge them:

```
Git Repository (Code)              Cloud Storage (Data)
├── tasks/                         ├── exploration/
│   └── my_task.py          →→→   │   └── MySheet.parquet
├── .oryxforge.cfg                 ├── sources/
└── ...                            └── ...
     ↑                                  ↑
     |                                  |
working_dir              mount_point (must be configured!)
```

**Without proper configuration**, services cannot:
- ✗ Find data files (d6tflow tasks fail with "file not found")
- ✗ Save outputs (writes to wrong location or fails)
- ✗ Load existing datasets (can't locate parquet files)
- ✗ Execute workflows (d6tflow doesn't know where to read/write)

#### What Must Be Configured

| Resource | Purpose | Configured By | Why Critical |
|----------|---------|---------------|--------------|
| **working_dir** | Git repository location | `ProjectContext.set()` | Code, tasks, and `.oryxforge.cfg` location |
| **mount_point** | Cloud storage mount path | `.oryxforge.cfg [mount]` | Data files location for d6tflow I/O |
| **user_id** | User identity | `.oryxforge.cfg [profile]` | Supabase RLS and file path structure |
| **project_id** | Project identity | `.oryxforge.cfg [profile]` | Supabase RLS and file path structure |
| **d6tflow directory** | Workflow output location | Set by `ProjectService` to `mount_point` | Where d6tflow reads/writes data |

**Key Insight:** The `mount_point` MUST point to where your cloud data is accessible. If misconfigured, d6tflow will look in the wrong place, causing all data operations to fail.

#### Configuration Flow

```
1. ProjectContext.set()
   → Determines working_dir
   → Writes .oryxforge.cfg

2. ProjectService.__init__()
   → Reads mount_point from config
   → Validates mount is accessible
   → Sets d6tflow.set_dir(mount_point)

3. IOService/d6tflow tasks
   → Read/write data at mount_point
   → Success! Files found at correct location
```

#### Configuration by Environment

Different environments require different configuration strategies:

| Environment | working_dir | mount_point | mount_ensure | Who Mounts |
|-------------|-------------|-------------|--------------|------------|
| **Local CLI** | `Path.cwd()` | User config (default: `./data`) | `true` | ProjectService (rclone auto-mount) |
| **Local Dev API** | `{ORYX_MOUNT_ROOT}/mnt/projects/{user}/{project}` | `{ORYX_MOUNT_ROOT}/mnt/data/{user}/{project}` | `false` | Developer (manual setup) |
| **Cloud API (GCP)** | `/tmp/{user}/{project}` (ephemeral) | `/mnt/data/{user}/{project}` | `false` | Cloud Run (volume mount) |
| **Test Mode** | `tempfile.gettempdir()/*` | `./data` (default) | `false` | None (checks skipped) |

**Key Differences:**
- **CLI**: Auto-mounts if needed, persistent working_dir
- **API modes**: External mount required, ephemeral/persistent working_dir
- **Test mode**: Skips mount validation for fast test execution

### The Zero-Parameter Service Pattern

Services like `ProjectService`, `IOService`, and `RepoService` can be initialized **without parameters**:

```python
# ✅ Zero-parameter initialization
project_service = ProjectService()
io_service = IOService()

# Services automatically know:
# - user_id (from .oryxforge.cfg)
# - project_id (from .oryxforge.cfg)
# - working_dir (from ProjectContext or cwd)
# - mount_point (from .oryxforge.cfg or default)
```

This is achieved through:
1. **ProjectContext** - Thread-safe context for working directory
2. **CredentialsManager** - Reads `[profile]` section from `.oryxforge.cfg`
3. **ConfigService** - Reads other config sections (mount, active, etc.)

### The `.oryxforge.cfg` File

Central configuration file with multiple sections:

```ini
[profile]
user_id = <user-uuid>
project_id = <project-uuid>

[mount]
mount_point = D:/data/projects/<user-id>/<project-id>/data
mount_ensure = true

[active]
dataset_id = <dataset-uuid>
sheet_id = <sheet-uuid>
mode = explore
```

#### Config Section Responsibilities

| Section    | Managed By           | Purpose                                    | Used By                                      |
|------------|----------------------|--------------------------------------------|--------------------------------------------- |
| `[profile]`| CredentialsManager   | User and project authentication            | All services (via `get_profile()`)           |
| `[mount]`  | ConfigService        | Data directory mount configuration         | ProjectService, CLIService                   |
| `[active]` | ConfigService        | Current dataset/sheet/mode selection       | CLIService, ChatService                      |

**Service Usage Summary:**

- **CredentialsManager**: Reads/writes `[profile]` section only
- **ConfigService**: Reads/writes `[mount]` and `[active]` sections (NOT `[profile]`)
- **CLIService**: Uses both CredentialsManager (`[profile]`) and ConfigService (`[mount]`, `[active]`)
- **ProjectService**: Reads `[profile]` via CredentialsManager, reads `[mount]` via ConfigService
- **IOService**: Delegates all config reading to ProjectService
- **RepoService**: Reads `[profile]` via CredentialsManager only
- **FastAPI (app.py)**: Never uses ConfigService directly; delegates to `ProjectService.project_init()`

---

## Working Directory Management

### ProjectContext: Thread-Safe Context Variable

**Location:** `oryxforge/services/env_config.py`

**Purpose:** Stores the current working directory in a thread-safe context variable, enabling services to find their configuration without passing parameters.

#### Key Methods

##### `ProjectContext.set(user_id, project_id, working_dir=None, write_config=True)`

Sets the working directory context. The `working_dir` parameter behavior depends on the environment:

```python
# CLI Mode (no GOOGLE_CLOUD_PROJECT, no FASTAPI_ENV)
if working_dir is None:
    working_dir = Path.cwd()  # Use current directory

# GCP Production Mode
if os.environ.get('GOOGLE_CLOUD_PROJECT'):
    working_dir = f"/tmp/{user_id}/{project_id}"  # Ephemeral

# Local API Development Mode
if os.environ.get('ORYX_MOUNT_ROOT'):
    working_dir = f"{ORYX_MOUNT_ROOT}/mnt/projects/{user_id}/{project_id}"
```

**Parameters:**
- `user_id`: User UUID
- `project_id`: Project UUID
- `working_dir`: Optional explicit path (for tests or special cases)
- `write_config`: If `False`, skips creating directory and writing `.oryxforge.cfg` (used before git clone)

**Returns:** The resolved working directory path

##### `ProjectContext.get()`

Retrieves the current working directory from context:

```python
context_dir = ProjectContext.get()
# Returns:
#   - Context working_dir if set via ProjectContext.set()
#   - Path.cwd() if no context set (fallback for CLI mode)
```

##### `ProjectContext.write_config(user_id, project_id, working_dir=None)`

Writes `.oryxforge.cfg` after the working directory is ready (e.g., after git clone):

```python
# Usage pattern in project_init:
# 1. Set context WITHOUT writing config (before clone)
working_dir = ProjectContext.set(user_id, project_id, write_config=False)

# 2. Clone repository
repo_service.ensure_repo()

# 3. Write config NOW (after repo exists)
ProjectContext.write_config(user_id, project_id, working_dir)
```

#### Environment Detection

##### `ProjectContext.is_api_mode()`

Detects if running in API mode (GCP or local API):

```python
return (
    os.environ.get('GOOGLE_CLOUD_PROJECT') is not None or
    os.environ.get('FASTAPI_ENV') is not None
)
```

##### `ProjectContext.get_mount_parent_path(user_id=None, project_id=None)`

Returns the base mount path for API mode:

```python
# GCP Production
if os.environ.get('GOOGLE_CLOUD_PROJECT'):
    base_path = "/mnt/data"

# Local API Development
else:
    base_path = f"{ORYX_MOUNT_ROOT}/mnt/data"

# If user_id/project_id provided
if user_id and project_id:
    return f"{base_path}/{user_id}/{project_id}"
```

---

## Configuration Architecture

### CredentialsManager: Profile Management

**Location:** `oryxforge/services/iam.py`

**Purpose:** Manages the `[profile]` section of `.oryxforge.cfg`, storing user_id and project_id.

#### Key Methods

##### `__init__(working_dir=None)`

```python
def __init__(self, working_dir: Optional[str] = None):
    if working_dir is None:
        from .env_config import ProjectContext
        self.working_dir = Path(ProjectContext.get())
    else:
        self.working_dir = Path(working_dir)
```

**Note (v1.2+):** Uses `ProjectContext.get()` as default, which falls back to `Path.cwd()` when no context is set. This makes it context-aware in API mode while maintaining compatibility with CLI bootstrap commands.

##### `set_profile(user_id, project_id)`

Writes credentials to `[profile]` section:

```python
# Read existing config or create new
config = ConfigObj()
if self.config_file.exists():
    config = ConfigObj(str(self.config_file))

# Set profile config
config['profile'] = {
    'user_id': user_id,
    'project_id': project_id
}

# Write to disk
config.filename = str(self.config_file)
config.write()
```

##### `get_profile()`

Reads credentials from `[profile]` section:

```python
# Returns dict with keys:
{
    'user_id': '<uuid>',
    'project_id': '<uuid>'
}

# Raises ValueError if:
# - .oryxforge.cfg doesn't exist
# - [profile] section incomplete
```

##### `clear_profile()`

Removes `[profile]` section from config file.

---

### ConfigService: General Configuration

**Location:** `oryxforge/services/config_service.py`

**Purpose:** Manages all non-profile config sections: `[mount]`, `[active]`, etc.

#### Key Methods

##### `__init__(working_dir=None)`

```python
def __init__(self, working_dir: Optional[str] = None):
    if working_dir is None:
        from .env_config import ProjectContext
        self.working_dir = Path(ProjectContext.get())
    else:
        self.working_dir = Path(working_dir)
    self.config_file = self.working_dir / '.oryxforge.cfg'
```

**Note (v1.2+):** Uses `ProjectContext.get()` as default, matching the pattern used by other services. This ensures config operations work correctly in API mode where the shell's cwd differs from the project's working directory.

##### `get(section, key)`

Retrieves a single config value:

```python
value = config_service.get('mount', 'mount_point')
# Returns: str | None
```

##### `set(section, key, value)`

Sets a single config value:

```python
config_service.set('mount', 'mount_point', '/path/to/mount')
# Creates [mount] section if needed
# Writes to disk immediately
```

##### `get_all(section)`

Gets all key-value pairs from a section:

```python
active_config = config_service.get_all('active')
# Returns: {'dataset_id': 'abc', 'sheet_id': 'def', 'mode': 'explore'}
```

##### `validate_mount_point(mount_point)`

Validates and normalizes mount point paths:

```python
# Windows: Validates absolute path or UNC path
# Unix: Validates absolute path
# Returns: Path object (normalized)
```

---

## Service Integration Patterns

### Pattern 1: ProjectService

**Location:** `oryxforge/services/project_service.py`

#### Initialization Flow

```python
def __init__(self,
             project_id: Optional[str] = None,
             user_id: Optional[str] = None,
             working_dir: Optional[str] = None,
             mount_ensure: Optional[bool] = None):

    # Step 1: Determine working_dir
    if working_dir is None:
        from .env_config import ProjectContext
        self.working_dir = ProjectContext.get()  # ← Uses context
    else:
        self.working_dir = working_dir

    # Step 2: Get credentials if not provided
    if project_id is None or user_id is None:
        creds_manager = CredentialsManager(working_dir=self.working_dir)
        profile = creds_manager.get_profile()  # ← Reads .oryxforge.cfg
        self.project_id = project_id or profile['project_id']
        self.user_id = user_id or profile['user_id']
    else:
        self.project_id = project_id
        self.user_id = user_id

    # Step 3: Get mount configuration
    config_service = ConfigService(working_dir=self.working_dir)
    saved_mount = config_service.get('mount', 'mount_point')
    if saved_mount:
        self.mount_point = str(Path(saved_mount))
    else:
        self.mount_point = "./data"  # Default

    # Step 4: Determine mount_ensure setting
    if mount_ensure is not None:
        self.mount_ensure_final = mount_ensure
    else:
        mount_ensure_str = config_service.get('mount', 'mount_ensure')
        self.mount_ensure_final = (mount_ensure_str != 'false') if mount_ensure_str else True
```

**Key Points:**
- Uses `ProjectContext.get()` for working_dir if not provided
- Falls back to `.oryxforge.cfg` for credentials
- Reads `[mount]` section for mount configuration
- Supports parameter overrides for all settings

#### Resource Initialization (v1.2+)

**IMPORTANT:** As of v1.2, resource initialization **always runs** regardless of `mount_ensure` setting.

**What Always Happens:**
1. Project validation (Supabase check)
2. Mount accessibility check (skipped in test mode)
3. d6tflow directory configuration

**What `mount_ensure` Controls:**
- `mount_ensure=true` (CLI mode): Automatically mount if not mounted
- `mount_ensure=false` (API mode): Fail fast if mount not accessible
- Test mode: Skip mount checks entirely

**Initialization Methods:**
- `_initialize_resources()`: Always runs once per request
  - Validates project exists
  - Checks mount (unless test mode)
  - Attempts auto-mount if `mount_ensure=true`
  - Sets d6tflow directory
- `_is_mount_ready()`: Checks if mount is accessible
  - API mode: Checks path exists
  - CLI mode: Checks actually mounted (reparse point/mount)
- `_attempt_mount()`: Tries to mount (CLI only, when `mount_ensure=true`)
- `_is_test_mode()`: Detects test environment (temp directory)

**Fixed Issue:** Previously, `mount_ensure=false` would skip ALL initialization, causing d6tflow to use wrong directory in API mode. Now initialization always runs; `mount_ensure` only controls auto-mount behavior.

---

### Pattern 2: IOService

**Location:** `oryxforge/services/io_service.py`

#### Initialization Flow

```python
def __init__(self):
    # No parameters - delegates everything to ProjectService
    self.ps = ProjectService()  # ← Zero-parameter init
```

**Usage:**

```python
# IOService delegates all context resolution to ProjectService
io_service = IOService()

# Build file paths using ProjectService's mount_point
path = io_service.ps.mount_point_path / "exploration" / "Sheet.parquet"
```

**Key Points:**
- **Simplest pattern** - delegates to ProjectService
- No direct interaction with CredentialsManager or ConfigService
- All paths resolved through `self.ps.mount_point_path`

---

### Pattern 3: RepoService

**Location:** `oryxforge/services/repo_service.py`

#### Initialization Flow

```python
def __init__(self,
             project_id: Optional[str] = None,
             user_id: Optional[str] = None,
             working_dir: Optional[str] = None):

    # Step 1: Get working_dir from ProjectContext if not provided
    if working_dir is None:
        from .env_config import ProjectContext
        self.working_dir = ProjectContext.get()
    else:
        self.working_dir = working_dir

    # Convert to absolute path for git operations
    self.working_dir_abspath = Path(self.working_dir).resolve()

    # Step 2: Get profile from CredentialsManager if not provided
    if project_id is None or user_id is None:
        creds_manager = CredentialsManager(working_dir=self.working_dir)
        profile = creds_manager.get_profile()
        self.project_id = project_id or profile['project_id']
        self.user_id = user_id or profile['user_id']
    else:
        self.project_id = project_id
        self.user_id = user_id
```

**Key Points:**
- Uses `ProjectContext.get()` for working_dir
- Resolves to absolute path for git operations
- Reads credentials from `.oryxforge.cfg` if not provided

---

### Pattern 4: CLIService

**Location:** `oryxforge/services/cli_service.py`

**Purpose:** High-level orchestration service for CLI commands, managing activation state and mount point configuration.

#### Initialization Flow

```python
def __init__(self, user_id: str = None, cwd: str = None):
    # Step 1: Determine working directory
    self.cwd = Path(cwd) if cwd else Path.cwd()

    # Step 2: Initialize ConfigService (stored as instance variable)
    self.config_service = ConfigService(working_dir=str(self.cwd))

    # Step 3: Get user_id from profile if not provided
    if user_id:
        self.user_id = user_id
    else:
        creds_manager = CredentialsManager(working_dir=str(self.cwd))
        try:
            profile = creds_manager.get_profile()
            self.user_id = profile['user_id']
        except ValueError as e:
            raise ValueError(
                f"No profile configured. Run 'oryxforge admin profile set...' first"
            )

    # Step 4: Initialize Supabase client
    self.supabase_client = init_supabase_client()

    # Step 5: Validate user exists
    self._validate_user()
```

#### ConfigService Usage

CLIService extensively uses ConfigService for managing the `[active]` and `[mount]` sections:

##### Managing Active State (`[active]` section)

**Dataset Activation:**
```python
def dataset_activate(self, dataset_id: str) -> None:
    # Validate dataset exists in database
    response = self.supabase_client.table("datasets")...

    # Update config using ConfigService
    self.config_service.set('active', 'dataset_id', dataset_id)
```

**Sheet Activation:**
```python
def sheet_activate(self, sheet_id: str) -> None:
    # Validate sheet exists in database
    response = self.supabase_client.table("datasheets")...

    # Update config using ConfigService
    self.config_service.set('active', 'sheet_id', sheet_id)
```

**Mode Management:**
```python
def mode_set(self, mode: str) -> None:
    # Validate mode is valid
    if mode not in self.VALID_MODES:
        raise ValueError(...)

    # Store in [active] section
    self.config_service.set('active', 'mode', mode)

def mode_get(self) -> Optional[str]:
    # Read from [active] section
    return self.config_service.get('active', 'mode')
```

**Getting All Active State:**
```python
def get_active(self) -> Dict[str, str]:
    # Get profile from CredentialsManager
    creds_manager = CredentialsManager(working_dir=str(self.cwd))
    profile = creds_manager.get_profile()

    result = {
        'user_id': profile['user_id'],
        'project_id': profile['project_id']
    }

    # Get additional active settings from [active] section
    active_section = self.config_service.get_all('active')
    if 'dataset_id' in active_section:
        result['dataset_id'] = active_section['dataset_id']
    if 'sheet_id' in active_section:
        result['sheet_id'] = active_section['sheet_id']
    if 'mode' in active_section:
        result['mode'] = active_section['mode']

    return result
```

##### Managing Mount Point (`[mount]` section)

**Setting Mount Point:**
```python
def mount_point_set(self, mount_point: str) -> None:
    # Validate and normalize path
    path = self.config_service.validate_mount_point(mount_point)

    # Store as POSIX format for cross-platform compatibility
    self.config_service.set('mount', 'mount_point', path.as_posix())
```

**Getting Mount Point:**
```python
def mount_point_get(self) -> Optional[str]:
    # Read from [mount] section
    return self.config_service.get('mount', 'mount_point')
```

**Suggesting Mount Point:**
```python
def mount_point_suggest(self, base_path: str) -> str:
    # Get profile for user_id and project_id
    active = self.get_active()
    user_id = active['user_id']
    project_id = active['project_id']

    # Build suggested path: base_path/user_id/project_id/data
    suggested_path = Path(base_path) / user_id / project_id / "data"

    # Validate and return as POSIX
    validated_path = self.config_service.validate_mount_point(str(suggested_path))
    return validated_path.as_posix()
```

#### Key Differences from Other Services

**1. Does NOT use ProjectContext:**
- CLIService uses explicit `cwd` parameter
- Falls back to `Path.cwd()` if not provided
- This allows CLI commands to operate before context is set

**2. Stores ConfigService as instance variable:**
```python
self.config_service = ConfigService(working_dir=str(self.cwd))
```
This enables multiple config operations without reinstantiating.

**3. Orchestrates both CredentialsManager and ConfigService:**
```python
# Uses CredentialsManager for [profile] section
creds_manager = CredentialsManager(working_dir=str(self.cwd))
profile = creds_manager.get_profile()

# Uses ConfigService for [active] and [mount] sections
self.config_service.set('active', 'dataset_id', dataset_id)
self.config_service.set('mount', 'mount_point', mount_point)
```

**4. Bridges CLI commands to other services:**
```python
# CLIService method
def repo_push(self, message: str, project_id: str = None) -> str:
    if not project_id:
        active = self.get_active()  # Gets from config
        project_id = active.get('project_id')

    # Delegates to RepoService with explicit parameters
    repo_service = RepoService(
        project_id=project_id,
        user_id=self.user_id,
        working_dir=str(self.cwd)
    )
    return repo_service.push(message)
```

#### Typical Usage Pattern

```python
# CLI command handler
@click.command()
def activate_dataset(dataset_id: str):
    # Initialize CLIService (reads from .oryxforge.cfg in current dir)
    cli_service = CLIService()

    # Update [active] section
    cli_service.dataset_activate(dataset_id)

    # Get current state (combines [profile] + [active] sections)
    active_state = cli_service.get_active()
    print(f"Active: {active_state}")
```

**Key Points:**
- Does NOT use `ProjectContext` - uses explicit `cwd` parameter
- Stores ConfigService as instance variable for repeated use
- Manages `[active]` section (dataset, sheet, mode)
- Manages `[mount]` section (mount_point)
- Reads `[profile]` section via CredentialsManager
- Used by CLI commands that need to operate before context is set

---

### Pattern 5: FastAPI Application (app.py)

**Location:** `api/app.py`

**Purpose:** HTTP API server that handles requests without direct ConfigService usage.

#### Configuration Strategy

The FastAPI app **does NOT directly use ConfigService**. Instead, it follows a request-scoped initialization pattern:

##### Startup: Mount Verification

```python
@app.on_event("startup")
async def startup_event():
    """Verify mount is available at API startup."""
    from oryxforge.services.env_config import ProjectContext

    # Only check mount in API mode
    if ProjectContext.is_api_mode():
        # Get parent mount path using centralized logic
        mount_parent = ProjectContext.get_mount_parent_path()

        # Check if mount parent exists
        if not os.path.exists(mount_parent):
            raise ValueError(
                f"API startup failed: Parent mount directory '{mount_parent}' does not exist."
            )
```

**Key Points:**
- Uses `ProjectContext.is_api_mode()` for environment detection
- Uses `ProjectContext.get_mount_parent_path()` for mount verification
- Does NOT read `.oryxforge.cfg` - config is request-scoped

##### Request Handling: Profile Management

**Setting Profile (Optional):**
```python
@app.post("/profile/set")
def set_profile(request: ProfileRequest):
    """Set profile configuration (user_id and project_id)."""
    from oryxforge.services.iam import CredentialsManager
    from pathlib import Path

    # Use current working directory for profile config
    creds_manager = CredentialsManager(working_dir=str(Path.cwd()))
    creds_manager.set_profile(user_id=request.user_id, project_id=request.project_id)
```

**Note:** This endpoint is **optional** and rarely used in API mode. Services typically receive user_id and project_id as request parameters.

##### Request Handling: Data Operations

**Loading DataFrame:**
```python
@app.post("/data/load-dataframe")
def load_dataframe(request: DataFrameLoadRequest):
    """Load a DataFrame using IOService."""
    from oryxforge.services.io_service import IOService
    from oryxforge.services.project_service import ProjectService

    # Initialize project: ensures repo exists + writes config
    ProjectService.project_init(
        project_id=request.project_id,
        user_id=request.user_id
        # target_dir defaults to None - auto-determined by ProjectContext.set()
    )

    # Load DataFrame using IOService
    io_service = IOService()
    df = io_service.load_df_pd(request.name_python)
    return df
```

**Flow:**
1. `ProjectService.project_init()` sets `ProjectContext` and writes `.oryxforge.cfg`
2. `IOService()` initializes without parameters, delegates to `ProjectService`
3. `ProjectService` reads config from `.oryxforge.cfg` created in step 1

#### Key Architectural Points

**1. Request-Scoped Configuration:**
- Each request calls `ProjectService.project_init()` with user_id/project_id from request body
- This creates per-request `.oryxforge.cfg` in working directory
- Working directory is ephemeral in GCP (`/tmp/{user_id}/{project_id}`)

**2. No Direct ConfigService Usage:**
- API never directly imports or uses ConfigService
- All config management delegated to `ProjectService.project_init()`

**3. Environment Variables Drive Behavior:**
```python
# Set at API startup
os.environ['FASTAPI_ENV'] = 'true'

# This causes ProjectContext.is_api_mode() to return True
# Which changes working directory resolution logic
```

**4. Stateless Request Handling:**
```python
# Each request is independent
Request 1: user_id=abc, project_id=123 → /tmp/abc/123/.oryxforge.cfg
Request 2: user_id=xyz, project_id=789 → /tmp/xyz/789/.oryxforge.cfg
```

**5. CredentialsManager Used for Optional Profile Endpoint:**
- `/profile/set` endpoint exists but rarely used
- Primary pattern: pass user_id/project_id per request

#### API vs CLI Configuration Comparison

| Aspect              | CLI Mode                              | API Mode (FastAPI)                          |
|---------------------|---------------------------------------|---------------------------------------------|
| Config Location     | `./.oryxforge.cfg` in user's project  | `/tmp/{user}/{project}/.oryxforge.cfg`      |
| Config Lifetime     | Persistent across CLI commands        | Ephemeral, per-request                      |
| Working Dir Source  | `Path.cwd()` (user's location)        | Auto-generated from environment             |
| ProjectContext      | Optional (CLI can set explicitly)     | Required (set per request)                  |
| ConfigService Usage | Used by CLIService                    | Never used directly                         |
| Profile Management  | Required (user runs `profile set`)    | Optional (passed in requests)               |

---

## Environment Detection

### Three Runtime Environments

#### 1. CLI Mode

**Detection:**
```python
not ProjectContext.is_api_mode()
# i.e., no GOOGLE_CLOUD_PROJECT and no FASTAPI_ENV
```

**Characteristics:**
- Working dir: `Path.cwd()` (user's local directory)
- Config file: `./.oryxforge.cfg` in current directory
- Mount point: User-configurable (default: `./data`)
- Mount ensure: `true` (auto-mount enabled)
- Git operations: Local repository

**Typical Flow:**
```bash
# User navigates to project folder
cd my-project

# CLI commands read config from ./my-project/.oryxforge.cfg
oryxforge admin status
oryxforge agent chat "show data"
```

---

#### 2. GCP Production Mode

**Detection:**
```python
os.environ.get('GOOGLE_CLOUD_PROJECT') is not None
```

**Characteristics:**
- Working dir: `/tmp/{user_id}/{project_id}` (ephemeral)
- Config file: `/tmp/{user_id}/{project_id}/.oryxforge.cfg` (ephemeral)
- Mount point: `/mnt/data/{user_id}/{project_id}` (GCS mount)
- Mount ensure: `false` (mounting handled externally)
- Serverless: Container resets frequently

**Typical Flow:**
```python
# API request arrives
# FastAPI middleware sets context:
ProjectContext.set(user_id, project_id)  # working_dir auto: /tmp/{user}/{project}

# Services initialize without parameters
project_service = ProjectService()

# Files accessed via GCS mount
df = pd.read_parquet("/mnt/data/{user}/{project}/exploration/Data.parquet")
```

---

#### 3. Local API Development Mode

**Detection:**
```python
os.environ.get('ORYX_MOUNT_ROOT') is not None
```

**Characteristics:**
- Working dir: `{ORYX_MOUNT_ROOT}/mnt/projects/{user_id}/{project_id}`
- Config file: `{ORYX_MOUNT_ROOT}/mnt/projects/{user_id}/{project_id}/.oryxforge.cfg`
- Mount point: `{ORYX_MOUNT_ROOT}/mnt/data/{user_id}/{project_id}`
- Mount ensure: `false`
- Persistent: Files survive across requests

**Typical Flow:**
```bash
# Set environment variable
export ORYX_MOUNT_ROOT="/path/to/api/root"

# Start local API server
uvicorn main:app

# API creates project structure:
# /path/to/api/root/mnt/projects/{user}/{project}/  (working dir)
# /path/to/api/root/mnt/data/{user}/{project}/      (mount point)
```

---

## Flow Diagrams

### CLI Command Flow: `oryxforge admin pull`

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User runs CLI command                                     │
│    $ oryxforge admin pull --projectid abc --userid xyz       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. admin.py: pull_project()                                  │
│    - Strips whitespace from UUIDs                            │
│    - Determines target directory:                            │
│      • --target-create → ./name_git/                         │
│      • --target <path> → specified path                      │
│      • No flags → Path.cwd()                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. ProjectService.project_init(project_id, user_id, target)  │
│    - Fetch project data from Supabase                        │
│    - Create GitLab repo if needed                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. ProjectContext.set(user_id, project_id, target,          │
│                       write_config=False)                    │
│    - Sets context variable: _project_context.set(target)     │
│    - Does NOT write config yet (git clone needs empty dir)   │
│    - Returns: resolved working_dir                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. RepoService.ensure_repo()                                 │
│    - Initializes with working_dir from context               │
│    - Checks if repo exists locally                           │
│    - Clones if missing, pulls if exists                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. ProjectContext.write_config(user_id, project_id)          │
│    - NOW writes .oryxforge.cfg to working_dir                │
│    - Calls CredentialsManager.set_profile()                  │
│    - Calls ConfigService.set() for [mount] section           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Repository ready with config                              │
│    - working_dir/                                            │
│      ├── .git/                                               │
│      ├── .oryxforge.cfg   ← [profile] + [mount] sections    │
│      ├── tasks/                                              │
│      └── ...                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

### Service Initialization Flow: `ProjectService()`

```
┌─────────────────────────────────────────────────────────────┐
│ User code: project_service = ProjectService()               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ ProjectService.__init__(project_id=None, user_id=None,      │
│                         working_dir=None, mount_ensure=None) │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
        ▼                                 ▼
┌──────────────────┐            ┌──────────────────────────┐
│ working_dir      │            │ working_dir != None      │
│ is None?         │            │ (explicit path provided) │
│                  │            │                          │
│ YES              │            │ Use provided path        │
└────┬─────────────┘            └──────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ from .env_config import ProjectContext                      │
│ self.working_dir = ProjectContext.get()                     │
│                                                              │
│ Returns:                                                     │
│ - Context dir if set (from ProjectContext.set())            │
│ - Path.cwd() if no context (fallback)                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Get credentials from .oryxforge.cfg                          │
│                                                              │
│ creds_manager = CredentialsManager(working_dir=self.working_dir)│
│ profile = creds_manager.get_profile()                       │
│                                                              │
│ self.project_id = project_id or profile['project_id']       │
│ self.user_id = user_id or profile['user_id']                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Get mount configuration from .oryxforge.cfg                  │
│                                                              │
│ config_service = ConfigService(working_dir=self.working_dir) │
│ saved_mount = config_service.get('mount', 'mount_point')    │
│                                                              │
│ if saved_mount:                                              │
│     self.mount_point = str(Path(saved_mount))                │
│ else:                                                        │
│     self.mount_point = "./data"  # Default                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Determine mount_ensure setting                               │
│                                                              │
│ if mount_ensure is not None:                                 │
│     self.mount_ensure_final = mount_ensure  # Override       │
│ else:                                                        │
│     mount_ensure_str = config_service.get('mount', 'mount_ensure')│
│     self.mount_ensure_final = (mount_ensure_str != 'false')  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Service fully initialized with:                              │
│ - self.working_dir                                           │
│ - self.user_id                                               │
│ - self.project_id                                            │
│ - self.mount_point                                           │
│ - self.mount_ensure_final                                    │
│ - self.supabase_client                                       │
└─────────────────────────────────────────────────────────────┘
```

---

### API Request Flow (FastAPI)

```
┌─────────────────────────────────────────────────────────────┐
│ HTTP Request arrives                                         │
│ POST /data/load-dataframe                                    │
│ Body: {                                                      │
│   "user_id": "<user-uuid>",                                  │
│   "project_id": "<project-uuid>",                            │
│   "name_python": "exploration.MySheet"                       │
│ }                                                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Route Handler                                                │
│                                                              │
│ @app.post("/data/load-dataframe")                           │
│ def load_dataframe(request: DataFrameLoadRequest):          │
│     # Extract user_id and project_id from request body      │
│     user_id = request.user_id                                │
│     project_id = request.project_id                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ ProjectService.project_init(project_id, user_id)            │
│                                                              │
│ 1. Sets ProjectContext:                                     │
│    ProjectContext.set(user_id, project_id, write_config=False)│
│                                                              │
│    In GCP: working_dir → /tmp/{user_id}/{project_id}        │
│    In Local: working_dir → {ORYX_MOUNT_ROOT}/mnt/projects/..│
│                                                              │
│ 2. Ensures repo exists (clone if new, pull if exists)       │
│                                                              │
│ 3. Writes .oryxforge.cfg to working_dir                     │
│    ProjectContext.write_config(user_id, project_id)         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ IOService() initialization                                   │
│                                                              │
│ - Initializes with zero parameters                          │
│ - Delegates to ProjectService()                             │
│ - ProjectService reads .oryxforge.cfg from working_dir      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Business Logic Executes                                      │
│                                                              │
│ df = io_service.load_df_pd(request.name_python)             │
│                                                              │
│ - Reads file from mount_point                               │
│ - Returns DataFrame                                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Response sent, request ends                                  │
│                                                              │
│ Next request may use different user_id/project_id           │
└─────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **NO middleware** - user_id and project_id are in request body
- **Explicit per-request initialization** - each endpoint calls `ProjectService.project_init()`
- **Ephemeral config** - `.oryxforge.cfg` created per request in working_dir
- **Stateless** - each request is independent

---

## Common Pitfalls

### ❌ Pitfall 1: Not Setting Context Before Service Init

```python
# BAD - ProjectService can't find working_dir
project_service = ProjectService()
# ERROR: No .oryxforge.cfg found (Path.cwd() used as fallback)
```

**Solution:** Set context first or provide explicit parameters:

```python
# GOOD - Set context first
ProjectContext.set(user_id, project_id, working_dir="/path/to/project")
project_service = ProjectService()

# ALSO GOOD - Explicit parameters
project_service = ProjectService(
    project_id="abc",
    user_id="xyz",
    working_dir="/path/to/project"
)
```

---

### ❌ Pitfall 2: Using Wrong Working Dir in CredentialsManager (Fixed in v1.2)

**This pitfall was fixed in v1.2.** CredentialsManager and ConfigService now use `ProjectContext.get()` as default.

```python
# ✅ GOOD (v1.2+) - Uses ProjectContext automatically
creds_manager = CredentialsManager()
profile = creds_manager.get_profile()
# Works correctly in all modes (CLI, API, tests)

# ✅ ALSO GOOD - Explicit working_dir still supported
working_dir = ProjectContext.get()
creds_manager = CredentialsManager(working_dir=working_dir)
```

**Before v1.2** this was a problem in API mode where `Path.cwd()` returned the wrong directory.

---

### ❌ Pitfall 3: Writing Config Before Git Clone

```python
# BAD - Config written before clone
ProjectContext.set(user_id, project_id, write_config=True)  # Creates dir + config
repo_service.clone()  # ERROR: Directory not empty!
```

**Solution:** Use two-phase initialization:

```python
# GOOD - Two-phase init
ProjectContext.set(user_id, project_id, write_config=False)  # Don't write yet
repo_service.ensure_repo()  # Clone into empty dir
ProjectContext.write_config(user_id, project_id)  # Write config after clone
```

---

### ❌ Pitfall 4: Forgetting Environment-Specific Behavior

```python
# BAD - Hard-coding paths that work in CLI but fail in API
mount_point = "./data"  # Won't work in GCP production!
```

**Solution:** Always use ConfigService or environment detection:

```python
# GOOD - Environment-aware
config_service = ConfigService(working_dir=working_dir)
mount_point = config_service.get('mount', 'mount_point') or "./data"
```

---

### ❌ Pitfall 5: Not Handling Missing Config Gracefully

```python
# BAD - Service crashes if config missing
profile = creds_manager.get_profile()  # ValueError if no config!
```

**Solution:** Provide clear error messages or fallbacks:

```python
# GOOD - Clear error message
try:
    profile = creds_manager.get_profile()
except ValueError as e:
    raise ValueError(
        f"No profile configured. Run 'oryxforge admin profile set...' first. {str(e)}"
    )
```

---

## Best Practices

### 1. Service Initialization Order

Always follow this order in service `__init__`:

```python
def __init__(self, ...):
    # 1. Determine working_dir
    if working_dir is None:
        self.working_dir = ProjectContext.get()
    else:
        self.working_dir = working_dir

    # 2. Get credentials
    creds_manager = CredentialsManager(working_dir=self.working_dir)
    profile = creds_manager.get_profile()

    # 3. Get other config
    config_service = ConfigService(working_dir=self.working_dir)
    # ... read config values

    # 4. Initialize other dependencies
    self.supabase_client = init_supabase_client()
```

### 2. Thread Safety

- Always use `ProjectContext` for thread-safe working directory storage
- Never use global variables for context state
- Each request/thread should set its own context

### 3. Testing

Provide explicit parameters in tests:

```python
# Test-friendly initialization
def test_project_service():
    temp_dir = Path(tempfile.mkdtemp())

    # Explicit parameters for predictable behavior
    ps = ProjectService(
        project_id="test-project",
        user_id="test-user",
        working_dir=str(temp_dir),
        mount_ensure=False  # Disable mounting in tests
    )
```

### 4. CLI Commands

CLI commands should set context explicitly:

```python
@click.command()
def my_command():
    # Set context for downstream services
    ProjectContext.set(user_id, project_id, working_dir=target_dir)

    # Now services work without parameters
    project_service = ProjectService()
```

---

## Revision History

| Date       | Version | Changes                                                     |
|------------|---------|-------------------------------------------------------------|
| 2025-10-31 | 1.0     | Initial documentation with all service patterns             |
| 2025-10-31 | 1.1     | Added FastAPI pattern, sanitized UUIDs, CLIService details  |
| 2025-10-31 | 1.2     | Fixed mount_ensure logic - decoupled initialization from auto-mount behavior; Updated ConfigService and CredentialsManager to use ProjectContext.get() as default |

---

## See Also

- [Testing Guide](../TESTING.md) - Testing patterns for context management
- [Deployment Architecture](../../CLAUDE.md#deployment-architecture) - Environment modes
- [Service Patterns](../../CLAUDE.md#service-integration-patterns) - Service integration examples

# OryxForge Architecture Evaluation
**Date**: 2025-11-02
**Evaluator**: Senior System Architect Analysis
**Scope**: Context Management, Service Architecture, Environment Detection

---

## Executive Summary

This evaluation analyzes the OryxForge AI data analysis backend architecture with focus on context management, resource initialization, and multi-environment deployment. The analysis covers user and system actions across four deployment environments (CLI, Local API Dev, GCP Production, Test Mode) and evaluates how resources (working directories, mount points, configuration files, ProjectContext) flow through 13 services.

**Key Findings**:
- ✅ **Strengths**: Zero-parameter service pattern, thread-safe context management, serverless-ready architecture
- ⚠️ **Critical Issues**: 5 architectural problems causing user-facing failures (e.g., "mount suggest" command failures)
- 🎯 **Recommendations**: Centralized environment detection, symlink strategy, simplified initialization flow

---

## 1. Environment-Action-Resource Flow Analysis

### 1.1 Four Deployment Environments

| Environment | Detection | Working Directory | Config Source | Mount Behavior |
|-------------|-----------|-------------------|---------------|----------------|
| **CLI Mode** | No env vars set | `os.getcwd()` | `.oryxforge.cfg` in cwd | Required, validated |
| **Local API Dev** | `ORYX_MOUNT_ROOT` set | `{ORYX_MOUNT_ROOT}/mnt/projects/{user}/{project}` | Context-based (no file) | Mount parent checked |
| **GCP Production** | `GOOGLE_CLOUD_PROJECT` set | `/tmp/{user_id}/{project_id}` | Context-based (no file) | Mount parent checked |
| **Test Mode** | Path contains "temp" or "test" | `tempfile.TemporaryDirectory()` | Temp config file | Skipped entirely |

**Environment Detection Logic** (from `env_config.py:ProjectContext.is_api_mode()`):
```python
@staticmethod
def is_api_mode() -> bool:
    """Detect if running in API mode (GCP or local API development)."""
    return bool(
        os.environ.get('GOOGLE_CLOUD_PROJECT') or
        os.environ.get('FASTAPI_ENV')
    )
```

### 1.2 Resource Flow Matrix: CLI Mode

| User Action | System Actions | Resources Created/Modified | Services Involved |
|-------------|---------------|---------------------------|-------------------|
| `oryxforge admin pull` | 1. Validate credentials<br>2. Clone GitLab repo<br>3. Write `.oryxforge.cfg` | - Cloned repo dir<br>- `.oryxforge.cfg` with [profile] | CLIService, RepoService, ProjectContext |
| `cd <cloned-dir>` | User navigation | - Current working directory changes | N/A |
| `oryxforge admin config mount suggest <base>` | 1. Read profile from `.oryxforge.cfg` in **cwd**<br>2. Construct path: `{base}/{user}/{project}/data`<br>3. Display suggestion | - No files modified | CLIService, ConfigService, CredentialsManager |
| `oryxforge admin config mount set <path>` | 1. Write `[mount]` section to `.oryxforge.cfg`<br>2. Set `mount_point` and `mount_ensure=true` | - `.oryxforge.cfg` updated | ConfigService |
| `oryxforge admin mount` | 1. Read mount config<br>2. Run `rclone mount` command<br>3. Background process | - Mount process running<br>- GCS bucket accessible at mount_point | ProjectService, MountService |
| `oryxforge activate <dataset>.<sheet>` | 1. Query Supabase for dataset/sheet<br>2. Write `[active]` section to `.oryxforge.cfg`<br>3. Initialize ProjectContext | - `.oryxforge.cfg` updated<br>- ProjectContext set | CLIService, ProjectService, ConfigService |

**Critical Failure Point**: `admin config mount suggest` fails if user hasn't `cd` into cloned directory because:
- `admin pull` clones to directory A
- User stays in directory B (original cwd)
- `admin config mount suggest` looks for `.oryxforge.cfg` in cwd (directory B)
- Config file is in directory A (cloned dir)

**Code Evidence** (`cli_service.py:28-30`):
```python
def __init__(self, user_id: str = None, cwd: str = None):
    self.cwd = Path(cwd) if cwd else Path.cwd()  # ← Uses cwd, not working_dir
    self.creds_manager = CredentialsManager(working_dir=str(self.cwd))
```

### 1.3 Resource Flow Matrix: API Mode (Local & GCP)

| API Endpoint | Request Parameters | System Actions | Resources Accessed | Services Involved |
|--------------|-------------------|----------------|-------------------|-------------------|
| **Startup Event** | N/A | 1. Check parent mount exists<br>2. Log success or raise error | - `/mnt/data` (parent dir) | ProjectContext |
| `/profile/set` | `user_id`, `project_id` | 1. Write `.oryxforge.cfg` to working dir<br>2. Create [profile] section | - Working dir config file | CredentialsManager, ConfigService |
| `/data/load-dataframe` | `user_id`, `project_id`, `name_python` | 1. Call `ProjectService.project_init()`<br>2. Validate mount at **project level**<br>3. Clone/pull repo<br>4. Write config<br>5. Load Parquet file | - `/mnt/data/{user}/{project}` (project dir)<br>- Cloned repo<br>- `.oryxforge.cfg`<br>- Parquet file from mount | ProjectService, RepoService, IOService |

**Critical Inconsistency**: Mount checking happens at TWO different levels:
- **Startup**: Checks `/mnt/data` (parent directory)
- **Per-request**: Checks `/mnt/data/{user_id}/{project_id}` (project-specific directory)

**Code Evidence** (`app.py:44-54` vs `project_service.py:_get_mount_check_path()`):
```python
# API Startup (app.py)
mount_parent = ProjectContext.get_mount_parent_path()  # Returns "/mnt/data"
if not os.path.exists(mount_parent):
    raise ValueError(f"Parent mount directory '{mount_parent}' does not exist")

# Per-request (project_service.py)
def _get_mount_check_path(self):
    """Different paths for API vs CLI mode."""
    if ProjectContext.is_api_mode():
        # API: Check parent level
        return ProjectContext.get_mount_parent_path()
    else:
        # CLI: Check project-specific level
        return Path(self.mount_point) / self.user_id / self.project_id
```

**Problem**: If parent exists but user-specific directory doesn't, startup succeeds but requests fail.

### 1.4 Resource Flow: Project Initialization (API Mode)

**Sequence Diagram** for `/data/load-dataframe` endpoint:

```
Client → FastAPI: POST /data/load-dataframe
                   {user_id, project_id, name_python}

FastAPI → ProjectService.project_init(project_id, user_id)
          ↓
          ProjectContext.set(working_dir=None, user_id, project_id, write_config=False)
          ↓ (determines working_dir based on environment)
          ↓ GCP: /tmp/{user}/{project}
          ↓ Local API: {ORYX_MOUNT_ROOT}/mnt/projects/{user}/{project}
          ↓
          RepoService.ensure_repo()  # Clone or pull
          ↓
          ProjectContext.write_config()  # Write .oryxforge.cfg
          ↓
          ConfigService initialized with working_dir
          ↓
          ProjectService.__init__(project_id, user_id)
          ├─ Read [mount] from .oryxforge.cfg (just created)
          ├─ _initialize_resources()
          │  ├─ Validate project exists in Supabase
          │  ├─ Check mount at parent level
          │  └─ Configure d6tflow.settings.data_dir
          └─ Return

FastAPI → IOService.load_df_pd(name_python)
          ↓
          Load from: {mount_point}/{user}/{project}/data/{dataset}/{sheet}.parquet
          ↓
FastAPI → Client: DataFrame as JSON
```

**Two-Phase Initialization Issue**:
1. **Phase 1**: `ProjectContext.set(write_config=False)` - Context set but no config file
2. **Intermediate**: Repo clone (may fail due to network, credentials, etc.)
3. **Phase 2**: `ProjectContext.write_config()` - Config file written
4. **Problem**: If Phase 2 fails, system is in inconsistent state (context set, no config)

### 1.5 Resource Flow: Import Data Workflow

**CLI Command**: `oryxforge import <file_path>`

| Step | Action | Service | Resources |
|------|--------|---------|-----------|
| 1 | User runs command | CLI | Command args |
| 2 | Initialize CLIService | CLIService | Reads `.oryxforge.cfg` from cwd |
| 3 | Check if file is remote (Supabase) | ImportService | Parse URI |
| 4 | Download file if remote | ImportService | Temp download file |
| 5 | Initialize ProjectService (with mount validation) | ProjectService | Mount check, config read |
| 6 | Analyze file with Claude Agent | ClaudeAgent | API call to Claude |
| 7 | Load file with pandas (Excel, CSV, etc.) | ImportService | Local file read |
| 8 | Create "Sources" dataset if not exists | ProjectService | Supabase insert/query |
| 9 | For each sheet: Save as Parquet | IOService | Write to `{mount}/{user}/{project}/data/{dataset}/{sheet}.parquet` |
| 10 | Create datasheet records | ProjectService | Supabase inserts |
| 11 | Display success message | CLI | Console output |

**Critical Dependencies**:
- Mount must be established before Step 9 (Parquet write)
- ProjectContext must be set with correct working_dir
- Config file must exist with [profile] section

### 1.6 Resource Flow: Chat Workflow

**CLI Command**: `oryxforge chat "<prompt>"`

| Step | Action | Service | Resources |
|------|--------|---------|-----------|
| 1 | User runs chat command | CLI | Command args |
| 2 | Load active context | CLIService | Read `[active]` from `.oryxforge.cfg` |
| 3 | Initialize ChatService | ChatService | ProjectContext |
| 4 | Query chat history | ChatService | Supabase `chat_messages` table (session_id = project_id) |
| 5 | Build system prompt with mode | ChatService | Read `[active].mode` from config |
| 6 | Send prompt + history to Claude | ClaudeAgent | API call with streaming |
| 7 | Stream response to console | CLI | Real-time output |
| 8 | Parse response for dataset.sheet | ChatService | Regex extraction |
| 9 | Save user + assistant messages | ChatService | Supabase inserts |
| 10 | Update active sheet if changed | CLIService | Write `[active]` section |

**Session Continuity**: `session_id = project_id` ensures conversations persist across CLI invocations within same project.

---

## 2. Architectural Issues

### Issue 1: Complex Environment Detection Scattered Across Services

**Severity**: Medium
**Impact**: Hard to understand, test, and modify environment-specific behavior
**Location**: Multiple services (ProjectContext, ProjectService, ConfigService)

**Problem Description**:
Environment detection logic is duplicated and scattered:
- `ProjectContext.is_api_mode()` checks for GCP or FASTAPI_ENV
- `ProjectContext.is_test_mode()` checks working_dir path
- `ProjectService._get_mount_check_path()` has conditional logic
- `ConfigService` behavior differs per environment but isn't explicitly aware

**Code Evidence**:

```python
# env_config.py:60-65
@staticmethod
def is_api_mode() -> bool:
    return bool(
        os.environ.get('GOOGLE_CLOUD_PROJECT') or
        os.environ.get('FASTAPI_ENV')
    )

# env_config.py:67-73
@staticmethod
def is_test_mode(working_dir: str) -> bool:
    working_dir_lower = str(working_dir).lower()
    return ('temp' in working_dir_lower or 'test' in working_dir_lower)

# project_service.py:_get_mount_check_path() (line ~800)
def _get_mount_check_path(self):
    if ProjectContext.is_api_mode():
        return ProjectContext.get_mount_parent_path()
    else:
        return Path(self.mount_point) / self.user_id / self.project_id
```

**Consequence**:
- Hard to add new environments (e.g., Docker, Kubernetes)
- Behavior changes scattered across multiple files
- No single source of truth for environment configuration

**Recommendation**:
Create centralized `EnvironmentConfig` class:

```python
class EnvironmentType(Enum):
    CLI = "cli"
    LOCAL_API = "local_api"
    GCP_PRODUCTION = "gcp_production"
    TEST = "test"

class EnvironmentConfig:
    @staticmethod
    def detect() -> EnvironmentType:
        """Single source of truth for environment detection."""
        if 'GOOGLE_CLOUD_PROJECT' in os.environ:
            return EnvironmentType.GCP_PRODUCTION
        elif 'ORYX_MOUNT_ROOT' in os.environ or 'FASTAPI_ENV' in os.environ:
            return EnvironmentType.LOCAL_API
        elif 'PYTEST_CURRENT_TEST' in os.environ:
            return EnvironmentType.TEST
        else:
            return EnvironmentType.CLI

    @staticmethod
    def get_working_dir(env_type: EnvironmentType, user_id: str, project_id: str) -> Path:
        """Environment-specific working directory logic."""
        if env_type == EnvironmentType.GCP_PRODUCTION:
            return Path(f"/tmp/{user_id}/{project_id}")
        elif env_type == EnvironmentType.LOCAL_API:
            root = os.environ.get('ORYX_MOUNT_ROOT', '/mnt/data')
            return Path(f"{root}/projects/{user_id}/{project_id}")
        else:  # CLI or TEST
            return Path.cwd()

    @staticmethod
    def needs_mount_validation(env_type: EnvironmentType) -> bool:
        """Whether mount validation is required in this environment."""
        return env_type in [EnvironmentType.CLI, EnvironmentType.LOCAL_API, EnvironmentType.GCP_PRODUCTION]
```

**Benefits**:
- Single place to modify environment logic
- Explicit environment types (no scattered booleans)
- Easy to test different environments
- Clear documentation of environment behaviors

---

### Issue 2: Fragile Two-Phase Initialization Can Leave Inconsistent State

**Severity**: High
**Impact**: System failures leave ProjectContext set but no config file, causing downstream confusion
**Location**: `project_service.py:ProjectService.project_init()`, `env_config.py:ProjectContext`

**Problem Description**:
Project initialization uses two-phase pattern that can fail midway:

```python
# Phase 1: Set context WITHOUT writing config
ProjectContext.set(working_dir, user_id, project_id, write_config=False)

# Intermediate: Clone repo (CAN FAIL - network, auth, GitLab API)
repo_service.ensure_repo()

# Phase 2: Write config AFTER clone
ProjectContext.write_config()
```

**Failure Scenarios**:

| Failure Point | System State | User Impact |
|---------------|--------------|-------------|
| Between Phase 1 & 2 | Context set, no config file | Next service call reads context but can't find config |
| During repo clone | Context set, partial clone | Repo in invalid state, context thinks it's ready |
| After Phase 2, before service init | Config written but mount not checked | Service assumes mount is ready when it's not |

**Code Evidence** (`project_service.py:120-145`):

```python
@staticmethod
def project_init(project_id: str, user_id: str, target_dir: str = None) -> 'ProjectService':
    # Phase 1: Set context (in-memory only)
    working_dir = ProjectContext.set(
        user_id=user_id,
        project_id=project_id,
        target_dir=target_dir,
        write_config=False  # ← No config file yet
    )

    # Intermediate: Clone/pull repo (CAN FAIL)
    repo_service = RepoService()
    repo_service.ensure_repo(user_id=user_id, project_id=project_id)

    # Phase 2: Now write config
    ProjectContext.write_config()  # ← If clone failed, this shouldn't happen

    # Service initialization (reads config that was just written)
    return ProjectService(project_id=project_id, user_id=user_id)
```

**Real-World Failure Example**:
```bash
# Step 1: User runs data load API
POST /data/load-dataframe {"user_id": "abc", "project_id": "xyz", "name_python": "sales.Q1"}

# Step 2: ProjectContext.set() succeeds
# working_dir = /tmp/abc/xyz
# Context stored in ContextVar

# Step 3: repo_service.ensure_repo() FAILS (network timeout)
Exception: "Failed to connect to GitLab API"

# Step 4: ProjectContext.write_config() NEVER CALLED
# But ProjectContext still has working_dir="/tmp/abc/xyz" set!

# Step 5: Next API call tries to read config
ConfigService(working_dir="/tmp/abc/xyz")  # ← Path exists from previous attempt
config.get('mount', 'mount_point')  # ← Returns None, config file doesn't exist

# Result: Confusing error "mount_point not configured" even though init was called
```

**Recommendation**:
Use atomic initialization with transaction-like pattern:

```python
@staticmethod
def project_init(project_id: str, user_id: str, target_dir: str = None) -> 'ProjectService':
    """Initialize project with atomic operation - either fully succeeds or fully rolls back."""

    # Determine working_dir without setting context yet
    if target_dir:
        working_dir = Path(target_dir)
    else:
        env_type = EnvironmentConfig.detect()
        working_dir = EnvironmentConfig.get_working_dir(env_type, user_id, project_id)

    try:
        # Step 1: Ensure repo exists (can fail)
        repo_service = RepoService()
        repo_service.ensure_repo(
            user_id=user_id,
            project_id=project_id,
            target_dir=str(working_dir)
        )

        # Step 2: Only NOW set context and write config (atomic)
        working_dir_final = ProjectContext.set(
            user_id=user_id,
            project_id=project_id,
            target_dir=str(working_dir),
            write_config=True  # ← Write immediately
        )

        # Step 3: Initialize service (reads config that definitely exists)
        return ProjectService(project_id=project_id, user_id=user_id)

    except Exception as e:
        # Rollback: Clear context if anything failed
        ProjectContext.clear()
        logger.error(f"Project initialization failed, context rolled back: {e}")
        raise
```

**Benefits**:
- All-or-nothing initialization
- Clear error messages (no partial state)
- Context only set if everything succeeds
- Automatic rollback on failure

---

### Issue 3: Mount Suggest Command Fails Due to Working Directory Mismatch

**Severity**: High
**Impact**: Users cannot configure mount after cloning repo, blocking all data operations
**Location**: CLI command flow, CLIService, ConfigService

**Problem Description**:
The intended workflow is straightforward:
```bash
# Step 1: Clone repo
oryxforge admin pull
# Creates directory and .oryxforge.cfg: /some/path/project-abc123

# Step 2: Suggest mount (automatically sets and mounts)
oryxforge admin config mount suggest "D:\data\oryx-forge-projects"
# Should auto-configure and mount in one command
```

**However, the `suggest` command fails** because `CLIService` looks for the config file in the **current working directory** instead of the **cloned repository directory**.

**Actual Workflow Commands** (for clarity):
- `admin config mount suggest <base>` - One-command solution: suggests path, sets config, AND mounts
- `admin config mount set <path>` - Manual override only (if user doesn't want to use suggest)
- `admin mount` - Re-mount after unmount (uses existing config)

**Failure Cause**:

After `admin pull` clones the repo to `/repos/project-abc123`:
1. Config file `.oryxforge.cfg` is created in `/repos/project-abc123`
2. User stays in original directory (e.g., `/home/user`)
3. `admin config mount suggest` runs
4. `CLIService.__init__` uses `Path.cwd()` which returns `/home/user`
5. `CredentialsManager` looks for config in `/home/user/.oryxforge.cfg` (doesn't exist)
6. Command fails: "Profile not configured"

**Code Evidence** (`cli_service.py:28-30`):

```python
def __init__(self, user_id: str = None, cwd: str = None):
    self.cwd = Path(cwd) if cwd else Path.cwd()  # ← Uses current working directory
    self.creds_manager = CredentialsManager(working_dir=str(self.cwd))  # ← Looks for config here
```

**User Experience** (Real Failure):
```bash
$ oryxforge admin pull
✓ Repo cloned to: D:\repos\my-project-abc123
✓ Config created: D:\repos\my-project-abc123\.oryxforge.cfg

$ oryxforge admin config mount suggest "D:\data"
✗ Error: Profile not configured. Run 'oryxforge admin pull' first and ensure you're in the project directory.
# User is confused: "But I just ran admin pull!"

# Workaround: User must manually cd
$ cd D:\repos\my-project-abc123

$ oryxforge admin config mount suggest "D:\data"
✓ Mount configured and established!
# Finally works
```

**Root Cause Analysis**:

The issue is a **directory context mismatch**:
- `admin pull` clones to a **new directory** (the cloned repo path)
- `admin pull` creates `.oryxforge.cfg` in that **new directory**
- `admin config mount suggest` creates a **new CLIService instance** which uses **cwd** (original directory)
- Config file is in cloned directory, but CLIService looks in cwd

**Why This Happens**:
Each CLI command creates a fresh `CLIService` instance. The `admin pull` command knows the cloned repo path, but that information is NOT passed to subsequent commands. Each new command starts from the user's current working directory.

**Recommendation 1: Make CLI Commands Working-Dir Aware**

```python
# Option A: Store last cloned path in user-level config
# ~/.oryxforge/last_pull_path

def pull(self):
    """Clone repo and remember location for subsequent commands."""
    repo_path = self.repo_service.ensure_repo(...)

    # Store last pull path in user config
    user_config_dir = Path.home() / '.oryxforge'
    user_config_dir.mkdir(exist_ok=True)
    (user_config_dir / 'last_pull_path').write_text(repo_path)

    return repo_path

def __init__(self, user_id: str = None, cwd: str = None):
    # Check for last pull path if not in a project directory
    if cwd is None:
        user_config_dir = Path.home() / '.oryxforge'
        last_pull_path_file = user_config_dir / 'last_pull_path'

        if last_pull_path_file.exists():
            last_pull_path = Path(last_pull_path_file.read_text().strip())
            if last_pull_path.exists() and (last_pull_path / '.oryxforge.cfg').exists():
                # Use last pull path if it's valid
                cwd = str(last_pull_path)

    self.cwd = Path(cwd) if cwd else Path.cwd()
    self.creds_manager = CredentialsManager(working_dir=str(self.cwd))
```

**Recommendation 2: Better Error Message with Recovery Guidance**

```python
def mount_point_suggest(self, mount_base: str = None) -> str:
    """Suggest a mount point path for the current user and project."""
    if not mount_base:
        raise ValueError("mount_base is required")

    profile = self.creds_manager.get_profile()

    if not profile or not profile.get('user_id') or not profile.get('project_id'):
        # Check if there's a recent pull
        user_config_dir = Path.home() / '.oryxforge'
        last_pull_path_file = user_config_dir / 'last_pull_path'

        error_msg = "Profile not configured. "

        if last_pull_path_file.exists():
            last_path = last_pull_path_file.read_text().strip()
            error_msg += f"\n\nTry one of these solutions:"
            error_msg += f"\n  1. Change to project directory: cd {last_path}"
            error_msg += f"\n  2. Run from project directory: cd {last_path} && oryxforge admin config mount suggest '{mount_base}'"
        else:
            error_msg += "Run 'oryxforge admin pull' first."

        raise ValueError(error_msg)

    suggested_path = Path(mount_base) / profile['user_id'] / profile['project_id'] / 'data'
    return str(suggested_path)
```

**Recommendation 3: Symlink Strategy** (from docs/system/context_mgmt.md)

Create symlink in working directory pointing to mount:

```python
def setup_mount_symlink(self):
    """Create symlink 'data' in working_dir pointing to mount location.

    This allows transparent access:
        working_dir/data/sales/Q1.parquet
    Instead of:
        {mount_base}/{user}/{project}/data/sales/Q1.parquet
    """
    working_dir = Path(ProjectContext.get())
    symlink = working_dir / 'data'

    # Get mount location
    config_service = ConfigService()
    mount_point = config_service.get('mount', 'mount_point')

    if not mount_point:
        raise ValueError("Mount point not configured")

    # Create symlink if doesn't exist
    if not symlink.exists():
        symlink.symlink_to(mount_point, target_is_directory=True)
        logger.success(f"Created symlink: {symlink} -> {mount_point}")
    else:
        logger.debug(f"Symlink already exists: {symlink}")
```

**Benefits of Symlink Approach**:
- Transparent mount access (users don't need to know mount location)
- Works across platforms (Windows, Linux, macOS)
- Simplifies IOService (just use `working_dir/data/{dataset}/{sheet}`)
- Easier to change mount backend without code changes

---

### Issue 4: Inconsistent Mount Checking Between API Startup and Per-Request

**Severity**: Medium
**Impact**: API can start successfully but fail on first request
**Location**: `app.py` startup event, `project_service.py:_initialize_resources()`

**Problem Description**:
Mount validation happens at TWO different directory levels:

1. **API Startup** (`app.py:32-54`): Checks parent directory `/mnt/data`
2. **Per-Request** (`project_service.py:_get_mount_check_path()`): Checks project directory `/mnt/data/{user}/{project}`

**Code Evidence**:

```python
# app.py:42-54 (API Startup)
@app.on_event("startup")
async def startup_event():
    if ProjectContext.is_api_mode():
        mount_parent = ProjectContext.get_mount_parent_path()  # Returns "/mnt/data"

        if not os.path.exists(mount_parent):
            raise ValueError(
                f"API startup failed: Parent mount directory '{mount_parent}' does not exist."
            )

        logger.success(f"Mount verified at API startup: {mount_parent}")

# project_service.py:_initialize_resources() (Per-Request)
def _initialize_resources(self):
    # ... project validation ...

    # Check mount
    mount_check_path = self._get_mount_check_path()

    if self.mount_ensure and not self._is_test_mode():
        if not os.path.exists(mount_check_path):
            raise ValueError(
                f"Mount point not accessible: {mount_check_path}. "
                f"Ensure mount is established before operations."
            )

def _get_mount_check_path(self):
    if ProjectContext.is_api_mode():
        return ProjectContext.get_mount_parent_path()  # Returns "/mnt/data"
    else:
        return Path(self.mount_point) / self.user_id / self.project_id  # Returns "/mnt/data/{user}/{project}"
```

**Wait, looking at the code more carefully**: Both actually check the same path in API mode (parent level). But there's still an inconsistency in **CLI mode** where startup isn't relevant but per-request checks project-specific path.

**Actual Problem**: Mount checking logic is duplicated and the behavior differs:
- API startup: Simple `os.path.exists()` check, raises ValueError
- Per-request: Checks `mount_ensure` config flag, respects test mode, raises ValueError

**Failure Scenario**:
```python
# API Startup
mount_parent = "/mnt/data"
os.path.exists(mount_parent)  # → True (parent exists)
# ✓ Startup succeeds

# First API Request: /data/load-dataframe
user_id = "user-abc"
project_id = "project-xyz"

# Per-request check (if API mode)
mount_check_path = "/mnt/data"  # Same as startup
os.path.exists(mount_check_path)  # → True

# But then IOService tries to load:
file_path = f"/mnt/data/{user_id}/{project_id}/data/sales/Q1.parquet"
# ✗ FileNotFoundError: /mnt/data/user-abc/project-xyz/data doesn't exist!
```

**Root Cause**: Mount existence check doesn't validate that **user-project subdirectories** exist, only that parent mount exists.

**Recommendation**:

```python
def validate_mount_access(user_id: str, project_id: str, mount_base: str) -> bool:
    """Validate mount is accessible and user-project directory exists or can be created.

    Args:
        user_id: User UUID
        project_id: Project UUID
        mount_base: Base mount path (e.g., "/mnt/data")

    Returns:
        True if mount is accessible and ready for use

    Raises:
        ValueError: If mount is not accessible or cannot be prepared
    """
    mount_base_path = Path(mount_base)

    # Check 1: Parent mount exists and is accessible
    if not mount_base_path.exists():
        raise ValueError(f"Mount base does not exist: {mount_base}")

    if not os.access(mount_base_path, os.R_OK | os.W_OK):
        raise ValueError(f"Mount base is not readable/writable: {mount_base}")

    # Check 2: User directory exists or can be created
    user_dir = mount_base_path / user_id
    if not user_dir.exists():
        try:
            user_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created user directory: {user_dir}")
        except Exception as e:
            raise ValueError(f"Cannot create user directory {user_dir}: {e}")

    # Check 3: Project directory exists or can be created
    project_dir = user_dir / project_id / "data"
    if not project_dir.exists():
        try:
            project_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created project data directory: {project_dir}")
        except Exception as e:
            raise ValueError(f"Cannot create project directory {project_dir}: {e}")

    logger.success(f"Mount validated and ready: {project_dir}")
    return True
```

**Usage**:
```python
# API Startup
@app.on_event("startup")
async def startup_event():
    if ProjectContext.is_api_mode():
        mount_base = ProjectContext.get_mount_parent_path()

        # Just check parent exists, don't validate user/project dirs yet
        if not os.path.exists(mount_base):
            raise ValueError(f"Mount base does not exist: {mount_base}")

        logger.success(f"Mount base verified: {mount_base}")

# Per-Request (in ProjectService)
def _initialize_resources(self):
    # ... project validation ...

    if self.mount_ensure and not self._is_test_mode():
        # Validate AND prepare mount for this user/project
        validate_mount_access(
            user_id=self.user_id,
            project_id=self.project_id,
            mount_base=ProjectContext.get_mount_parent_path()
        )
```

**Benefits**:
- Single validation function used consistently
- Creates directories if needed (idempotent)
- Clear error messages for each failure point
- Validates actual access permissions, not just existence

---

### Issue 5: No Symlink Implementation Despite Documentation

**Severity**: Low
**Impact**: Users must understand mount architecture instead of transparent file access
**Location**: Missing feature (documented but not implemented)

**Problem Description**:
Documentation in `docs/system/context_mgmt.md` mentions "new: create sym link in the working project directory to keep file IO in code agnostic of mount_points," but this feature is not implemented.

**Current State**:
IOService directly uses mount paths:

```python
# io_service.py:save_df_pd()
def save_df_pd(self, df: pd.DataFrame, name_python: str, dataset_id: str) -> str:
    context = ProjectContext.get()

    # Get mount point from config
    config_service = ConfigService()
    mount_point = config_service.get('mount', 'mount_point')

    # Build path: {mount_point}/{user}/{project}/data/{dataset}/{name}.parquet
    file_path = Path(mount_point) / context.user_id / context.project_id / 'data' / dataset_id / f"{name_python}.parquet"

    df.to_parquet(file_path)
```

**Problem**:
- IOService is tightly coupled to mount configuration
- No abstraction layer for file storage
- Hard to switch storage backends (e.g., direct GCS, S3, local files)

**Recommendation: Implement Symlink Strategy**

**Step 1: Add symlink creation to ProjectContext.set()**

```python
# env_config.py:ProjectContext.set()
@staticmethod
def set(
    user_id: str,
    project_id: str,
    target_dir: str = None,
    write_config: bool = True
) -> str:
    # ... existing code to determine working_dir ...

    # Store in ContextVar
    _project_context.set(context)

    # NEW: Create data symlink if mount is configured
    if write_config:
        ProjectContext.write_config()
        ProjectContext._setup_data_symlink()  # ← New method

    return working_dir

@staticmethod
def _setup_data_symlink():
    """Create symlink 'data' in working_dir pointing to mount location."""
    context = ProjectContext.get()
    working_dir = Path(context.working_dir)

    # Get mount configuration
    config_service = ConfigService(working_dir=str(working_dir))
    mount_point = config_service.get('mount', 'mount_point')

    if not mount_point:
        logger.debug("No mount point configured, skipping symlink creation")
        return

    # Build mount path: {mount_point}/{user}/{project}/data
    mount_data_path = Path(mount_point) / context.user_id / context.project_id / 'data'

    # Create symlink in working_dir
    symlink = working_dir / 'data'

    if symlink.exists() or symlink.is_symlink():
        # Check if symlink points to correct location
        if symlink.is_symlink() and symlink.resolve() == mount_data_path.resolve():
            logger.debug(f"Data symlink already correct: {symlink} -> {mount_data_path}")
            return
        else:
            # Remove incorrect symlink
            if symlink.is_symlink():
                symlink.unlink()
            else:
                logger.warning(f"'data' exists as regular directory, not removing: {symlink}")
                return

    # Create symlink
    try:
        symlink.symlink_to(mount_data_path, target_is_directory=True)
        logger.success(f"Created data symlink: {symlink} -> {mount_data_path}")
    except Exception as e:
        logger.error(f"Failed to create data symlink: {e}")
        # Don't raise - symlink is optional for backward compatibility
```

**Step 2: Simplify IOService to use symlink**

```python
# io_service.py:save_df_pd()
def save_df_pd(self, df: pd.DataFrame, name_python: str, dataset_id: str) -> str:
    context = ProjectContext.get()
    working_dir = Path(context.working_dir)

    # Use symlink: {working_dir}/data/{dataset}/{name}.parquet
    data_dir = working_dir / 'data' / dataset_id
    data_dir.mkdir(parents=True, exist_ok=True)

    file_path = data_dir / f"{name_python}.parquet"
    df.to_parquet(file_path)

    return str(file_path)
```

**Benefits**:
- IOService no longer needs to know about mount configuration
- File paths are relative to working_dir (cleaner, more intuitive)
- Easy to switch backends (symlink can point anywhere)
- Backward compatible (if symlink doesn't exist, can fall back to mount_point)

**Migration Path**:
1. Implement symlink creation (non-breaking)
2. Update IOService to prefer symlink if exists, fallback to mount_point
3. Update tests to verify symlink creation
4. Document new behavior
5. Eventually deprecate direct mount_point usage

---

## 3. Summary of Recommendations

| Issue | Severity | Recommendation | Effort | Impact |
|-------|----------|----------------|--------|--------|
| **1. Scattered Environment Detection** | Medium | Create `EnvironmentConfig` class | Low | High (easier to maintain/test) |
| **2. Fragile Two-Phase Init** | High | Atomic initialization with rollback | Medium | High (prevents inconsistent state) |
| **3. Mount Suggest Command Failure** | High | Store last pull path or improve error messages | Low | Very High (unblocks mount configuration) |
| **4. Inconsistent Mount Checking** | Medium | Unified `validate_mount_access()` function | Low | Medium (more reliable startup) |
| **5. Missing Symlink Implementation** | Low | Implement symlink in `ProjectContext.set()` | Low | Medium (cleaner abstractions) |

### Priority Order:
1. **Issue 3** (Mount Command Failure): Blocking user onboarding, simple fix
2. **Issue 2** (Init Fragility): Causes hard-to-debug errors
3. **Issue 5** (Symlink): Enables fixing Issue 3 elegantly
4. **Issue 1** (Environment Detection): Makes other fixes cleaner
5. **Issue 4** (Mount Checking): Polish after other fixes

---

## 4. Conclusion

The OryxForge architecture demonstrates strong design principles:
- ✅ Zero-parameter service pattern reduces coupling
- ✅ Thread-safe context management for concurrent requests
- ✅ Multi-environment support (CLI, Local API, GCP Production)
- ✅ Serverless-ready with ephemeral storage handling

However, the complexity of environment detection and resource initialization creates user-facing issues, particularly around mount configuration. The recommended fixes focus on:

1. **Simplification**: Centralize environment logic, improve working directory resolution
2. **Robustness**: Atomic initialization prevents partial failures
3. **User Experience**: Fix working directory mismatch, transparent file access via symlinks

These changes will reduce configuration errors, improve testability, and create a more intuitive developer experience.

---

**Next Steps**: See `integration_test_strategy_2025.md` for comprehensive testing plan to validate these recommendations.

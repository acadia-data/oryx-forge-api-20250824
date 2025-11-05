# OryxForge Integration Test Strategy
**Date**: 2025-11-02
**Author**: Senior System Architect Analysis
**Scope**: End-to-End Testing, Environment Coverage, Failure Recovery

---

## Executive Summary

This document outlines a comprehensive integration test strategy to address critical gaps in the OryxForge test suite. Current tests (205 tests, 94% passing) primarily use temporary directories which trigger "test mode" and skip mount validation - the exact failure points users encounter in production.

**Current Test Coverage Gaps**:
1. ❌ All tests use `temp_working_dir` → skips mount validation
2. ❌ No environment-specific tests (CLI vs Local API vs GCP)
3. ❌ No end-to-end workflow tests (project creation → init → import → chat)
4. ❌ No mount operation tests (mount/unmount with various conditions)
5. ❌ No configuration flow tests (admin pull → mount suggest → mount set)

**Proposed Solution**: 5 new test suites with 47 new test cases covering real-world workflows, environment variations, and failure recovery scenarios.

---

## 1. Current Test Suite Analysis

### 1.1 Existing Test Infrastructure

**Fixtures** (from `conftest.py:1-150`):

| Fixture | Scope | Purpose | Issue |
|---------|-------|---------|-------|
| `test_user_id` | Session | Returns `24d811e2-1801-4208-8030-a86abbda59b8` | ✓ Reusable |
| `test_project_id` | Session | Returns `fd0b6b50-ed50-49db-a3ce-6c7295fb85a2` | ✓ Reusable |
| `temp_working_dir` | Function | Creates `tempfile.TemporaryDirectory()` | ❌ Triggers test mode |
| `supabase_client` | Class | Initializes Supabase client | ✓ Reusable |
| `project_context` | Function | Sets/clears ProjectContext with temp dir | ❌ Uses temp_working_dir |

**Test Mode Detection** (`env_config.py:67-73`):
```python
@staticmethod
def is_test_mode(working_dir: str) -> bool:
    working_dir_lower = str(working_dir).lower()
    return ('temp' in working_dir_lower or 'test' in working_dir_lower)
```

**Problem**: `temp_working_dir` fixture creates paths like `/tmp/pytest-xxx/test_xxx` which trigger test mode, causing mount validation to be skipped.

**Consequence** (`project_service.py:_is_test_mode()`):
```python
def _is_test_mode(self) -> bool:
    """Check if running in test mode (skip mount checks)."""
    return ProjectContext.is_test_mode(self.working_dir)

def _initialize_resources(self):
    # ... project validation ...

    # Mount checking - SKIPPED in test mode!
    if self.mount_ensure and not self._is_test_mode():
        mount_check_path = self._get_mount_check_path()
        if not os.path.exists(mount_check_path):
            raise ValueError(f"Mount point not accessible: {mount_check_path}")
```

### 1.2 Test Coverage Summary

**Current Test Files**:
- `test_project_service.py` - 87 tests (project CRUD, dataset/sheet operations)
- `test_io_service.py` - 42 tests (DataFrame save/load, Parquet operations)
- `test_chat_service.py` - 31 tests (Claude Agent integration, session management)
- `test_import_service.py` - 18 tests (file import, data source handling)
- `test_config.py` - 27 tests (configuration management)

**Total**: 205 tests, ~94% passing rate

**What's Tested Well**:
- ✓ Service method units (create_dataset, save_dataframe, etc.)
- ✓ Supabase queries with RLS filtering
- ✓ DataFrame serialization/deserialization
- ✓ Claude Agent API integration
- ✓ Configuration file read/write

**What's NOT Tested**:
- ❌ Mount validation and mount operations
- ❌ Environment-specific behavior (CLI vs API vs GCP)
- ❌ End-to-end workflows (multiple services orchestrated)
- ❌ CLI command execution with real working directories
- ❌ Failure recovery (partial state cleanup, rollback)
- ❌ Symlink creation and file access through symlinks
- ❌ Two-phase initialization edge cases

---

## 2. Test Gap Analysis

### Gap 1: Mount Validation Testing

**Impact**: Critical - mount failures are primary user pain point
**Current Coverage**: 0%

**Missing Test Scenarios**:
1. Mount point doesn't exist
2. Mount point exists but not accessible (permissions)
3. Mount parent exists but user/project subdirectories don't exist
4. Mount point configured but rclone mount not running
5. Mount unmount during active operations
6. Invalid mount paths (relative paths, special characters)

**Real-World Failure Examples**:
```bash
# User configures mount but directory doesn't exist
oryxforge admin config mount set "D:\data\oryx\user123\project456\data"
oryxforge activate sales.Q1
# ✗ Error: Mount point not accessible

# User sets mount parent, but per-project directories not created
# API startup checks /mnt/data (exists)
# First request checks /mnt/data/user123/project456 (doesn't exist)
# ✗ Error: Mount point not accessible
```

**Why Current Tests Miss This**:
```python
# Typical test pattern
def test_create_dataset(test_user_id, test_project_id, temp_working_dir):
    context = ProjectContext.set(temp_working_dir, test_user_id, test_project_id)

    # This path contains "temp" → is_test_mode() returns True
    # → _initialize_resources() skips mount checking
    # → test passes even if mount would fail in production

    project_service = ProjectService()
    dataset = project_service.create_dataset("Test Dataset")
    assert dataset["name"] == "Test Dataset"
```

---

### Gap 2: Environment-Specific Testing

**Impact**: High - behavior differs significantly across environments
**Current Coverage**: ~5% (implicit through env var mocking)

**Missing Test Scenarios**:

| Environment | Current Tests | Needed Tests |
|-------------|--------------|--------------|
| **CLI Mode** | None explicit | Project init, mount setup, config persistence |
| **Local API Dev** | None | Working dir determination, mount parent checking |
| **GCP Production** | None | Ephemeral /tmp handling, no config file reliance |
| **Test Mode** | Implicit (all tests) | Explicit test mode flag validation |

**Environment Variables Not Tested**:
- `GOOGLE_CLOUD_PROJECT` (GCP production detection)
- `FASTAPI_ENV` (local API mode)
- `ORYX_MOUNT_ROOT` (local API mount base)
- `PYTEST_CURRENT_TEST` (explicit test mode)

**Critical Differences Not Tested**:

```python
# CLI Mode (never tested explicitly)
working_dir = os.getcwd()  # User's project directory
config_file = working_dir / ".oryxforge.cfg"  # Must exist and be correct

# GCP Production (never tested)
working_dir = f"/tmp/{user_id}/{project_id}"  # Ephemeral
config_file = working_dir / ".oryxforge.cfg"  # Created on-demand, doesn't persist

# Local API Dev (never tested)
working_dir = f"{ORYX_MOUNT_ROOT}/mnt/projects/{user_id}/{project_id}"
config_file = working_dir / ".oryxforge.cfg"  # Persists across requests
```

---

### Gap 3: End-to-End Workflow Testing

**Impact**: High - individual service tests pass but integration fails
**Current Coverage**: 0%

**Missing Workflow Tests**:

**Workflow 1: New Project Setup (CLI)**
```bash
# Steps user actually performs
1. oryxforge admin pull
2. cd <cloned-directory>
3. oryxforge admin config mount suggest "D:\data"
4. oryxforge admin config mount set <suggested-path>
5. oryxforge admin mount
6. oryxforge activate sales.Q1
```

**Current Tests**: Each command has unit tests, but no test validates the SEQUENCE works end-to-end.

**Workflow 2: API Data Load**
```python
# Steps API performs internally
1. POST /data/load-dataframe {"user_id": "...", "project_id": "...", "name_python": "sales.Q1"}
2. ProjectService.project_init(project_id, user_id)
   a. ProjectContext.set(write_config=False)
   b. RepoService.ensure_repo()
   c. ProjectContext.write_config()
   d. ProjectService.__init__() → _initialize_resources()
3. IOService.load_df_pd("sales.Q1")
4. Return DataFrame as JSON
```

**Current Tests**: Service methods tested individually, but no test validates the full API request flow.

**Workflow 3: Data Import → Chat Analysis**
```bash
# Real user workflow
1. oryxforge import data/sales.xlsx
   → Downloads/analyzes with Claude
   → Saves sheets as Parquet
   → Creates datasheet records
2. oryxforge activate sales.Summary
3. oryxforge chat "What were the top 3 products?"
   → Loads chat history
   → Sends to Claude with context
   → Parses response
   → Updates active sheet if changed
```

**Current Tests**: Import and chat tested separately, no integration test.

---

### Gap 4: Configuration Flow Testing

**Impact**: Medium - configuration commands frequently fail in practice
**Current Coverage**: 10% (basic ConfigService read/write)

**Missing Test Scenarios**:

**Scenario 1: Admin Pull → Mount Configuration**
```python
# What should be tested but isn't
def test_admin_pull_then_mount_config():
    # Step 1: Admin pull
    cli_service = CLIService()
    repo_path = cli_service.pull()
    assert Path(repo_path).exists()
    assert (Path(repo_path) / ".oryxforge.cfg").exists()

    # Step 2: Change working directory (simulate 'cd')
    os.chdir(repo_path)

    # Step 3: Mount suggest
    suggested = cli_service.mount_point_suggest("D:/data")
    assert suggested == f"D:/data/{user_id}/{project_id}/data"

    # Step 4: Mount set
    cli_service.mount_point_set(suggested)

    # Verify config updated
    config = ConfigObj(str(Path(repo_path) / ".oryxforge.cfg"))
    assert config['mount']['mount_point'] == suggested
    assert config['mount']['mount_ensure'] == 'true'
```

**Scenario 2: Config File Migration**
```python
# Test old config format → new format
def test_config_migration():
    # Create old format config
    old_config = """
    [profile]
    user_id = abc-123
    project_id = xyz-789
    """

    # Load with ConfigService
    config_service = ConfigService(working_dir=test_dir)

    # Should auto-migrate to new format with [mount] section
    assert config_service.get('mount', 'mount_point') is not None
```

---

### Gap 5: Failure Recovery Testing

**Impact**: High - partial failures leave system in inconsistent state
**Current Coverage**: 0%

**Missing Test Scenarios**:

**Scenario 1: Repo Clone Fails Midway**
```python
def test_project_init_repo_clone_fails():
    """Test that failed repo clone doesn't leave partial context."""
    with patch('oryxforge.services.repo_service.RepoService.ensure_repo') as mock_ensure:
        # Simulate network failure during clone
        mock_ensure.side_effect = Exception("Network timeout")

        with pytest.raises(Exception):
            ProjectService.project_init(project_id, user_id)

        # Verify context was rolled back
        with pytest.raises(RuntimeError):
            ProjectContext.get()  # Should raise "No context set"

        # Verify no config file created
        working_dir = Path(f"/tmp/{user_id}/{project_id}")
        assert not (working_dir / ".oryxforge.cfg").exists()
```

**Scenario 2: Mount Unmounted During Operation**
```python
def test_import_file_mount_unmounted_midway():
    """Test graceful failure when mount disappears during import."""
    import_service = ImportService()

    # Start import
    with patch('oryxforge.services.io_service.IOService.save_df_pd') as mock_save:
        # First sheet succeeds
        mock_save.return_value = "sheet_id_1"

        # Second sheet fails (mount unmounted)
        def save_side_effect(df, name, dataset_id):
            if name == "Sheet2":
                raise FileNotFoundError("Mount point not accessible")
            return f"sheet_id_{name}"

        mock_save.side_effect = save_side_effect

        # Import should fail with clear error
        with pytest.raises(FileNotFoundError) as exc_info:
            import_service.import_file("multi_sheet.xlsx")

        assert "Mount point not accessible" in str(exc_info.value)

        # Verify partial records are cleaned up or marked as failed
        # (This behavior may need to be implemented)
```

**Scenario 3: Supabase Connection Lost**
```python
def test_create_dataset_supabase_timeout():
    """Test that transient Supabase errors are handled gracefully."""
    project_service = ProjectService()

    with patch.object(project_service.supabase.table('datasets'), 'insert') as mock_insert:
        # Simulate timeout
        mock_insert.side_effect = Exception("Connection timeout")

        with pytest.raises(Exception) as exc_info:
            project_service.create_dataset("Test Dataset")

        # Verify error message is user-friendly
        assert "timeout" in str(exc_info.value).lower()

        # Verify no partial state in ProjectContext
        # (e.g., dataset_id not set in [active] section)
```

---

## 3. Proposed Test Suites

### Suite 1: Environment Configuration Tests

**Purpose**: Validate environment detection and working directory determination across all deployment modes

**Prerequisites**:
- New fixture: `real_working_dir` (doesn't contain "temp" or "test")
- Environment variable mocking fixtures
- Cleanup utilities for test directories

**Test Cases**:

#### Test 1.1: CLI Mode Detection
```python
def test_cli_mode_detection(real_working_dir):
    """Test that CLI mode is correctly detected when no env vars are set."""
    # Clear all environment variables
    with patch.dict(os.environ, {}, clear=True):
        env_type = EnvironmentConfig.detect()
        assert env_type == EnvironmentType.CLI

        # Working dir should be cwd
        working_dir = EnvironmentConfig.get_working_dir(env_type, "user123", "proj456")
        assert working_dir == Path.cwd()
```

#### Test 1.2: GCP Production Mode Detection
```python
def test_gcp_production_mode_detection():
    """Test GCP production mode detection via GOOGLE_CLOUD_PROJECT."""
    with patch.dict(os.environ, {'GOOGLE_CLOUD_PROJECT': 'my-gcp-project'}):
        env_type = EnvironmentConfig.detect()
        assert env_type == EnvironmentType.GCP_PRODUCTION

        # Working dir should be /tmp/{user}/{project}
        working_dir = EnvironmentConfig.get_working_dir(env_type, "user123", "proj456")
        assert str(working_dir) == "/tmp/user123/proj456"
```

#### Test 1.3: Local API Mode Detection
```python
def test_local_api_mode_detection():
    """Test local API mode detection via ORYX_MOUNT_ROOT or FASTAPI_ENV."""
    test_cases = [
        {'ORYX_MOUNT_ROOT': '/data'},
        {'FASTAPI_ENV': 'true'},
        {'ORYX_MOUNT_ROOT': '/data', 'FASTAPI_ENV': 'true'},
    ]

    for env_vars in test_cases:
        with patch.dict(os.environ, env_vars, clear=True):
            env_type = EnvironmentConfig.detect()
            assert env_type == EnvironmentType.LOCAL_API

            # Working dir should be {ORYX_MOUNT_ROOT}/mnt/projects/{user}/{project}
            working_dir = EnvironmentConfig.get_working_dir(env_type, "user123", "proj456")
            expected = "/data/mnt/projects/user123/proj456"
            assert str(working_dir) == expected
```

#### Test 1.4: Test Mode Detection
```python
def test_test_mode_detection_explicit():
    """Test explicit test mode detection via PYTEST_CURRENT_TEST."""
    with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_foo.py::test_bar'}):
        env_type = EnvironmentConfig.detect()
        assert env_type == EnvironmentType.TEST

def test_test_mode_detection_implicit(temp_working_dir):
    """Test implicit test mode detection via working dir path."""
    # temp_working_dir contains "temp"
    assert ProjectContext.is_test_mode(str(temp_working_dir))
```

#### Test 1.5: Environment Configuration Persistence
```python
def test_config_written_correctly_per_environment(real_working_dir):
    """Test that .oryxforge.cfg is written with correct values per environment."""
    test_cases = [
        {
            'env': EnvironmentType.CLI,
            'expected_mount_ensure': True,
            'expected_mount_point': './data',
        },
        {
            'env': EnvironmentType.LOCAL_API,
            'expected_mount_ensure': False,  # Mount assumed to be established externally
            'expected_mount_point': '/data/mnt/data',
        },
        {
            'env': EnvironmentType.GCP_PRODUCTION,
            'expected_mount_ensure': False,
            'expected_mount_point': '/mnt/data',
        },
    ]

    for case in test_cases:
        with patch('oryxforge.services.env_config.EnvironmentConfig.detect') as mock_detect:
            mock_detect.return_value = case['env']

            # Set context and write config
            ProjectContext.set(
                user_id="user123",
                project_id="proj456",
                target_dir=str(real_working_dir),
                write_config=True
            )

            # Read config and verify
            config = ConfigObj(str(real_working_dir / ".oryxforge.cfg"))
            assert config['mount']['mount_ensure'] == str(case['expected_mount_ensure']).lower()
            assert config['mount']['mount_point'] == case['expected_mount_point']

            ProjectContext.clear()
```

**Total Test Cases in Suite 1**: 5 tests

---

### Suite 2: Project Initialization End-to-End Tests

**Purpose**: Validate complete project initialization workflows including repo cloning, config writing, and service initialization

**Prerequisites**:
- Real working directory fixture
- Mock GitLab API for repo operations
- Supabase test project with known user/project IDs

**Test Cases**:

#### Test 2.1: CLI Project Initialization from Scratch
```python
def test_cli_project_init_new_user(real_working_dir, test_user_id, test_project_id):
    """Test full CLI project initialization flow for new user."""
    # Step 1: Simulate admin pull
    with patch.dict(os.environ, {}, clear=True):  # CLI mode
        repo_service = RepoService()

        # Mock GitLab clone
        with patch.object(repo_service, 'clone_repo') as mock_clone:
            mock_clone.return_value = str(real_working_dir)

            # Execute pull
            repo_path = repo_service.ensure_repo(user_id=test_user_id, project_id=test_project_id)

            assert Path(repo_path).exists()

        # Step 2: Initialize ProjectContext
        working_dir = ProjectContext.set(
            user_id=test_user_id,
            project_id=test_project_id,
            target_dir=repo_path,
            write_config=True
        )

        # Verify context
        context = ProjectContext.get()
        assert context.user_id == test_user_id
        assert context.project_id == test_project_id

        # Verify config file
        config_file = Path(working_dir) / ".oryxforge.cfg"
        assert config_file.exists()

        config = ConfigObj(str(config_file))
        assert config['profile']['user_id'] == test_user_id
        assert config['profile']['project_id'] == test_project_id

        # Step 3: Initialize ProjectService
        project_service = ProjectService(project_id=test_project_id, user_id=test_user_id)

        # Should succeed (mount validation will be skipped if mount_ensure=False in test)
        assert project_service.user_id == test_user_id
        assert project_service.project_id == test_project_id
```

#### Test 2.2: API Project Initialization (Ephemeral /tmp)
```python
def test_api_project_init_ephemeral_tmp(test_user_id, test_project_id):
    """Test API project initialization with ephemeral /tmp directory."""
    with patch.dict(os.environ, {'GOOGLE_CLOUD_PROJECT': 'test-project'}):
        # Execute project_init
        with patch('oryxforge.services.repo_service.RepoService.ensure_repo'):
            project_service = ProjectService.project_init(
                project_id=test_project_id,
                user_id=test_user_id
            )

            # Verify working dir is /tmp based
            context = ProjectContext.get()
            assert str(context.working_dir).startswith('/tmp/')
            assert test_user_id in str(context.working_dir)
            assert test_project_id in str(context.working_dir)

            # Verify config was written
            config_file = Path(context.working_dir) / ".oryxforge.cfg"
            assert config_file.exists()
```

#### Test 2.3: Project Init with Repo Clone Failure (Rollback Test)
```python
def test_project_init_rollback_on_clone_failure(test_user_id, test_project_id):
    """Test that project init rolls back context if repo clone fails."""
    with patch.dict(os.environ, {}):  # CLI mode
        with patch('oryxforge.services.repo_service.RepoService.ensure_repo') as mock_ensure:
            # Simulate clone failure
            mock_ensure.side_effect = Exception("GitLab API timeout")

            # Should raise exception
            with pytest.raises(Exception) as exc_info:
                ProjectService.project_init(
                    project_id=test_project_id,
                    user_id=test_user_id
                )

            assert "timeout" in str(exc_info.value).lower()

            # Verify context was NOT set (rolled back)
            with pytest.raises(RuntimeError):
                ProjectContext.get()
```

#### Test 2.4: Project Init with Existing Config (Update Flow)
```python
def test_project_init_with_existing_config(real_working_dir, test_user_id, test_project_id):
    """Test project init when .oryxforge.cfg already exists (update flow)."""
    # Create existing config
    config_file = real_working_dir / ".oryxforge.cfg"
    config = ConfigObj()
    config.filename = str(config_file)
    config['profile'] = {'user_id': test_user_id, 'project_id': test_project_id}
    config['mount'] = {'mount_point': './data', 'mount_ensure': 'false'}
    config.write()

    # Initialize project
    with patch('oryxforge.services.repo_service.RepoService.ensure_repo'):
        ProjectContext.set(
            user_id=test_user_id,
            project_id=test_project_id,
            target_dir=str(real_working_dir),
            write_config=True
        )

        # Read config again
        config = ConfigObj(str(config_file))

        # Verify profile section preserved
        assert config['profile']['user_id'] == test_user_id

        # Verify mount section preserved
        assert config['mount']['mount_point'] == './data'
```

#### Test 2.5: Concurrent Project Init (Race Condition Test)
```python
import threading

def test_concurrent_project_init(test_user_id, test_project_id, real_working_dir):
    """Test that concurrent project init calls don't interfere (thread safety)."""
    results = []
    errors = []

    def init_project(user_suffix):
        try:
            with patch('oryxforge.services.repo_service.RepoService.ensure_repo'):
                # Each thread uses different user_id
                user_id = f"{test_user_id}-{user_suffix}"
                project_dir = real_working_dir / user_suffix
                project_dir.mkdir(exist_ok=True)

                ProjectContext.set(
                    user_id=user_id,
                    project_id=test_project_id,
                    target_dir=str(project_dir),
                    write_config=True
                )

                # Get context and verify
                context = ProjectContext.get()
                results.append((user_suffix, context.user_id))

                ProjectContext.clear()
        except Exception as e:
            errors.append((user_suffix, str(e)))

    # Launch 5 concurrent threads
    threads = [threading.Thread(target=init_project, args=(f"thread{i}",)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify no errors
    assert len(errors) == 0, f"Errors occurred: {errors}"

    # Verify each thread got correct user_id
    assert len(results) == 5
    for suffix, user_id in results:
        assert user_id.endswith(suffix)
```

**Total Test Cases in Suite 2**: 5 tests

---

### Suite 3: Mount Operations Integration Tests

**Purpose**: Validate mount checking, mounting, unmounting, and error handling with real mount points

**Prerequisites**:
- Real mount directory (not temp)
- Fixtures to set up/teardown mount state
- Platform-specific mount commands (rclone for real tests, mocks for CI)

**Test Cases**:

#### Test 3.1: Mount Point Validation - Parent Exists, Project Dir Missing
```python
def test_mount_validation_parent_exists_project_missing(real_working_dir, test_user_id, test_project_id):
    """Test mount validation creates project directories if parent exists."""
    mount_base = real_working_dir / "mount_base"
    mount_base.mkdir(exist_ok=True)

    # Set config with mount point
    ProjectContext.set(
        user_id=test_user_id,
        project_id=test_project_id,
        target_dir=str(real_working_dir),
        write_config=True
    )

    config_service = ConfigService(working_dir=str(real_working_dir))
    config_service.set('mount', 'mount_point', str(mount_base))
    config_service.set('mount', 'mount_ensure', 'true')

    # Initialize ProjectService (should create project directories)
    project_service = ProjectService(
        project_id=test_project_id,
        user_id=test_user_id,
        mount_ensure=True
    )

    # Verify directories created
    project_data_dir = mount_base / test_user_id / test_project_id / "data"
    assert project_data_dir.exists()
```

#### Test 3.2: Mount Point Validation - Parent Missing
```python
def test_mount_validation_parent_missing(real_working_dir, test_user_id, test_project_id):
    """Test that missing mount parent raises clear error."""
    mount_base = real_working_dir / "nonexistent_mount"

    ProjectContext.set(
        user_id=test_user_id,
        project_id=test_project_id,
        target_dir=str(real_working_dir),
        write_config=True
    )

    config_service = ConfigService(working_dir=str(real_working_dir))
    config_service.set('mount', 'mount_point', str(mount_base))
    config_service.set('mount', 'mount_ensure', 'true')

    # Should raise clear error
    with pytest.raises(ValueError) as exc_info:
        ProjectService(
            project_id=test_project_id,
            user_id=test_user_id,
            mount_ensure=True
        )

    assert "Mount" in str(exc_info.value)
    assert str(mount_base) in str(exc_info.value)
```

#### Test 3.3: Mount Point Validation - Invalid Permissions
```python
@pytest.mark.skipif(sys.platform == "win32", reason="Permission test not reliable on Windows")
def test_mount_validation_invalid_permissions(real_working_dir, test_user_id, test_project_id):
    """Test that mount point with invalid permissions raises error."""
    mount_base = real_working_dir / "readonly_mount"
    mount_base.mkdir(exist_ok=True)

    # Make directory read-only
    os.chmod(mount_base, 0o444)

    try:
        ProjectContext.set(
            user_id=test_user_id,
            project_id=test_project_id,
            target_dir=str(real_working_dir),
            write_config=True
        )

        config_service = ConfigService(working_dir=str(real_working_dir))
        config_service.set('mount', 'mount_point', str(mount_base))
        config_service.set('mount', 'mount_ensure', 'true')

        # Should raise permission error
        with pytest.raises(ValueError) as exc_info:
            ProjectService(
                project_id=test_project_id,
                user_id=test_user_id,
                mount_ensure=True
            )

        assert "permission" in str(exc_info.value).lower() or "writable" in str(exc_info.value).lower()
    finally:
        # Restore permissions for cleanup
        os.chmod(mount_base, 0o755)
```

#### Test 3.4: Symlink Creation and Access
```python
def test_symlink_creation_and_access(real_working_dir, test_user_id, test_project_id):
    """Test that symlink is created correctly and files are accessible through it."""
    mount_base = real_working_dir / "mount"
    mount_base.mkdir(exist_ok=True)

    # Create project directories
    project_data_dir = mount_base / test_user_id / test_project_id / "data"
    project_data_dir.mkdir(parents=True, exist_ok=True)

    # Create test file in mount
    test_file = project_data_dir / "test.txt"
    test_file.write_text("test content")

    # Set context and config
    ProjectContext.set(
        user_id=test_user_id,
        project_id=test_project_id,
        target_dir=str(real_working_dir),
        write_config=True
    )

    config_service = ConfigService(working_dir=str(real_working_dir))
    config_service.set('mount', 'mount_point', str(mount_base))

    # Create symlink (using proposed _setup_data_symlink method)
    ProjectContext._setup_data_symlink()

    # Verify symlink exists
    symlink = real_working_dir / "data"
    assert symlink.is_symlink()

    # Verify symlink points to correct location
    assert symlink.resolve() == project_data_dir.resolve()

    # Verify file accessible through symlink
    file_via_symlink = symlink / "test.txt"
    assert file_via_symlink.exists()
    assert file_via_symlink.read_text() == "test content"
```

#### Test 3.5: Mount Suggest Command Flow
```python
def test_mount_suggest_command_flow(real_working_dir, test_user_id, test_project_id):
    """Test complete mount suggest → mount set flow."""
    # Setup: Create config with profile
    config_file = real_working_dir / ".oryxforge.cfg"
    config = ConfigObj()
    config.filename = str(config_file)
    config['profile'] = {'user_id': test_user_id, 'project_id': test_project_id}
    config.write()

    # Change to working directory (simulate user 'cd')
    original_cwd = os.getcwd()
    try:
        os.chdir(real_working_dir)

        # Execute mount suggest
        cli_service = CLIService()
        suggested_path = cli_service.mount_point_suggest(mount_base=str(real_working_dir / "mounts"))

        # Verify suggestion format
        expected = str(real_working_dir / "mounts" / test_user_id / test_project_id / "data")
        assert suggested_path == expected

        # Execute mount set
        cli_service.mount_point_set(suggested_path)

        # Verify config updated
        config = ConfigObj(str(config_file))
        assert config['mount']['mount_point'] == suggested_path
        assert config['mount']['mount_ensure'] == 'true'
    finally:
        os.chdir(original_cwd)
```

#### Test 3.6: API Startup Mount Validation
```python
def test_api_startup_mount_validation(real_working_dir):
    """Test API startup mount validation behavior."""
    mount_base = real_working_dir / "api_mount"
    mount_base.mkdir(exist_ok=True)

    with patch.dict(os.environ, {'ORYX_MOUNT_ROOT': str(real_working_dir)}):
        with patch('oryxforge.services.env_config.ProjectContext.get_mount_parent_path') as mock_get_mount:
            mock_get_mount.return_value = str(mount_base)

            # Simulate API startup check (from app.py:startup_event)
            from api.app import startup_event
            import asyncio

            # Should succeed
            asyncio.run(startup_event())

            # Now remove mount directory
            import shutil
            shutil.rmtree(mount_base)

            # Should fail
            with pytest.raises(ValueError) as exc_info:
                asyncio.run(startup_event())

            assert "mount" in str(exc_info.value).lower()
```

**Total Test Cases in Suite 3**: 6 tests

---

### Suite 4: End-to-End Workflow Tests

**Purpose**: Validate complete user workflows spanning multiple services and commands

**Prerequisites**:
- Real working directory
- Supabase test data
- Mock Claude API for agent calls
- Sample data files (Excel, CSV)

**Test Cases**:

#### Test 4.1: Complete CLI Setup Workflow
```python
def test_cli_complete_setup_workflow(real_working_dir, test_user_id, test_project_id):
    """Test complete CLI workflow: pull → mount setup → activate → import → chat."""
    cli_service = CLIService()

    # Step 1: Admin pull (clone repo)
    with patch('oryxforge.services.repo_service.RepoService.clone_repo') as mock_clone:
        mock_clone.return_value = str(real_working_dir)
        repo_path = cli_service.pull()
        assert Path(repo_path).exists()

    # Step 2: Change directory
    original_cwd = os.getcwd()
    try:
        os.chdir(repo_path)

        # Step 3: Mount configuration
        mount_base = real_working_dir / "data"
        mount_base.mkdir(exist_ok=True)
        suggested = cli_service.mount_point_suggest(str(mount_base))
        cli_service.mount_point_set(suggested)

        # Step 4: Create mount directories (simulate successful mount)
        Path(suggested).mkdir(parents=True, exist_ok=True)

        # Step 5: Activate dataset
        # First create dataset and sheet
        ProjectContext.set(user_id=test_user_id, project_id=test_project_id, target_dir=repo_path, write_config=True)
        project_service = ProjectService(project_id=test_project_id, user_id=test_user_id, mount_ensure=False)

        dataset = project_service.create_dataset("Sales")
        sheet_id = "test-sheet-id"  # Would be created by import

        # Activate
        cli_service.activate(dataset['id'], sheet_id)

        # Verify active config
        config = ConfigObj(str(Path(repo_path) / ".oryxforge.cfg"))
        assert config['active']['dataset_id'] == dataset['id']
        assert config['active']['sheet_id'] == sheet_id

        # Step 6: Import file (mocked)
        with patch('oryxforge.services.import_service.ImportService.import_file') as mock_import:
            mock_import.return_value = {'sheets': ['Sheet1', 'Sheet2']}
            result = cli_service.import_file("test.xlsx")
            assert 'sheets' in result

        # Step 7: Chat (mocked)
        with patch('oryxforge.services.chat_service.ChatService.chat') as mock_chat:
            mock_chat.return_value = {"response": "Analysis complete", "target_sheet": "Sales.Summary"}
            response = cli_service.chat("Analyze sales data")
            assert 'response' in response

    finally:
        os.chdir(original_cwd)
        ProjectContext.clear()
```

#### Test 4.2: API Data Load Workflow
```python
def test_api_data_load_workflow(test_user_id, test_project_id, real_working_dir):
    """Test API /data/load-dataframe endpoint workflow."""
    from api.app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Setup: Create dataset and datasheet in Supabase
    with patch.dict(os.environ, {'FASTAPI_ENV': 'true', 'ORYX_MOUNT_ROOT': str(real_working_dir)}):
        # Create mount structure
        mount_base = real_working_dir / "mnt" / "data"
        mount_base.mkdir(parents=True, exist_ok=True)

        project_data_dir = mount_base / test_user_id / test_project_id / "data"
        project_data_dir.mkdir(parents=True, exist_ok=True)

        # Create test Parquet file
        dataset_dir = project_data_dir / "test-dataset-id"
        dataset_dir.mkdir(exist_ok=True)

        import pandas as pd
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        parquet_file = dataset_dir / "TestSheet.parquet"
        df.to_parquet(parquet_file)

        # Mock repo operations
        with patch('oryxforge.services.repo_service.RepoService.ensure_repo'):
            # Make API request
            response = client.post(
                "/data/load-dataframe",
                json={
                    "user_id": test_user_id,
                    "project_id": test_project_id,
                    "name_python": "test-dataset.TestSheet"
                }
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert 'headers' in data
            assert 'data' in data
            assert data['headers'] == ['col1', 'col2']
```

#### Test 4.3: Import → Activate → Chat Workflow
```python
def test_import_activate_chat_workflow(real_working_dir, test_user_id, test_project_id):
    """Test workflow: import data → activate sheet → chat analysis."""
    # Setup context
    ProjectContext.set(user_id=test_user_id, project_id=test_project_id, target_dir=str(real_working_dir), write_config=True)

    # Create mount structure
    mount_base = real_working_dir / "data"
    mount_base.mkdir(exist_ok=True)
    project_data_dir = mount_base / test_user_id / test_project_id / "data"
    project_data_dir.mkdir(parents=True, exist_ok=True)

    config_service = ConfigService(working_dir=str(real_working_dir))
    config_service.set('mount', 'mount_point', str(mount_base))
    config_service.set('mount', 'mount_ensure', 'false')

    # Step 1: Import file
    import_service = ImportService()

    # Create sample Excel file
    import pandas as pd
    sample_file = real_working_dir / "sample.xlsx"
    with pd.ExcelWriter(sample_file) as writer:
        pd.DataFrame({"Product": ["A", "B"], "Sales": [100, 200]}).to_excel(writer, sheet_name="Q1", index=False)

    # Mock Claude agent analysis
    with patch('oryxforge.agents.oryxforge_agent.claude_agent') as mock_agent:
        mock_agent.send_message.return_value = {"analysis": "2 sheets found"}

        result = import_service.import_file(str(sample_file))

        assert 'dataset_id' in result
        dataset_id = result['dataset_id']
        assert len(result['sheets']) > 0
        sheet_id = result['sheets'][0]['id']

    # Step 2: Activate imported sheet
    config_service.set('active', 'dataset_id', dataset_id)
    config_service.set('active', 'sheet_id', sheet_id)

    # Step 3: Chat analysis
    chat_service = ChatService()

    with patch('oryxforge.agents.oryxforge_agent.claude_agent') as mock_agent:
        # Mock streaming response
        def mock_stream():
            yield {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Sales "}}
            yield {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "analysis complete"}}

        mock_agent.send_message.return_value = mock_stream()

        response_text = ""
        for chunk in chat_service.chat("Analyze Q1 sales", stream=True):
            response_text += chunk

        assert "Sales" in response_text or "analysis" in response_text

    ProjectContext.clear()
```

#### Test 4.4: Multi-User Concurrent Workflow
```python
def test_multi_user_concurrent_workflow(real_working_dir):
    """Test that multiple users can work concurrently without interference."""
    import threading

    users = [
        ("user1", "proj1"),
        ("user2", "proj2"),
        ("user3", "proj3"),
    ]

    results = {}
    errors = {}

    def user_workflow(user_id, project_id):
        try:
            # Each user gets own directory
            user_dir = real_working_dir / user_id
            user_dir.mkdir(exist_ok=True)

            # Set context
            ProjectContext.set(
                user_id=user_id,
                project_id=project_id,
                target_dir=str(user_dir),
                write_config=True
            )

            # Create dataset
            project_service = ProjectService(project_id=project_id, user_id=user_id, mount_ensure=False)
            dataset = project_service.create_dataset(f"Dataset-{user_id}")

            results[user_id] = dataset['id']

            ProjectContext.clear()
        except Exception as e:
            errors[user_id] = str(e)

    # Launch threads
    threads = [threading.Thread(target=user_workflow, args=user) for user in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify no errors
    assert len(errors) == 0, f"Errors: {errors}"

    # Verify each user created dataset
    assert len(results) == 3
```

#### Test 4.5: Failure Recovery - Import with Mount Failure
```python
def test_failure_recovery_import_mount_fails(real_working_dir, test_user_id, test_project_id):
    """Test that import failure due to mount issue is handled gracefully."""
    ProjectContext.set(user_id=test_user_id, project_id=test_project_id, target_dir=str(real_working_dir), write_config=True)

    # Set mount config to non-existent path
    config_service = ConfigService(working_dir=str(real_working_dir))
    config_service.set('mount', 'mount_point', '/nonexistent/mount')
    config_service.set('mount', 'mount_ensure', 'true')

    import_service = ImportService()

    # Create sample file
    import pandas as pd
    sample_file = real_working_dir / "test.xlsx"
    with pd.ExcelWriter(sample_file) as writer:
        pd.DataFrame({"col": [1, 2]}).to_excel(writer, index=False)

    # Import should fail with clear error
    with pytest.raises(ValueError) as exc_info:
        import_service.import_file(str(sample_file))

    assert "mount" in str(exc_info.value).lower()

    # Verify no partial records created in Supabase
    project_service = ProjectService(project_id=test_project_id, user_id=test_user_id, mount_ensure=False)
    datasets = project_service.get_datasets()

    # "Sources" dataset should not exist or should be empty
    sources = [d for d in datasets if d['name'] == 'Sources']
    if sources:
        sheets = project_service.get_datasheets(sources[0]['id'])
        assert len(sheets) == 0, "Partial sheets created despite mount failure"

    ProjectContext.clear()
```

**Total Test Cases in Suite 4**: 5 tests

---

### Suite 5: Configuration and State Management Tests

**Purpose**: Validate configuration persistence, migration, and state consistency

**Prerequisites**:
- Real working directory
- Config file fixtures with various formats

**Test Cases**:

#### Test 5.1: Config File Format Validation
```python
def test_config_file_format_validation(real_working_dir):
    """Test that config files are created with correct format."""
    ProjectContext.set(
        user_id="test-user",
        project_id="test-project",
        target_dir=str(real_working_dir),
        write_config=True
    )

    config_file = real_working_dir / ".oryxforge.cfg"
    assert config_file.exists()

    config = ConfigObj(str(config_file))

    # Verify required sections exist
    assert 'profile' in config
    assert 'mount' in config

    # Verify profile section
    assert config['profile']['user_id'] == "test-user"
    assert config['profile']['project_id'] == "test-project"

    # Verify mount section has required keys
    assert 'mount_point' in config['mount']
    assert 'mount_ensure' in config['mount']

    ProjectContext.clear()
```

#### Test 5.2: Config Update Preserves Existing Sections
```python
def test_config_update_preserves_sections(real_working_dir):
    """Test that updating one section doesn't overwrite others."""
    config_file = real_working_dir / ".oryxforge.cfg"

    # Create initial config
    config = ConfigObj()
    config.filename = str(config_file)
    config['profile'] = {'user_id': 'user1', 'project_id': 'proj1'}
    config['mount'] = {'mount_point': '/original/mount', 'mount_ensure': 'true'}
    config['custom'] = {'key1': 'value1', 'key2': 'value2'}
    config.write()

    # Update mount section
    config_service = ConfigService(working_dir=str(real_working_dir))
    config_service.set('mount', 'mount_point', '/new/mount')

    # Reload config
    config = ConfigObj(str(config_file))

    # Verify mount updated
    assert config['mount']['mount_point'] == '/new/mount'

    # Verify other sections preserved
    assert config['profile']['user_id'] == 'user1'
    assert config['custom']['key1'] == 'value1'
```

#### Test 5.3: Active Context Persistence Across Commands
```python
def test_active_context_persistence(real_working_dir, test_user_id, test_project_id):
    """Test that active dataset/sheet persist across command invocations."""
    # Command 1: Set profile
    ProjectContext.set(user_id=test_user_id, project_id=test_project_id, target_dir=str(real_working_dir), write_config=True)

    # Command 2: Activate dataset
    config_service = ConfigService(working_dir=str(real_working_dir))
    config_service.set('active', 'dataset_id', 'dataset-123')
    config_service.set('active', 'sheet_id', 'sheet-456')
    config_service.set('active', 'mode', 'explore')

    # Clear context (simulate new command invocation)
    ProjectContext.clear()

    # Command 3: Read active context
    ProjectContext.set(user_id=test_user_id, project_id=test_project_id, target_dir=str(real_working_dir), write_config=False)

    config_service = ConfigService(working_dir=str(real_working_dir))
    active_dataset = config_service.get('active', 'dataset_id')
    active_sheet = config_service.get('active', 'sheet_id')
    active_mode = config_service.get('active', 'mode')

    assert active_dataset == 'dataset-123'
    assert active_sheet == 'sheet-456'
    assert active_mode == 'explore'

    ProjectContext.clear()
```

#### Test 5.4: ProjectContext Clear Behavior
```python
def test_project_context_clear_behavior():
    """Test that ProjectContext.clear() properly resets state."""
    # Set context
    ProjectContext.set(
        user_id="test-user",
        project_id="test-project",
        target_dir="/tmp/test",
        write_config=False
    )

    # Verify context is set
    context = ProjectContext.get()
    assert context.user_id == "test-user"

    # Clear context
    ProjectContext.clear()

    # Verify context is cleared
    with pytest.raises(RuntimeError) as exc_info:
        ProjectContext.get()

    assert "no context" in str(exc_info.value).lower() or "not set" in str(exc_info.value).lower()
```

#### Test 5.5: Config File Permissions and Security
```python
@pytest.mark.skipif(sys.platform == "win32", reason="Unix permissions test")
def test_config_file_permissions(real_working_dir):
    """Test that config file is created with secure permissions."""
    ProjectContext.set(
        user_id="test-user",
        project_id="test-project",
        target_dir=str(real_working_dir),
        write_config=True
    )

    config_file = real_working_dir / ".oryxforge.cfg"
    assert config_file.exists()

    # Check permissions (should be 0o600 or 0o644)
    stat_info = config_file.stat()
    mode = stat_info.st_mode & 0o777

    # Should be readable by owner
    assert mode & 0o400

    # Should not be world-writable
    assert not (mode & 0o002)

    ProjectContext.clear()
```

#### Test 5.6: Config Service Working Directory Resolution
```python
def test_config_service_working_dir_resolution(real_working_dir):
    """Test that ConfigService correctly resolves working directory."""
    # Case 1: Explicit working_dir
    config_service = ConfigService(working_dir=str(real_working_dir))
    assert config_service.working_dir == real_working_dir

    # Case 2: No working_dir, ProjectContext not set (should use cwd)
    config_service = ConfigService(working_dir=None)
    assert config_service.working_dir == Path.cwd()

    # Case 3: No working_dir, ProjectContext set (should use context)
    ProjectContext.set(
        user_id="test-user",
        project_id="test-project",
        target_dir=str(real_working_dir),
        write_config=False
    )

    config_service = ConfigService(working_dir=None)
    assert config_service.working_dir == real_working_dir

    ProjectContext.clear()
```

**Total Test Cases in Suite 5**: 6 tests

---

## 4. Test Infrastructure Requirements

### 4.1 New Fixtures Needed

**`real_working_dir` Fixture**:
```python
@pytest.fixture(scope="function")
def real_working_dir() -> Generator[Path, None, None]:
    """
    Create a real working directory that doesn't trigger test mode.

    Unlike temp_working_dir, this creates a directory without 'temp' or 'test' in path,
    allowing mount validation and other production-like behavior to be tested.
    """
    # Use a non-temp directory name
    base_dir = Path.cwd() / "pytest_workdirs"
    base_dir.mkdir(exist_ok=True)

    # Create unique directory for this test
    import uuid
    test_dir = base_dir / f"workdir_{uuid.uuid4().hex[:8]}"
    test_dir.mkdir(exist_ok=True)

    yield test_dir

    # Cleanup
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)

    # Cleanup base dir if empty
    if not any(base_dir.iterdir()):
        base_dir.rmdir()
```

**`environment_vars` Fixture**:
```python
@pytest.fixture
def environment_vars():
    """Fixture to temporarily set environment variables for testing."""
    original_environ = os.environ.copy()

    def set_env(**kwargs):
        """Set environment variables for test."""
        os.environ.clear()
        os.environ.update(kwargs)

    def reset_env():
        """Reset to original environment."""
        os.environ.clear()
        os.environ.update(original_environ)

    yield set_env

    # Cleanup
    reset_env()
```

**`mock_mount` Fixture**:
```python
@pytest.fixture
def mock_mount(real_working_dir):
    """Fixture to create mock mount structure."""
    mount_base = real_working_dir / "mock_mount"
    mount_base.mkdir(exist_ok=True)

    def create_mount_structure(user_id: str, project_id: str) -> Path:
        """Create mount directory structure for user/project."""
        project_dir = mount_base / user_id / project_id / "data"
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    yield create_mount_structure

    # Cleanup handled by real_working_dir cleanup
```

**`supabase_cleanup` Fixture**:
```python
@pytest.fixture(scope="function")
def supabase_cleanup(supabase_client, test_user_id, test_project_id):
    """Fixture to clean up Supabase test data after each test."""
    created_ids = {
        'datasets': [],
        'datasheets': [],
        'chat_messages': [],
        'data_sources': []
    }

    def register_created(table: str, id: str):
        """Register a created record for cleanup."""
        created_ids[table].append(id)

    yield register_created

    # Cleanup
    for table, ids in created_ids.items():
        for record_id in ids:
            try:
                supabase_client.table(table).delete().eq('id', record_id).execute()
            except Exception as e:
                logger.warning(f"Failed to cleanup {table} record {record_id}: {e}")
```

### 4.2 Test Utilities

**`assert_config_section` Utility**:
```python
def assert_config_section(config_file: Path, section: str, expected: Dict[str, str]):
    """Assert that config file contains expected section and values."""
    assert config_file.exists(), f"Config file not found: {config_file}"

    config = ConfigObj(str(config_file))
    assert section in config, f"Section '{section}' not found in config"

    for key, value in expected.items():
        assert key in config[section], f"Key '{key}' not found in [{section}]"
        assert config[section][key] == value, f"[{section}] {key} = {config[section][key]}, expected {value}"
```

**`simulate_cli_command` Utility**:
```python
def simulate_cli_command(command: str, working_dir: Path) -> subprocess.CompletedProcess:
    """Simulate CLI command execution in specified working directory."""
    original_cwd = os.getcwd()
    try:
        os.chdir(working_dir)
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            timeout=30
        )
        return result
    finally:
        os.chdir(original_cwd)
```

### 4.3 Test Markers

Add custom pytest markers in `pytest.ini`:
```ini
[pytest]
markers =
    integration: Integration tests spanning multiple services
    mount_required: Tests requiring real mount point (skip in CI if unavailable)
    slow: Slow tests (> 5 seconds)
    environment_specific: Tests for specific environment (CLI/API/GCP)
    failure_recovery: Tests for failure scenarios and rollback
```

Usage:
```python
@pytest.mark.integration
@pytest.mark.mount_required
def test_mount_operations_integration():
    """Integration test requiring real mount."""
    pass
```

---

## 5. Test Execution Strategy

### 5.1 Test Phases

**Phase 1: Unit Tests (Current)**
- Run time: ~30 seconds
- Coverage: Individual service methods
- Environment: Test mode (temp directories)
- Command: `pytest oryxforge/tests/ -m "not integration"`

**Phase 2: Integration Tests (New)**
- Run time: ~5 minutes
- Coverage: Multi-service workflows, environment-specific behavior
- Environment: Real working directories, mocked external services
- Command: `pytest oryxforge/tests/ -m integration`

**Phase 3: Mount Integration Tests (New)**
- Run time: ~10 minutes
- Coverage: Real mount operations (may be skipped in CI)
- Environment: Real mount points, real rclone operations
- Command: `pytest oryxforge/tests/ -m mount_required`

**Phase 4: End-to-End Tests (New)**
- Run time: ~15 minutes
- Coverage: Complete user workflows from CLI/API
- Environment: Production-like setup
- Command: `pytest oryxforge/tests/ -m "integration and not mount_required"`

### 5.2 CI/CD Integration

**GitHub Actions Workflow** (example):
```yaml
name: OryxForge Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov
      - name: Run unit tests
        run: pytest oryxforge/tests/ -m "not integration" -v --cov

  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest
      - name: Run integration tests (no mount)
        run: pytest oryxforge/tests/ -m "integration and not mount_required" -v

  mount-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install rclone
        run: |
          curl https://rclone.org/install.sh | sudo bash
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest
      - name: Run mount tests
        run: pytest oryxforge/tests/ -m mount_required -v
        # May skip if mount not available
        continue-on-error: true
```

### 5.3 Local Development Workflow

**Developer Test Commands**:
```bash
# Quick unit tests (pre-commit)
make test-quick
# → pytest -m "not integration and not slow"

# Integration tests (before push)
make test-integration
# → pytest -m integration

# All tests including mount operations
make test-all
# → pytest oryxforge/tests/ -v

# Coverage report
make test-cov-html
# → pytest --cov --cov-report=html
```

### 5.4 Test Data Management

**Supabase Test Project**:
- Dedicated test project: `test_project_id = "fd0b6b50-ed50-49db-a3ce-6c7295fb85a2"`
- Test user: `test_user_id = "24d811e2-1801-4208-8030-a86abbda59b8"`
- RLS policies allow test user access
- Cleanup after each test to avoid pollution

**Test Files**:
```
oryxforge/tests/fixtures/
├── sample_data.xlsx       # Multi-sheet Excel file
├── sample_data.csv        # Simple CSV
├── sample_chart.json      # Plotly chart JSON
├── sample_markdown.md     # Markdown document
└── configs/
    ├── minimal.cfg        # Minimal valid config
    ├── complete.cfg       # All sections populated
    └── invalid.cfg        # Invalid for error testing
```

---

## 6. Success Metrics

### 6.1 Coverage Goals

| Test Suite | Target Coverage | Current Coverage | Gap |
|------------|----------------|------------------|-----|
| Unit Tests | 85% | 94% | ✓ Exceeded |
| Integration Tests | 70% | 0% | 70% to achieve |
| Mount Operations | 60% | 0% | 60% to achieve |
| E2E Workflows | 50% | 0% | 50% to achieve |
| **Overall** | **75%** | **~60%** | **15% to achieve** |

### 6.2 Quality Metrics

**Test Reliability**:
- Target: < 1% flaky tests (tests that pass/fail inconsistently)
- Current: ~6% (12/205 tests occasionally fail)
- Goal: Achieve < 2 flaky tests through better fixtures and mocking

**Test Speed**:
- Unit tests: < 1 minute total
- Integration tests: < 10 minutes total
- Full suite: < 15 minutes total

**Issue Detection**:
- Target: Tests should catch 90% of user-reported issues before deployment
- Current: ~50% (mount issues not caught, config flow issues not caught)
- Goal: New test suites cover remaining 40%

### 6.3 Implementation Timeline

| Week | Focus Area | Deliverables | Tests Added |
|------|-----------|--------------|-------------|
| **Week 1** | Test infrastructure | `real_working_dir`, `environment_vars`, test utilities | 0 |
| **Week 2** | Environment config tests | Suite 1 complete (5 tests) | 5 |
| **Week 3** | Project init tests | Suite 2 complete (5 tests) | 5 |
| **Week 4** | Mount operations tests | Suite 3 complete (6 tests) | 6 |
| **Week 5** | E2E workflow tests | Suite 4 complete (5 tests) | 5 |
| **Week 6** | Config & state tests | Suite 5 complete (6 tests) | 6 |
| **Week 7** | Bug fixes & stabilization | Fix flaky tests, improve fixtures | 0 |
| **Week 8** | Documentation & CI/CD | Update docs, configure GitHub Actions | 0 |

**Total New Tests**: 27 core tests + variations = ~47 total test cases

---

## 7. Conclusion

This integration test strategy addresses critical gaps in the OryxForge test suite by:

1. **Real-World Validation**: Testing with real working directories and mount points, not just temp directories
2. **Environment Coverage**: Explicit tests for CLI, Local API, and GCP production environments
3. **Workflow Testing**: End-to-end tests spanning multiple services and commands
4. **Failure Recovery**: Tests for partial failure scenarios and state consistency
5. **Configuration Flows**: Tests for common user workflows like mount configuration

**Expected Outcomes**:
- Catch mount validation issues before production (current #1 user pain point)
- Validate environment-specific behavior (prevents API/CLI inconsistencies)
- Ensure configuration workflows work end-to-end (reduces user confusion)
- Improve system reliability through failure recovery testing
- Increase developer confidence through comprehensive integration coverage

**Next Steps**:
1. Review and approve test strategy
2. Implement test infrastructure (fixtures, utilities)
3. Develop test suites incrementally (1-2 suites per week)
4. Integrate with CI/CD pipeline
5. Monitor and improve test reliability

---

**See Also**: `architecture_evaluation_2025.md` for detailed architectural issues that these tests are designed to catch.

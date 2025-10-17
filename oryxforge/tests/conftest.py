"""Shared pytest configuration and fixtures for oryxforge tests.

This module provides common fixtures that are used across multiple test files,
reducing code duplication and ensuring consistent test setup.
"""

import sys
import pytest
import tempfile
from pathlib import Path

# Fix encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Import test configuration
from .test_config import TEST_USER_ID, TEST_PROJECT_ID


@pytest.fixture
def temp_working_dir():
    """Create temporary working directory for tests.

    This fixture creates a fresh temporary directory for each test that uses it,
    ensuring test isolation and automatic cleanup.

    Yields:
        str: Path to temporary directory
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def temp_working_dir_repo():
    """Create temporary directory with better Windows cleanup for repo tests.

    This fixture handles Windows file locking issues with git repositories
    by adding retry logic and forced garbage collection.

    Yields:
        Path: Path object to temporary directory
    """
    import shutil
    import gc
    import time

    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)

        # Force cleanup on Windows
        if sys.platform == 'win32':
            gc.collect()  # Force garbage collection to release file handles
            time.sleep(0.1)  # Brief pause for file handles to release

            # Retry cleanup if needed (Windows file locking)
            for attempt in range(3):
                try:
                    if Path(temp_dir).exists():
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    break
                except Exception:
                    if attempt < 2:  # Only sleep if we're going to retry
                        time.sleep(0.2)
                    else:
                        # On final attempt, just ignore the error
                        pass


@pytest.fixture(scope="session")
def test_user_id():
    """Get the test user ID from configuration.

    Returns:
        str: Test user UUID
    """
    return TEST_USER_ID


@pytest.fixture(scope="session")
def test_project_id():
    """Get the test project ID from configuration.

    Returns:
        str: Test project UUID
    """
    return TEST_PROJECT_ID


@pytest.fixture(scope="class")
def supabase_client():
    """Get a shared Supabase client for the test session.

    Creates a single Supabase client instance that is reused across all tests
    in the session to reduce overhead.

    Returns:
        Client: Supabase client instance
    """
    from ..services.utils import init_supabase_client
    return init_supabase_client()


@pytest.fixture(scope="class")
def test_project_id():
    """Get the test project ID from configuration (class-scoped).

    Returns:
        str: Test project UUID
    """
    return TEST_PROJECT_ID


@pytest.fixture
def setup_credentials(temp_working_dir, test_user_id, test_project_id):
    """Set up test credentials in a temporary directory.

    This fixture configures the CredentialsManager with test credentials
    in an isolated temporary directory.

    Args:
        temp_working_dir: Temporary directory fixture
        test_user_id: Test user ID fixture
        test_project_id: Test project ID fixture

    Yields:
        dict: Dictionary with user_id, project_id, and working_dir
    """
    from ..services.iam import CredentialsManager

    creds_manager = CredentialsManager(working_dir=temp_working_dir)
    creds_manager.set_profile(user_id=test_user_id, project_id=test_project_id)

    yield {
        'user_id': test_user_id,
        'project_id': test_project_id,
        'working_dir': temp_working_dir,
        'creds_manager': creds_manager
    }


@pytest.fixture
def project_context(test_user_id, test_project_id, temp_working_dir):
    """Set up and tear down ProjectContext for tests.

    This fixture configures the global ProjectContext with test values
    and ensures it's properly cleaned up after the test.

    Args:
        test_user_id: Test user ID fixture
        test_project_id: Test project ID fixture
        temp_working_dir: Temporary directory fixture

    Yields:
        dict: Dictionary with user_id, project_id, and working_dir
    """
    from ..services.env_config import ProjectContext

    ProjectContext.set(
        user_id=test_user_id,
        project_id=test_project_id,
        working_dir=temp_working_dir
    )

    yield {
        'user_id': test_user_id,
        'project_id': test_project_id,
        'working_dir': temp_working_dir
    }

    # Cleanup
    ProjectContext.clear()


# Pytest configuration hooks
def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_data: mark test as requiring test data in database"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their characteristics.

    This hook automatically applies markers to tests based on their location
    and naming patterns, reducing the need for manual marker decoration.
    """
    for item in items:
        # Auto-mark integration tests
        if 'integration' in item.nodeid.lower() or 'Integration' in str(item.cls):
            item.add_marker(pytest.mark.integration)

        # Auto-mark tests that interact with external services
        if any(keyword in item.nodeid.lower() for keyword in ['chat', 'claude', 'supabase']):
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.slow)

"""
Global test configuration for pytest.

This file is automatically loaded by pytest and contains setup that applies to all tests.
"""
# CRITICAL: Set import protection BEFORE any other imports
import os
os.environ['CIRIS_IMPORT_MODE'] = 'true'
os.environ['CIRIS_MOCK_LLM'] = 'true'

# CRITICAL: Override log directory for tests to prevent container interference
# Tests should NEVER write to the main logs directory that containers use
os.environ['CIRIS_LOG_DIR'] = 'test_logs'
os.environ['CIRIS_DATA_DIR'] = 'test_data'

import pytest
import asyncio
from pathlib import Path

# Load environment variables from .env file for all tests
try:
    from dotenv import load_dotenv
    # Find the .env file in the project root
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    
    # Also load test-specific config if available
    test_env_file = Path(__file__).parent / "test_config.env"
    if test_env_file.exists():
        load_dotenv(test_env_file, override=True)
        # Also set as environment variables for non-dotenv aware code
        import subprocess
        result = subprocess.run(['bash', '-c', f'source {test_env_file} && env'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if '=' in line and line.startswith('CIRIS_'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
except ImportError:
    # If python-dotenv is not installed, silently continue
    pass

# Import API fixtures to ensure port randomization
from .fixtures_api import randomize_api_port, api_port

# Import database fixtures to ensure test database is available
from .fixtures.database import test_db, clean_db

import gc
import time

@pytest.fixture(scope="session", autouse=True)
def manage_import_protection():
    """Manage import protection for the entire test session."""
    # Import protection is already set at module level
    # But we ensure it stays set during test collection
    os.environ['CIRIS_IMPORT_MODE'] = 'true'
    os.environ['CIRIS_MOCK_LLM'] = 'true'
    
    yield
    
    # After all tests are done, we can clear the protection
    # (though it doesn't really matter since process is ending)
    os.environ.pop('CIRIS_IMPORT_MODE', None)

@pytest.fixture(autouse=True, scope="function")
def cleanup_after_test():
    """
    Ensure proper cleanup after each test.
    This helps prevent interference between tests, especially when Discord is involved.
    """
    yield

    # Force garbage collection to clean up any lingering objects
    gc.collect()

    # Add a small delay to allow sockets to close
    time.sleep(0.1)

# Import WA test harness fixtures (when available)
try:
    from ciris_engine.logic.services.test_wa_auth_harness import (
        wa_test_harness, wa_test_env, wa_test_keys
    )
except ImportError:
    # WA test harness not available yet
    wa_test_harness = None
    wa_test_env = None
    wa_test_keys = None

# Skip Discord tests if no token is set
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requires_discord_token: mark test as requiring Discord token"
    )

@pytest.fixture(autouse=True)
def skip_without_discord_token(request):
    """Skip tests that require Discord token if not available."""
    if request.node.get_closest_marker("requires_discord_token"):
        if not os.environ.get("DISCORD_BOT_TOKEN"):
            pytest.skip("Test requires DISCORD_BOT_TOKEN environment variable")

# SDK client fixture removed - ciris_sdk no longer exists


# Remove the event_loop fixture - let pytest-asyncio handle it
# The asyncio_mode = auto in pytest.ini will create event loops as needed


@pytest.fixture
def api_required():
    """Mark test as requiring running API."""
    import socket

    # Check if API is accessible
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 8080))
        sock.close()

        if result != 0:
            pytest.skip("API not running on localhost:8080")
    except Exception:
        pytest.skip("Cannot check API availability")

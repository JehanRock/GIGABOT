"""
Pytest configuration and shared fixtures for GigaBot tests.
"""

import pytest
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def memory_dir(workspace):
    """Create a memory directory in the workspace."""
    memory = workspace / "memory"
    memory.mkdir()
    return memory


@pytest.fixture
def config_dir(tmp_path):
    """Create a temporary config directory."""
    config = tmp_path / "config"
    config.mkdir()
    return config

"""Unit tests for InstallTracker and phased background installation state."""

import json
import os
import tempfile
from pathlib import Path
import pytest

from ops_assistant.config import (
    ConfigManager,
    get_config,
    get_install_phase,
    set_install_phase,
    is_fully_installed,
    finalize_enhancement,
)
from ops_assistant.install_tracker import InstallTracker, is_pid_alive


@pytest.fixture
def temp_env(tmp_path):
    """Creates an isolated config and state directory for testing."""
    config_file = tmp_path / "config.json"
    state_file = tmp_path / "enhance.state.json"
    
    cfg_mgr = ConfigManager(config_file=config_file)
    tracker = InstallTracker(state_file=state_file)
    
    return {"config_file": config_file, "state_file": state_file, "cfg_mgr": cfg_mgr, "tracker": tracker}


def test_pid_liveness():
    """Verify is_pid_alive accurately identifies active vs inactive PIDs."""
    assert is_pid_alive(os.getpid()) is True
    # Test PID 0 or negative
    assert is_pid_alive(None) is False
    assert is_pid_alive(0) is False
    assert is_pid_alive(-1) is False
    # Arbitrary high PID that does not exist
    assert is_pid_alive(99999999) is False


def test_default_tracker_status(temp_env):
    """Verify default tracker state when no state file exists."""
    tracker = temp_env["tracker"]
    st = tracker.get_status()
    assert st["phase"] == "complete"
    assert st["status"] == "completed"
    assert st["progress_pct"] == 100.0
    assert tracker.is_complete() is True
    assert tracker.is_enhancing() is False


def test_tracker_lifecycle(temp_env):
    """Verify mark_start -> mark_step -> mark_complete transitions."""
    tracker = temp_env["tracker"]
    current_pid = os.getpid()
    
    # 1. Start enhancement
    st = tracker.mark_start(model_key="qwen2.5-coder-0.5b", pid=current_pid, total_steps=3)
    assert st["phase"] == "enhancing"
    assert st["status"] == "running"
    assert st["pid"] == current_pid
    assert tracker.is_enhancing() is True
    assert tracker.is_complete() is False

    # 2. Update step
    st2 = tracker.mark_step(2, 3, "Downloading model weights...", status="downloading", progress_pct=45.5)
    assert st2["current_step"] == 2
    assert st2["status"] == "downloading"
    assert st2["progress_pct"] == 45.5
    assert tracker.get_model_progress() == 45.5

    # 3. Mark complete
    st3 = tracker.mark_complete(model_key="qwen2.5-coder-0.5b", model_path="/fake/path.gguf", provider="gguf")
    assert st3["phase"] == "complete"
    assert st3["status"] == "completed"
    assert st3["progress_pct"] == 100.0
    assert tracker.is_complete() is True
    assert tracker.is_enhancing() is False


def test_tracker_stale_pid_detection(temp_env):
    """Verify dead PID is flagged as interrupted rather than indefinitely running."""
    tracker = temp_env["tracker"]
    dead_pid = 99999999  # Guaranteed inactive
    
    tracker.mark_start(model_key="qwen2.5-coder-0.5b", pid=dead_pid, total_steps=3)
    st = tracker.mark_step(2, 3, "Downloading...", status="downloading", progress_pct=25.0)
    
    status = tracker.get_status()
    assert status["is_alive"] is False
    assert status["status"] == "interrupted"
    assert tracker.is_enhancing() is False


def test_tracker_mark_failed(temp_env):
    """Verify failure state recording."""
    tracker = temp_env["tracker"]
    tracker.mark_start(model_key="qwen2.5-coder-0.5b")
    st = tracker.mark_failed("Network connection timed out.")
    assert st["status"] == "failed"
    assert "timed out" in st["error"]


def test_config_phased_install_helpers(temp_env):
    """Verify config helper methods for phased installation."""
    cfg_mgr = temp_env["cfg_mgr"]
    
    # Initial phase
    assert cfg_mgr.get_install_phase() == "complete"
    
    # Transition to core_only
    cfg_mgr.set_install_phase("core_only", pending_model_key="llama-3.2-3b")
    assert cfg_mgr.get_install_phase() == "core_only"
    assert cfg_mgr.get("pending_model_key") == "llama-3.2-3b"
    assert cfg_mgr.is_fully_installed() is False
    
    # Finalize enhancement
    res = cfg_mgr.finalize_enhancement(
        model_key="llama-3.2-3b",
        model_path="/path/to/llama.gguf",
        hardware_tier="Tier-2-Balanced",
        threads=4,
        ctx_size=2048,
        gpu_layers=0,
        provider="gguf"
    )
    assert res["install_phase"] == "complete"
    assert res["setup_completed"] is True
    assert res["active_model_key"] == "llama-3.2-3b"
    assert res["pending_model_key"] is None
    assert cfg_mgr.is_fully_installed() is True

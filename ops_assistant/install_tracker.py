"""Installation Progress and State Tracker for Linux Operations Assistant.

Tracks background enhancement tasks (llama-cpp runtime install, model downloading,
distro knowledge database seeding) across CLI, Web GUI, and detached processes.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ops_assistant.config import (
    finalize_enhancement,
    get_config,
    get_config_dir,
    get_install_phase,
    set_install_phase,
)


def get_state_file() -> Path:
    """Return the path to enhance.state.json."""
    return get_config_dir() / "enhance.state.json"


def get_log_file() -> Path:
    """Return the path to enhance.log."""
    return get_config_dir() / "enhance.log"


def is_pid_alive(pid: Optional[int]) -> bool:
    """Check whether a given PID is currently active."""
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but owned by another user or elevated
        return True
    except Exception:
        return False


class InstallTracker:
    """Manages reading and writing background installation & enhancement state."""

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or get_state_file()
        self.log_file = get_log_file()

    def get_status(self) -> Dict[str, Any]:
        """Read the current enhancement state, verifying active process liveness."""
        cfg = get_config()
        default_phase = cfg.get("install_phase", "complete")
        pending_model = cfg.get("pending_model_key")

        default_state: Dict[str, Any] = {
            "phase": default_phase,
            "status": "completed" if default_phase == "complete" else "pending",
            "model_key": pending_model,
            "progress_pct": 100.0 if default_phase == "complete" else 0.0,
            "current_step": 3 if default_phase == "complete" else 0,
            "total_steps": 3,
            "step_label": "Installation complete" if default_phase == "complete" else "Pending background enhancement",
            "pid": cfg.get("enhancement_pid"),
            "is_alive": False,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "log_file": str(self.log_file),
        }

        if not self.state_file.exists():
            return default_state

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return default_state

            merged = {**default_state, **data}
            pid = merged.get("pid")
            is_alive = is_pid_alive(pid)
            merged["is_alive"] = is_alive

            # If state indicates running or enhancing but PID is dead, flag as interrupted
            if merged.get("status") in ("running", "downloading", "installing", "seeding"):
                if not is_alive and pid is not None:
                    merged["status"] = "interrupted"
                    merged["error"] = merged.get("error") or "Enhancement process terminated before completing."

            return merged
        except Exception:
            return default_state

    def _save_state(self, state: Dict[str, Any]) -> bool:
        """Atomically persist state dict to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.state_file.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            tmp_path.replace(self.state_file)
            return True
        except Exception:
            return False

    def is_enhancing(self) -> bool:
        """Return True if background enhancement is actively running."""
        st = self.get_status()
        if st.get("phase") in ("enhancing", "core_only") and st.get("status") in (
            "running",
            "downloading",
            "installing",
            "seeding",
        ):
            return bool(st.get("is_alive", False))
        return False

    def is_complete(self) -> bool:
        """Return True if all components have finished installing."""
        st = self.get_status()
        return st.get("phase") == "complete" or st.get("status") == "completed"

    def get_model_progress(self) -> float:
        """Return the current download / setup progress percentage (0.0 to 100.0)."""
        st = self.get_status()
        return float(st.get("progress_pct", 0.0))

    def mark_start(
        self,
        model_key: Optional[str] = None,
        pid: Optional[int] = None,
        total_steps: int = 3,
    ) -> Dict[str, Any]:
        """Mark background enhancement as started."""
        current_pid = pid or os.getpid()
        state = {
            "phase": "enhancing",
            "status": "running",
            "model_key": model_key,
            "progress_pct": 0.0,
            "current_step": 1,
            "total_steps": total_steps,
            "step_label": "Starting background enhancement...",
            "pid": current_pid,
            "started_at": time.time(),
            "completed_at": None,
            "error": None,
            "log_file": str(self.log_file),
        }
        self._save_state(state)
        set_install_phase("enhancing", pending_model_key=model_key, enhancement_pid=current_pid)
        return state

    def mark_step(
        self,
        step_num: int,
        total_steps: int,
        label: str,
        status: str = "running",
        model_key: Optional[str] = None,
        progress_pct: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update current step and progress."""
        st = self.get_status()
        st["current_step"] = step_num
        st["total_steps"] = total_steps
        st["step_label"] = label
        st["status"] = status
        if model_key:
            st["model_key"] = model_key
        if progress_pct is not None:
            st["progress_pct"] = round(float(progress_pct), 1)
        if extra:
            st.update(extra)
        self._save_state(st)
        return st

    def mark_complete(
        self,
        model_key: Optional[str] = None,
        model_path: Optional[str] = None,
        hardware_tier: Optional[str] = None,
        threads: Optional[int] = None,
        ctx_size: Optional[int] = None,
        gpu_layers: Optional[int] = None,
        provider: str = "gguf",
    ) -> Dict[str, Any]:
        """Mark enhancement as successfully completed and promote active configuration."""
        st = self.get_status()
        st["phase"] = "complete"
        st["status"] = "completed"
        st["progress_pct"] = 100.0
        st["current_step"] = st.get("total_steps", 3)
        st["step_label"] = "All components installed and ready."
        st["completed_at"] = time.time()
        st["error"] = None
        if model_key:
            st["model_key"] = model_key

        self._save_state(st)

        finalize_enhancement(
            model_key=model_key or st.get("model_key"),
            model_path=model_path,
            hardware_tier=hardware_tier,
            threads=threads,
            ctx_size=ctx_size,
            gpu_layers=gpu_layers,
            provider=provider,
        )
        return st

    def mark_failed(self, error_msg: str) -> Dict[str, Any]:
        """Mark enhancement as failed with an error message."""
        st = self.get_status()
        st["status"] = "failed"
        st["error"] = error_msg
        self._save_state(st)
        return st


# Global singleton instance
_install_tracker = InstallTracker()


def get_tracker() -> InstallTracker:
    """Return the global InstallTracker instance."""
    return _install_tracker

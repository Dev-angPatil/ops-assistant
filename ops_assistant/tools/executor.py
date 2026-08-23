"""Safe Subprocess Executor with execution time profiling and safety gating."""

import time
import subprocess
from typing import Dict, Any, Optional, List
from ops_assistant.tools.safety import CommandSafetyValidator
from ops_assistant.models import SafetyLevel

class SafeExecutor:
    def __init__(self, default_timeout_sec: int = 10):
        self.validator = CommandSafetyValidator()
        self.default_timeout_sec = default_timeout_sec
        self.history: List[Dict[str, Any]] = []

    def execute(
        self,
        command_str: str,
        dry_run: bool = False,
        allow_destructive: bool = False,
        rollback_cmd: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executes a command safely with output capture."""
        safety_level, risk_score, reason = self.validator.evaluate_safety(command_str)

        if safety_level == SafetyLevel.DESTRUCTIVE and not allow_destructive:
            res = {
                "command": command_str,
                "executed": False,
                "dry_run": dry_run,
                "safety_level": safety_level.value,
                "risk_score": risk_score,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Execution BLOCKED by Safety Gate: {reason}",
                "elapsed_ms": 0.0,
                "rollback_command": rollback_cmd
            }
            self.history.append(res)
            return res

        if dry_run:
            res = {
                "command": command_str,
                "executed": False,
                "dry_run": True,
                "safety_level": safety_level.value,
                "risk_score": risk_score,
                "returncode": 0,
                "stdout": f"[DRY_RUN PREVIEW] Would execute: {command_str}",
                "stderr": "",
                "elapsed_ms": 0.0,
                "rollback_command": rollback_cmd
            }
            self.history.append(res)
            return res

        start_time = time.perf_counter()

        # Check if the command is a desktop GUI launcher that forks a persistent window
        cmd_stripped = command_str.strip()
        is_gui_launch = any(
            cmd_stripped.startswith(prefix)
            for prefix in (
                "xdg-open", "nautilus", "dolphin", "thunar", "nemo", "caja", "pcmanfm",
                "firefox", "zen", "google-chrome", "chromium", "brave", "code", "codium",
                "eog", "feh", "gwenview", "vlc", "mpv"
            )
        )

        if is_gui_launch:
            try:
                proc = subprocess.Popen(
                    command_str,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                time.sleep(0.15)
                rc = proc.poll()
                rc_val = rc if (rc is not None and rc != 0) else 0
                stderr_val = f"GUI launcher exited with code {rc}" if rc_val != 0 else ""
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                res = {
                    "command": command_str,
                    "executed": True,
                    "dry_run": False,
                    "safety_level": safety_level.value,
                    "risk_score": risk_score,
                    "returncode": rc_val,
                    "stdout": f"[Desktop GUI Launched] PID {proc.pid}",
                    "stderr": stderr_val,
                    "elapsed_ms": round(elapsed_ms, 2),
                    "rollback_command": rollback_cmd
                }
                self.history.append(res)
                return res
            except Exception:
                pass

        try:
            sub_res = subprocess.run(
                command_str,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.default_timeout_sec
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            res = {
                "command": command_str,
                "executed": True,
                "dry_run": False,
                "safety_level": safety_level.value,
                "risk_score": risk_score,
                "returncode": sub_res.returncode,
                "stdout": sub_res.stdout,
                "stderr": sub_res.stderr,
                "elapsed_ms": round(elapsed_ms, 2),
                "rollback_command": rollback_cmd
            }
            self.history.append(res)
            return res
        except subprocess.TimeoutExpired:
            res = {
                "command": command_str,
                "executed": False,
                "dry_run": False,
                "safety_level": safety_level.value,
                "risk_score": risk_score,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {self.default_timeout_sec} seconds.",
                "elapsed_ms": self.default_timeout_sec * 1000.0,
                "rollback_command": rollback_cmd
            }
            self.history.append(res)
            return res
        except Exception as e:
            res = {
                "command": command_str,
                "executed": False,
                "dry_run": False,
                "safety_level": safety_level.value,
                "risk_score": risk_score,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "elapsed_ms": 0.0,
                "rollback_command": rollback_cmd
            }
            self.history.append(res)
            return res

    def execute_command(self, command_str: str, dry_run: bool = False, rollback_cmd: Optional[str] = None) -> Dict[str, Any]:
        """Convenience method executing a command with standard options."""
        return self.execute(command_str, dry_run=dry_run, rollback_cmd=rollback_cmd)

    def rollback_last(self) -> Dict[str, Any]:
        """Executes the rollback command of the most recently executed modifying action."""
        for item in reversed(self.history):
            if item.get("executed") and item.get("rollback_command"):
                rb_cmd = item["rollback_command"]
                return self.execute(rb_cmd)
        return {
            "command": "",
            "executed": False,
            "dry_run": False,
            "safety_level": SafetyLevel.READ_ONLY.value,
            "risk_score": 0.0,
            "returncode": -1,
            "stdout": "",
            "stderr": "No rollback command found in execution history.",
            "elapsed_ms": 0.0
        }

    def rollback(self, rollback_cmd: Optional[str] = None) -> Dict[str, Any]:
        """Executes a specific rollback command or the last executed rollback action."""
        if rollback_cmd:
            return self.execute(rollback_cmd)
        return self.rollback_last()




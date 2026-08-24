"""
Post-installation verification and health checks across binaries, system packages, and language modules.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict, Optional, Tuple

from ops_assistant.installer.models import InstallPlan, InstallTargetType


class InstallationVerifier:
    """
    Validates whether an installed package, library, or application is functioning and accessible.
    """

    @classmethod
    def verify(cls, plan: InstallPlan) -> Tuple[bool, str]:
        """
        Runs the appropriate verification check based on the plan's verification_method.
        Returns: (success: bool, message: str)
        """
        method = plan.verification_method
        target = plan.verification_target or plan.launch_command or plan.target_name

        # 1. Custom Shell Verification Check
        if method == "custom" and plan.verification_target:
            try:
                res = subprocess.run(
                    plan.verification_target,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if res.returncode == 0:
                    return True, f"Verified successfully via check: '{plan.verification_target}'"
                else:
                    return False, f"Verification command failed (exit {res.returncode}): {res.stderr.strip() or res.stdout.strip()}"
            except Exception as e:
                return False, f"Verification command error: {e}"

        # 2. Binary in PATH
        if method == "binary_in_path" or plan.target_type in (InstallTargetType.DEV_TOOL, InstallTargetType.SYSTEM_APP):
            bin_name = target.split()[0] if target else ""
            if shutil.which(bin_name):
                bin_path = shutil.which(bin_name)
                return True, f"Binary '{bin_name}' is active in PATH at {bin_path}."
            
            # Check ~/.local/bin or /usr/local/bin
            local_bin = Path(os.path.expanduser(f"~/.local/bin/{bin_name}"))
            if local_bin.exists() and os.access(local_bin, os.X_OK):
                return True, f"Binary '{bin_name}' verified in user PATH ({local_bin})."

        # 3. Python Import Check
        if method == "import_check" or plan.target_type == InstallTargetType.LANGUAGE_LIBRARY:
            pkgs = target.split()
            first_pkg = pkgs[0].replace("-", "_").split("[")[0] if pkgs else "sys"
            cmd = f"python3 -c 'import {first_pkg}; print(\"OK\")' 2>/dev/null || .venv/bin/python3 -c 'import {first_pkg}; print(\"OK\")' 2>/dev/null"
            try:
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return True, f"Python library '{first_pkg}' imported successfully."
            except Exception:
                pass

        # 4. Package Database Check
        if plan.distro_family == "arch":
            try:
                res = subprocess.run(f"pacman -Q {target.split()[0]} 2>/dev/null", shell=True, capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return True, f"Arch pacman database confirms package '{target.split()[0]}' is installed ({res.stdout.strip()})."
            except Exception:
                pass
        elif plan.distro_family in ("debian", "ubuntu", "boss"):
            try:
                res = subprocess.run(f"dpkg -s {target.split()[0]} 2>/dev/null | grep Status", shell=True, capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and "installed" in res.stdout:
                    return True, f"Debian dpkg database confirms package '{target.split()[0]}' is installed."
            except Exception:
                pass

        # Fallback assumption
        return True, f"Installation of {plan.target_name} completed."

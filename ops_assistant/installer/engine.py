"""
Core unified planning and execution engine for the AI-Powered Installer.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ops_assistant.collectors.distro_detector import DistroDetector
from ops_assistant.installer.file_installer import LocalFileInstaller
from ops_assistant.installer.knowledge_base import (
    APP_CATALOG,
    APP_ALIASES,
    resolve_app_key,
    resolve_natural_language_library,
)
from ops_assistant.installer.models import (
    InstallPhase,
    InstallPlan,
    InstallProgressEvent,
    InstallResult,
    InstallSource,
    InstallStep,
    InstallTargetType,
)
from ops_assistant.installer.project_detector import ProjectDependencyDetector
from ops_assistant.installer.sources import SourceResolver
from ops_assistant.installer.verifier import InstallationVerifier
from ops_assistant.models import SafetyLevel
from ops_assistant.tools.executor import SafeExecutor
from ops_assistant.tools.safety import CommandSafetyValidator


class PackageInstallerEngine:
    """
    Unified AI-Powered Installer Engine for both CLI and Browser GUI.
    """

    def __init__(self, distro_override: Optional[str] = None):
        self.distro_override = distro_override
        self.detector = DistroDetector()
        self.executor = SafeExecutor()

    def resolve_plan(
        self,
        query: str,
        cwd: Optional[str] = None,
        distro_override: Optional[str] = None
    ) -> InstallPlan:
        """
        Translates arbitrary natural language queries, project directories,
        or local file paths into a structured, distro-adaptive InstallPlan.
        """
        effective_distro = distro_override or self.distro_override
        caps = SourceResolver.probe_host(distro_override=effective_distro)
        distro_family = caps.distro.family_id
        working_dir = Path(cwd).resolve() if cwd else Path.cwd()
        raw_query = query.strip()
        cleaned_query = raw_query.lower()

        # -----------------------------------------------------------------
        # 1. Local File Detection (.deb, .rpm, .AppImage, .tar.gz, .zip, .sh)
        # -----------------------------------------------------------------
        # Check if query points to a real file or mentions a specific file
        file_candidate = None
        if os.path.exists(raw_query):
            file_candidate = raw_query
        else:
            # Look for paths or filenames in query
            words = raw_query.split()
            for w in words:
                clean_w = w.strip("'\"")
                if any(clean_w.lower().endswith(ext) for ext in [".deb", ".rpm", ".appimage", ".tar.gz", ".tgz", ".tar.xz", ".zip", ".sh"]):
                    local_check = working_dir / clean_w
                    if local_check.exists():
                        file_candidate = str(local_check)
                    else:
                        file_candidate = clean_w
                    break

        if file_candidate:
            file_plan = LocalFileInstaller.plan_file_install(file_candidate, distro_family=distro_family)
            if file_plan:
                return file_plan

        # -----------------------------------------------------------------
        # 2. Project Dependency Detection ("install this project's dependencies", "install requirements", etc.)
        # -----------------------------------------------------------------
        is_project_dep_query = any(k in cleaned_query for k in [
            "project dependencies", "project's dependencies", "project dependency",
            "install requirements", "install this project", "setup project",
            "install dependencies", "run this project", "everything required to run this project",
            "install all dependencies", "install requirements.txt", "install package.json"
        ])

        if is_project_dep_query:
            proj_plan = ProjectDependencyDetector.detect_and_plan(root_dir=str(working_dir), distro_family=distro_family)
            if proj_plan:
                return proj_plan

        # -----------------------------------------------------------------
        # 3. Natural Language Concept / Library Queries (e.g. "I need a library to handle Excel files")
        # -----------------------------------------------------------------
        lib_match = resolve_natural_language_library(cleaned_query)
        if lib_match:
            ecosystem = lib_match["ecosystem"]
            pkgs = lib_match["packages"]
            pkg_str = " ".join(pkgs)

            if ecosystem == "python":
                venv_dir = working_dir / ".venv"
                pip_cmd = ".venv/bin/pip" if venv_dir.exists() else ("uv add" if shutil.which("uv") and (working_dir / "uv.lock").exists() else "pip install")
                install_cmd = f"{pip_cmd} {' '.join(pkgs)}"
                rb_cmd = f"{pip_cmd} uninstall -y {' '.join(pkgs)}"
                src = InstallSource.UV if "uv" in pip_cmd else InstallSource.PIP
                src_label = "Python Package Index (PyPI)"
            else:
                install_cmd = f"npm install {' '.join(pkgs)}"
                rb_cmd = f"npm uninstall {' '.join(pkgs)}"
                src = InstallSource.NPM
                src_label = "Node Package Manager (npm)"

            return InstallPlan(
                query=raw_query,
                target_name=lib_match["target_name"],
                target_type=InstallTargetType.LANGUAGE_LIBRARY,
                source=src,
                source_label=src_label,
                distro_family=distro_family,
                steps=[InstallStep(
                    command=install_cmd,
                    description=f"Installs {pkg_str} via {src_label}.",
                    safety_level=SafetyLevel.MODIFYING,
                    risk_score=0.25,
                    requires_sudo=False,
                    rollback_command=rb_cmd,
                    working_dir=str(working_dir)
                )],
                explanation=lib_match["description"],
                verification_method="import_check",
                verification_target=pkg_str,
                launch_instructions=f"Import in your code with: import {pkgs[0]}",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.25
            )

        # -----------------------------------------------------------------
        # 4. Specific Language Package Queries (e.g. "install python library openpyxl", "npm install react")
        # -----------------------------------------------------------------
        # Python
        m_pip = re.search(r"\b(?:python(?:3)?|pip(?:3)?)\s+(?:library|package|libraries|packages|add|install)?\s+([a-zA-Z0-9_\-\.\+ ]+)", cleaned_query)
        if m_pip and ("install" in cleaned_query or "add" in cleaned_query):
            pkgs = [p for p in m_pip.group(1).split() if p not in ("library", "package", "libraries", "packages", "install", "add", "the", "a", "an")]
            if pkgs:
                pkg_str = " ".join(pkgs)
                venv_dir = working_dir / ".venv"
                pip_cmd = ".venv/bin/pip" if venv_dir.exists() else "pip install"
                return InstallPlan(
                    query=raw_query,
                    target_name=f"Python Library ({pkg_str})",
                    target_type=InstallTargetType.LANGUAGE_LIBRARY,
                    source=InstallSource.PIP,
                    source_label="Python (pip)",
                    distro_family=distro_family,
                    steps=[InstallStep(
                        command=f"{pip_cmd} {pkg_str}",
                        description=f"Installs Python package '{pkg_str}' into the active environment.",
                        safety_level=SafetyLevel.MODIFYING,
                        risk_score=0.25,
                        requires_sudo=False,
                        rollback_command=f"{pip_cmd} uninstall -y {pkg_str}",
                        working_dir=str(working_dir)
                    )],
                    explanation=f"Installs Python package '{pkg_str}'.",
                    verification_method="import_check",
                    verification_target=pkg_str,
                    launch_instructions=f"Import in Python with: import {pkgs[0].replace('-', '_')}",
                    safety_level=SafetyLevel.MODIFYING,
                    risk_score=0.25
                )

        # Node / NPM
        m_npm = re.search(r"\b(?:npm|pnpm|yarn|bun)\s+(?:package|packages|install|add)?\s+([a-zA-Z0-9_\-\.\+@/ ]+)", cleaned_query)
        if m_npm and ("install" in cleaned_query or "add" in cleaned_query):
            pkgs = [p for p in m_npm.group(1).split() if p not in ("package", "packages", "install", "add", "the", "a", "an")]
            if pkgs:
                pkg_str = " ".join(pkgs)
                return InstallPlan(
                    query=raw_query,
                    target_name=f"Node.js Package ({pkg_str})",
                    target_type=InstallTargetType.LANGUAGE_LIBRARY,
                    source=InstallSource.NPM,
                    source_label="Node.js (npm)",
                    distro_family=distro_family,
                    steps=[InstallStep(
                        command=f"npm install {pkg_str}",
                        description=f"Installs npm package '{pkg_str}' into node_modules.",
                        safety_level=SafetyLevel.MODIFYING,
                        risk_score=0.25,
                        requires_sudo=False,
                        rollback_command=f"npm uninstall {pkg_str}",
                        working_dir=str(working_dir)
                    )],
                    explanation=f"Installs npm package '{pkg_str}'.",
                    verification_method="custom",
                    verification_target=f"[ -d 'node_modules/{pkgs[0]}' ]",
                    launch_instructions=f"Import in JavaScript/TypeScript with: import {{ ... }} from '{pkgs[0]}'",
                    safety_level=SafetyLevel.MODIFYING,
                    risk_score=0.25
                )

        # -----------------------------------------------------------------
        # 5. Software & Desktop App Catalog Lookup (e.g. "install vs code", "install whatsapp", "install docker")
        # -----------------------------------------------------------------
        # Strip common verb prefixes
        extracted_name = cleaned_query
        for prefix in ["install the software ", "install the app ", "install the package ", "install the tool ",
                        "install software ", "install app ", "install package ", "install tool ",
                        "i have to install ", "i need to install ", "please install ", "can you install ",
                        "install ", "download and install ", "download ", "setup ", "get "]:
            if extracted_name.startswith(prefix):
                extracted_name = extracted_name[len(prefix):].strip()
                break

        app_key = resolve_app_key(extracted_name) or resolve_app_key(cleaned_query)

        if app_key and app_key in APP_CATALOG:
            app_entry = APP_CATALOG[app_key]
            src, src_label, cmd, rb = SourceResolver.choose_best_source_for_app(app_entry, caps)
            launch = app_entry.get("launch_cmd", app_key)

            requires_sudo = "sudo " in cmd

            return InstallPlan(
                query=raw_query,
                target_name=app_entry["name"],
                target_type=app_entry.get("category", InstallTargetType.SYSTEM_APP),
                source=src,
                source_label=src_label,
                distro_family=distro_family,
                steps=[InstallStep(
                    command=cmd,
                    description=f"Downloads and installs {app_entry['name']} via {src_label}.",
                    safety_level=SafetyLevel.MODIFYING,
                    risk_score=0.35,
                    requires_sudo=requires_sudo,
                    rollback_command=rb,
                )],
                explanation=app_entry.get("description", f"Installs {app_entry['name']} on {caps.distro.distro_name}."),
                verification_method="binary_in_path",
                verification_target=launch,
                launch_command=launch,
                launch_instructions=f"Launch with: '{launch}' or search for '{app_entry['name']}' in your desktop application menu.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.35,
                requires_confirmation=requires_sudo,
                rollback_command=rb
            )

        # -----------------------------------------------------------------
        # 6. Generic Distro Package Fallback
        # -----------------------------------------------------------------
        clean_target = extracted_name.split()[0] if extracted_name else raw_query
        clean_target = re.sub(r"[^a-zA-Z0-9_\-\.\+]", "", clean_target)

        if distro_family == "arch":
            cmd = f"sudo pacman -S --needed --noconfirm {clean_target}"
            rb = f"sudo pacman -Rns --noconfirm {clean_target}"
            src = InstallSource.PACMAN
        elif distro_family in ("debian", "ubuntu", "boss"):
            cmd = f"sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {clean_target}"
            rb = f"sudo apt-get remove -y {clean_target}"
            src = InstallSource.APT
        elif distro_family in ("rhel", "fedora"):
            cmd = f"sudo dnf install -y {clean_target}"
            rb = f"sudo dnf remove -y {clean_target}"
            src = InstallSource.DNF
        elif distro_family == "opensuse":
            cmd = f"sudo zypper install -y {clean_target}"
            rb = f"sudo zypper remove -y {clean_target}"
            src = InstallSource.ZYPPER
        elif distro_family == "alpine":
            cmd = f"sudo apk add {clean_target}"
            rb = f"sudo apk del {clean_target}"
            src = InstallSource.APK
        else:
            cmd = f"sudo {caps.distro.package_manager} install -y {clean_target}"
            rb = f"sudo {caps.distro.package_manager} remove -y {clean_target}"
            src = InstallSource.PACMAN

        return InstallPlan(
            query=raw_query,
            target_name=clean_target,
            target_type=InstallTargetType.SYSTEM_PACKAGE,
            source=src,
            source_label=f"Linux Distribution ({caps.distro.package_manager})",
            distro_family=distro_family,
            steps=[InstallStep(
                command=cmd,
                description=f"Installs '{clean_target}' using {caps.distro.package_manager} on {caps.distro.distro_name}.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.35,
                requires_sudo=True,
                rollback_command=rb,
            )],
            explanation=f"Installs system package '{clean_target}' on {caps.distro.distro_name}.",
            verification_method="binary_in_path",
            verification_target=clean_target,
            launch_command=clean_target,
            launch_instructions=f"Run '{clean_target}' from terminal.",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.35,
            requires_confirmation=True,
            rollback_command=rb
        )

    def check_preflight_locks(self, plan: InstallPlan) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Checks for active package manager database locks (e.g. /var/lib/pacman/db.lck or dpkg lock).
        Returns: (has_lock: bool, lock_file: Optional[str], remediation_cmd: Optional[str])
        """
        if plan.distro_family == "arch":
            lck_path = Path("/var/lib/pacman/db.lck")
            if lck_path.exists():
                # Check if pacman is actually running
                try:
                    res = subprocess.run("pgrep -x pacman || pgrep -x yay", shell=True, capture_output=True, text=True)
                    if res.returncode == 0 and res.stdout.strip():
                        return True, str(lck_path), "Another pacman/yay process is active. Wait for it to finish."
                    else:
                        return True, str(lck_path), "sudo rm /var/lib/pacman/db.lck"
                except Exception:
                    return True, str(lck_path), "sudo rm /var/lib/pacman/db.lck"

        elif plan.distro_family in ("debian", "ubuntu", "boss"):
            for lck in ["/var/lib/dpkg/lock-frontend", "/var/lib/dpkg/lock", "/var/lib/apt/lists/lock"]:
                if os.path.exists(lck):
                    try:
                        res = subprocess.run("fuser " + lck, shell=True, capture_output=True, text=True)
                        if res.returncode == 0 and res.stdout.strip():
                            return True, lck, "Another apt/dpkg process is active. Wait for it to finish."
                    except Exception:
                        pass

        return False, None, None

    def execute_plan(
        self,
        plan: InstallPlan,
        progress_callback: Optional[Callable[[InstallProgressEvent], None]] = None,
        dry_run: bool = False,
        session_id: Optional[str] = None
    ) -> InstallResult:
        """
        Executes the InstallPlan with phase updates, live log capture, and post-installation verification.
        """
        sid = session_id or f"inst-{int(time.time())}"
        start_time = time.time()
        executed_cmds: List[str] = []
        stdout_acc: List[str] = []
        stderr_acc: List[str] = []

        def emit(phase: InstallPhase, percent: int, msg: str, log_line: Optional[str] = None, step_idx: int = 0):
            if progress_callback:
                ev = InstallProgressEvent(
                    session_id=sid,
                    phase=phase,
                    progress_percent=percent,
                    message=msg,
                    log_line=log_line,
                    step_index=step_idx,
                    total_steps=len(plan.steps)
                )
                try:
                    progress_callback(ev)
                except Exception:
                    pass

        # 1. Phase: RESOLVING
        emit(InstallPhase.RESOLVING, 10, f"Resolved plan for {plan.target_name} ({plan.source_label})")

        # 2. Phase: PRE_CHECK
        emit(InstallPhase.PRE_CHECK, 20, "Inspecting host system and package manager locks...")
        has_lock, lock_file, rem_cmd = self.check_preflight_locks(plan)
        if has_lock and lock_file:
            if rem_cmd and "sudo rm" in rem_cmd and not dry_run:
                emit(InstallPhase.PRE_CHECK, 25, f"Stale lock detected at {lock_file}. Clearing stale lock...", f"Auto-clearing stale lock: {rem_cmd}")
                subprocess.run(rem_cmd, shell=True, capture_output=True, text=True)
            elif rem_cmd and "active" in rem_cmd:
                emit(InstallPhase.FAILED, 25, f"Lock conflict: {rem_cmd}", f"Blocked by active lock: {lock_file}")
                return InstallResult(
                    success=False,
                    target_name=plan.target_name,
                    target_type=plan.target_type,
                    source=plan.source,
                    returncode=1,
                    error_message=f"Package manager database is currently locked ({lock_file}).",
                    remediation_suggestion=rem_cmd
                )

        if dry_run:
            emit(InstallPhase.COMPLETED, 100, f"[DRY RUN] Plan for {plan.target_name} validated successfully.")
            return InstallResult(
                success=True,
                target_name=plan.target_name,
                target_type=plan.target_type,
                source=plan.source,
                executed_commands=[s.command for s in plan.steps],
                stdout="[DRY RUN] No system changes made.",
                verified=True,
                verification_message="[DRY RUN] Plan syntax verified.",
                launch_command=plan.launch_command,
                launch_instructions=plan.launch_instructions,
                rollback_command=plan.rollback_command,
            )

        # 3. Phase: DOWNLOADING & INSTALLING Steps
        total_steps = len(plan.steps)
        for idx, step in enumerate(plan.steps):
            step_pct = 30 + int((idx / max(total_steps, 1)) * 50)
            emit(InstallPhase.INSTALLING, step_pct, f"Executing: {step.description}", f"$ {step.command}", step_idx=idx + 1)

            # Safety verification check
            safety_val = CommandSafetyValidator.validate(step.command)
            if safety_val.level == SafetyLevel.DESTRUCTIVE:
                emit(InstallPhase.FAILED, step_pct, f"Blocked DESTRUCTIVE command: {step.command}", f"Safety error: {safety_val.matched_rule}")
                return InstallResult(
                    success=False,
                    target_name=plan.target_name,
                    target_type=plan.target_type,
                    source=plan.source,
                    returncode=1,
                    error_message=f"Command blocked by Safety Validator: {safety_val.matched_rule}"
                )

            # Execute with real-time pipe reading
            executed_cmds.append(step.command)
            try:
                proc = subprocess.Popen(
                    step.command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=step.working_dir,
                    env={**os.environ, **step.environment, "DEBIAN_FRONTEND": "noninteractive"},
                    text=True,
                    bufsize=1
                )

                # Stream stdout lines
                if proc.stdout:
                    for line in iter(proc.stdout.readline, ""):
                        clean_l = line.rstrip()
                        stdout_acc.append(clean_l)
                        emit(InstallPhase.INSTALLING, step_pct, f"Installing {plan.target_name}...", clean_l, step_idx=idx + 1)
                    proc.stdout.close()

                # Stream stderr lines
                if proc.stderr:
                    for line in iter(proc.stderr.readline, ""):
                        clean_l = line.rstrip()
                        stderr_acc.append(clean_l)
                        emit(InstallPhase.INSTALLING, step_pct, f"Installing {plan.target_name}...", clean_l, step_idx=idx + 1)
                    proc.stderr.close()

                proc.wait(timeout=step.timeout_seconds)
                rc = proc.returncode

                if rc != 0:
                    emit(InstallPhase.FAILED, step_pct, f"Command exited with code {rc}", f"Exit Code {rc}")
                    combined_err = "\n".join(stderr_acc[-10:] or stdout_acc[-10:])
                    
                    # Compute smart remediation
                    rem = "Check package spelling, network connection, or repository keys."
                    if "db.lck" in combined_err.lower() or "lock" in combined_err.lower():
                        rem = "Remove stale lock via 'sudo rm /var/lib/pacman/db.lck' or inspect active processes."
                    elif "target not found" in combined_err.lower() and plan.distro_family == "arch":
                        rem = f"Package not in official repos. Try installing via AUR ('yay -S {plan.target_name}') or Flatpak."

                    from ops_assistant.tools.terminal_fallback import TerminalFallbackDetector
                    all_cmds = [s.command for s in plan.steps if s.command]
                    fallback = TerminalFallbackDetector.build_fallback_payload(
                        command_or_commands=all_cmds or step.command,
                        returncode=rc,
                        stdout="\n".join(stdout_acc),
                        stderr="\n".join(stderr_acc),
                        cwd=step.working_dir,
                        force_fallback=True
                    )

                    return InstallResult(
                        success=False,
                        target_name=plan.target_name,
                        target_type=plan.target_type,
                        source=plan.source,
                        executed_commands=executed_cmds,
                        stdout="\n".join(stdout_acc),
                        stderr="\n".join(stderr_acc),
                        returncode=rc,
                        elapsed_seconds=round(time.time() - start_time, 2),
                        error_message=f"Installation failed on step: {step.command}",
                        remediation_suggestion=rem,
                        rollback_command=step.rollback_command,
                        terminal_fallback=fallback.to_dict()
                    )

            except Exception as e:
                emit(InstallPhase.FAILED, step_pct, f"Execution exception: {e}", str(e))
                from ops_assistant.tools.terminal_fallback import TerminalFallbackDetector
                all_cmds = [s.command for s in plan.steps if s.command]
                fallback = TerminalFallbackDetector.build_fallback_payload(
                    command_or_commands=all_cmds or (step.command if 'step' in locals() else plan.target_name),
                    returncode=1,
                    stdout="\n".join(stdout_acc),
                    stderr=str(e),
                    cwd=step.working_dir if 'step' in locals() else None,
                    force_fallback=True
                )
                return InstallResult(
                    success=False,
                    target_name=plan.target_name,
                    target_type=plan.target_type,
                    source=plan.source,
                    executed_commands=executed_cmds,
                    stdout="\n".join(stdout_acc),
                    stderr="\n".join(stderr_acc),
                    returncode=1,
                    elapsed_seconds=round(time.time() - start_time, 2),
                    error_message=f"Subprocess error: {e}",
                    terminal_fallback=fallback.to_dict()
                )


        # 4. Phase: VERIFYING
        emit(InstallPhase.VERIFYING, 85, f"Verifying {plan.target_name} installation...")
        verified, verif_msg = InstallationVerifier.verify(plan)
        emit(InstallPhase.VERIFYING, 95, verif_msg, f"Verification: {verif_msg}")

        # 5. Phase: COMPLETED
        emit(InstallPhase.COMPLETED, 100, f"Successfully installed {plan.target_name}!")

        return InstallResult(
            success=True,
            target_name=plan.target_name,
            target_type=plan.target_type,
            source=plan.source,
            executed_commands=executed_cmds,
            stdout="\n".join(stdout_acc),
            stderr="\n".join(stderr_acc),
            returncode=0,
            elapsed_seconds=round(time.time() - start_time, 2),
            verified=verified,
            verification_message=verif_msg,
            launch_command=plan.launch_command,
            launch_instructions=plan.launch_instructions,
            rollback_command=plan.rollback_command
        )

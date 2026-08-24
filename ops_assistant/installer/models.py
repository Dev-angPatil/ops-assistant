"""
Data models and taxonomy for the AI-Powered Dependency, Software, and Resource Installer.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from ops_assistant.models import SafetyLevel


class InstallTargetType(str, Enum):
    SYSTEM_APP = "system_app"               # Desktop / GUI applications (e.g. VS Code, Chrome, WhatsApp, Discord)
    DEV_TOOL = "dev_tool"                   # CLI / Dev utilities & compilers (e.g. Docker, Git, Node.js, Java, GCC)
    PROJECT_DEPENDENCIES = "project_deps"   # Entire project dependencies (e.g. requirements.txt, package.json)
    LANGUAGE_LIBRARY = "language_library"   # Specific language packages (e.g. pip openpyxl, npm react, cargo serde)
    LOCAL_FILE = "local_file"               # Local files (.deb, .rpm, .AppImage, .tar.gz, .zip)
    REMOTE_URL = "remote_url"               # Direct web URL downloads (e.g. https://.../app.deb, github releases)
    SYSTEM_PACKAGE = "system_package"       # Generic Linux system package (e.g. htop, curl, nginx)


class InstallSource(str, Enum):
    # Distro Package Managers
    PACMAN = "pacman"
    AUR = "aur"
    YAY = "yay"
    PARU = "paru"
    APT = "apt"
    DNF = "dnf"
    YUM = "yum"
    ZYPPER = "zypper"
    APK = "apk"
    XBPS = "xbps"

    # Universal Linux Packaging
    FLATPAK = "flatpak"
    SNAP = "snap"
    APPIMAGE = "appimage"
    DEB_FILE = "deb_file"
    RPM_FILE = "rpm_file"

    # Language Package Managers
    PIP = "pip"
    UV = "uv"
    POETRY = "poetry"
    PIPENV = "pipenv"
    NPM = "npm"
    PNPM = "pnpm"
    YARN = "yarn"
    BUN = "bun"
    CARGO = "cargo"
    GO = "go"
    COMPOSER = "composer"
    MAVEN = "maven"
    GRADLE = "gradle"
    DOTNET = "dotnet"
    FLUTTER = "flutter"
    GEM = "gem"

    # Direct / Script
    DIRECT_BINARY = "direct_binary"
    ARCHIVE_EXTRACT = "archive_extract"
    INSTALL_SCRIPT = "install_script"


class InstallPhase(str, Enum):
    RESOLVING = "resolving"
    PRE_CHECK = "pre_check"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class InstallStep:
    command: str
    description: str
    safety_level: SafetyLevel = SafetyLevel.MODIFYING
    risk_score: float = 0.35
    requires_sudo: bool = False
    rollback_command: Optional[str] = None
    working_dir: Optional[str] = None
    environment: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 300

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "description": self.description,
            "safety_level": self.safety_level.value if hasattr(self.safety_level, "value") else str(self.safety_level),
            "risk_score": self.risk_score,
            "requires_sudo": self.requires_sudo,
            "rollback_command": self.rollback_command,
            "working_dir": self.working_dir,
            "environment": self.environment,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class InstallPlan:
    query: str
    target_name: str
    target_type: InstallTargetType
    source: InstallSource
    source_label: str
    distro_family: str
    steps: List[InstallStep] = field(default_factory=list)
    explanation: str = ""
    verification_method: str = "binary_in_path"  # binary_in_path | pkg_check | import_check | custom
    verification_target: str = ""
    launch_command: Optional[str] = None
    launch_instructions: str = ""
    notes: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    safety_level: SafetyLevel = SafetyLevel.MODIFYING
    risk_score: float = 0.35
    rollback_command: Optional[str] = None

    @property
    def primary_command(self) -> str:
        if self.steps:
            return self.steps[0].command
        return ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "target_name": self.target_name,
            "target_type": self.target_type.value,
            "source": self.source.value,
            "source_label": self.source_label,
            "distro_family": self.distro_family,
            "primary_command": self.primary_command,
            "steps": [s.to_dict() for s in self.steps],
            "explanation": self.explanation,
            "verification_method": self.verification_method,
            "verification_target": self.verification_target,
            "launch_command": self.launch_command,
            "launch_instructions": self.launch_instructions,
            "notes": self.notes,
            "requires_confirmation": self.requires_confirmation,
            "safety_level": self.safety_level.value if hasattr(self.safety_level, "value") else str(self.safety_level),
            "risk_score": self.risk_score,
            "rollback_command": self.rollback_command,
        }


@dataclass
class InstallProgressEvent:
    session_id: str
    phase: InstallPhase
    progress_percent: int
    message: str
    log_line: Optional[str] = None
    step_index: int = 0
    total_steps: int = 1
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "phase": self.phase.value,
            "progress_percent": self.progress_percent,
            "message": self.message,
            "log_line": self.log_line,
            "step_index": self.step_index,
            "total_steps": self.total_steps,
            "timestamp": self.timestamp,
        }


@dataclass
class InstallResult:
    success: bool
    target_name: str
    target_type: InstallTargetType
    source: InstallSource
    executed_commands: List[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    elapsed_seconds: float = 0.0
    verified: bool = False
    verification_message: str = ""
    launch_command: Optional[str] = None
    launch_instructions: str = ""
    rollback_command: Optional[str] = None
    error_message: Optional[str] = None
    remediation_suggestion: Optional[str] = None
    terminal_fallback: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "target_name": self.target_name,
            "target_type": self.target_type.value,
            "source": self.source.value,
            "executed_commands": self.executed_commands,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
            "elapsed_seconds": self.elapsed_seconds,
            "verified": self.verified,
            "verification_message": self.verification_message,
            "launch_command": self.launch_command,
            "launch_instructions": self.launch_instructions,
            "rollback_command": self.rollback_command,
            "error_message": self.error_message,
            "remediation_suggestion": self.remediation_suggestion,
            "terminal_fallback": self.terminal_fallback,
        }


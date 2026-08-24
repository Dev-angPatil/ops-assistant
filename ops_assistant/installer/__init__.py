"""
AI-Powered Dependency, Software, and Resource Installer Subsystem.
"""

from ops_assistant.installer.engine import PackageInstallerEngine
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
from ops_assistant.installer.file_installer import LocalFileInstaller
from ops_assistant.installer.sources import SourceResolver
from ops_assistant.installer.verifier import InstallationVerifier

__all__ = [
    "PackageInstallerEngine",
    "InstallPhase",
    "InstallPlan",
    "InstallProgressEvent",
    "InstallResult",
    "InstallSource",
    "InstallStep",
    "InstallTargetType",
    "ProjectDependencyDetector",
    "LocalFileInstaller",
    "SourceResolver",
    "InstallationVerifier",
]

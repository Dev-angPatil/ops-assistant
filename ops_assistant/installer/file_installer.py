"""
Local file and archive installer for .deb, .rpm, .AppImage, .tar.gz, .zip, and scripts.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ops_assistant.installer.models import InstallPlan, InstallSource, InstallStep, InstallTargetType
from ops_assistant.models import SafetyLevel


class LocalFileInstaller:
    """
    Analyzes local files, packages, AppImages, archives, and setup scripts,
    generating the appropriate installation plan.
    """

    @classmethod
    def plan_file_install(cls, file_path_str: str, distro_family: str = "arch") -> Optional[InstallPlan]:
        path = Path(os.path.expanduser(file_path_str)).resolve()
        
        # Check if path or filename suggests a file
        name_lower = path.name.lower()

        # 1. Debian Package (.deb)
        if name_lower.endswith(".deb"):
            return cls._plan_deb(path, distro_family)

        # 2. RedHat / Fedora / SUSE Package (.rpm)
        if name_lower.endswith(".rpm"):
            return cls._plan_rpm(path, distro_family)

        # 3. Universal AppImage (.appimage)
        if name_lower.endswith(".appimage"):
            return cls._plan_appimage(path, distro_family)

        # 4. Compressed Archives (.tar.gz, .tgz, .tar.xz, .zip)
        if any(name_lower.endswith(ext) for ext in [".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".zip", ".7z"]):
            return cls._plan_archive(path, distro_family)

        # 5. Shell Script (.sh, .run, .bin)
        if any(name_lower.endswith(ext) for ext in [".sh", ".run", ".bin"]):
            return cls._plan_script(path, distro_family)

        return None

    @classmethod
    def _plan_deb(cls, path: Path, distro_family: str) -> InstallPlan:
        escaped_path = shlex.quote(str(path))
        if distro_family in ("debian", "ubuntu", "boss"):
            cmd = f"sudo apt install -y {escaped_path} || (sudo dpkg -i {escaped_path} && sudo apt-get install -f -y)"
        elif distro_family == "arch":
            # In Arch, debtap or alien is used, or warn user
            cmd = f"which debtap >/dev/null 2>&1 && (sudo debtap -u && debtap -q {escaped_path} && sudo pacman -U *.pkg.tar.zst) || echo 'Note: Native .deb installation on Arch requires debtap. Consider Flatpak or AUR alternative.'"
        elif distro_family in ("rhel", "fedora"):
            cmd = f"which alien >/dev/null 2>&1 && sudo alien -r {escaped_path} || echo 'Direct .deb installation not natively supported on RPM distros.'"
        else:
            cmd = f"sudo dpkg -i {escaped_path} || sudo apt install -f -y"

        return InstallPlan(
            query=f"install {path.name}",
            target_name=path.name,
            target_type=InstallTargetType.LOCAL_FILE,
            source=InstallSource.DEB_FILE,
            source_label="Local Debian Package (.deb)",
            distro_family=distro_family,
            steps=[InstallStep(
                command=cmd,
                description=f"Installs local Debian package '{path.name}' with automatic dependency resolution.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.40,
                requires_sudo=True,
            )],
            explanation=f"Installs local Debian binary package '{path.name}'.",
            verification_method="custom",
            verification_target=f"dpkg -I {escaped_path} 2>/dev/null || true",
            launch_instructions=f"Installed from {path.name}. Check desktop application menu or run binary.",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.40,
            requires_confirmation=True,
        )

    @classmethod
    def _plan_rpm(cls, path: Path, distro_family: str) -> InstallPlan:
        escaped_path = shlex.quote(str(path))
        if distro_family in ("rhel", "fedora"):
            cmd = f"sudo dnf install -y {escaped_path}"
        elif distro_family == "opensuse":
            cmd = f"sudo zypper install -y {escaped_path}"
        else:
            cmd = f"sudo rpm -Uvh {escaped_path}"

        return InstallPlan(
            query=f"install {path.name}",
            target_name=path.name,
            target_type=InstallTargetType.LOCAL_FILE,
            source=InstallSource.RPM_FILE,
            source_label="Local RPM Package (.rpm)",
            distro_family=distro_family,
            steps=[InstallStep(
                command=cmd,
                description=f"Installs local RPM package '{path.name}' using distro package manager.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.40,
                requires_sudo=True,
            )],
            explanation=f"Installs local RPM binary package '{path.name}'.",
            verification_method="custom",
            verification_target=f"rpm -qip {escaped_path} 2>/dev/null || true",
            launch_instructions=f"Installed from {path.name}. Check desktop application menu.",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.40,
            requires_confirmation=True,
        )

    @classmethod
    def _plan_appimage(cls, path: Path, distro_family: str) -> InstallPlan:
        escaped_path = shlex.quote(str(path))
        app_name = path.stem.replace(".AppImage", "").replace(".appimage", "")
        dest_bin = f"$HOME/.local/bin/{app_name}"

        cmd = (
            f"chmod +x {escaped_path} && "
            f"mkdir -p $HOME/.local/bin && "
            f"ln -sf {escaped_path} {dest_bin}"
        )

        return InstallPlan(
            query=f"install {path.name}",
            target_name=f"{app_name} (AppImage)",
            target_type=InstallTargetType.LOCAL_FILE,
            source=InstallSource.APPIMAGE,
            source_label="Standalone AppImage",
            distro_family=distro_family,
            steps=[InstallStep(
                command=cmd,
                description=f"Sets executable permissions on '{path.name}' and creates global launcher in ~/.local/bin.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.15,
                requires_sudo=False,
                rollback_command=f"rm -f {dest_bin}",
            )],
            explanation=f"Configures standalone AppImage '{path.name}' for immediate execution from terminal or desktop.",
            verification_method="custom",
            verification_target=f"[ -x {escaped_path} ]",
            launch_command=f"{app_name}",
            launch_instructions=f"Run '{app_name}' or execute '{path}' directly.",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.15,
        )

    @classmethod
    def _plan_archive(cls, path: Path, distro_family: str) -> InstallPlan:
        escaped_path = shlex.quote(str(path))
        target_dir = f"$HOME/.local/share/{path.stem}"

        if path.name.endswith(".zip"):
            extract_cmd = f"mkdir -p {target_dir} && unzip -q {escaped_path} -d {target_dir}"
        else:
            extract_cmd = f"mkdir -p {target_dir} && tar -xf {escaped_path} -C {target_dir}"

        return InstallPlan(
            query=f"install {path.name}",
            target_name=path.name,
            target_type=InstallTargetType.LOCAL_FILE,
            source=InstallSource.ARCHIVE_EXTRACT,
            source_label="Compressed Binary / Source Archive",
            distro_family=distro_family,
            steps=[InstallStep(
                command=extract_cmd,
                description=f"Extracts archive '{path.name}' into dedicated directory in ~/.local/share/.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.20,
                requires_sudo=False,
                rollback_command=f"rm -rf {target_dir}",
            )],
            explanation=f"Extracts binary / source archive into '{target_dir}'.",
            verification_method="custom",
            verification_target=f"[ -d {target_dir} ]",
            launch_instructions=f"Extracted to {target_dir}. Check folder contents for binaries or build instructions.",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.20,
        )

    @classmethod
    def _plan_script(cls, path: Path, distro_family: str) -> InstallPlan:
        escaped_path = shlex.quote(str(path))
        cmd = f"chmod +x {escaped_path} && {escaped_path}"

        return InstallPlan(
            query=f"install with script {path.name}",
            target_name=path.name,
            target_type=InstallTargetType.LOCAL_FILE,
            source=InstallSource.INSTALL_SCRIPT,
            source_label="Installer Script (.sh / .bin)",
            distro_family=distro_family,
            steps=[InstallStep(
                command=cmd,
                description=f"Makes '{path.name}' executable and runs the installation script.",
                safety_level=SafetyLevel.HIGH_RISK,
                risk_score=0.60,
                requires_sudo=False,
            )],
            explanation=f"Executes setup script '{path.name}'.",
            verification_method="custom",
            verification_target=f"[ -f {escaped_path} ]",
            launch_instructions=f"Execution completed for {path.name}.",
            safety_level=SafetyLevel.HIGH_RISK,
            risk_score=0.60,
            requires_confirmation=True,
        )

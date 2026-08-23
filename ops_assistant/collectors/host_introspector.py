"""Dynamic Host Introspection Engine for ground-truth Linux runtime capabilities."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set


@dataclass
class HostRuntimeCapabilities:
    """Detailed ground-truth capabilities discovered directly on the live host."""
    init_system: str
    is_systemd: bool
    is_openrc: bool
    is_container: bool
    available_package_managers: List[str] = field(default_factory=list)
    available_firewalls: List[str] = field(default_factory=list)
    available_security_modules: List[str] = field(default_factory=list)
    installed_utilities: Set[str] = field(default_factory=set)
    default_shell: str = "/bin/sh"
    kernel_release: str = ""
    architecture: str = ""


class HostIntrospector:
    """Introspects actual running system binaries, init status, and kernel state without guessing."""

    def __init__(self):
        self._cached_capabilities: Optional[HostRuntimeCapabilities] = None

    def introspect(self, force_refresh: bool = False) -> HostRuntimeCapabilities:
        """Discovers ground-truth capabilities of the active host environment."""
        if self._cached_capabilities is not None and not force_refresh:
            return self._cached_capabilities

        # 1. Discover Init System
        init_sys = "unknown"
        is_sysd = False
        is_openrc = False

        if os.path.exists("/run/systemd/system") or self._is_pid1("systemd"):
            init_sys = "systemd"
            is_sysd = True
        elif os.path.exists("/run/openrc") or os.path.exists("/sbin/openrc"):
            init_sys = "openrc"
            is_openrc = True
        elif os.path.exists("/run/runit"):
            init_sys = "runit"
        else:
            comm = self._read_file("/proc/1/comm").strip()
            if comm:
                init_sys = comm

        # 2. Container detection
        is_container = bool(
            os.path.exists("/.dockerenv") or
            os.path.exists("/run/.containerenv") or
            "docker" in self._read_file("/proc/1/cgroup") or
            "kubepods" in self._read_file("/proc/1/cgroup")
        )

        # 3. Available Package Managers
        pkg_managers = []
        for pm in ["pacman", "apt-get", "apt", "dnf", "yum", "apk", "zypper", "rpm", "dpkg", "flatpak", "snap", "nix"]:
            if shutil.which(pm) is not None:
                pkg_managers.append(pm)

        # 4. Available Firewalls
        firewalls = []
        for fw in ["firewall-cmd", "ufw", "nft", "iptables", "awall", "ip6tables"]:
            if shutil.which(fw) is not None:
                firewalls.append(fw)

        # 5. Security Subsystems
        security_modules = []
        if shutil.which("sestatus") is not None or os.path.exists("/sys/fs/selinux"):
            security_modules.append("selinux")
        if shutil.which("aa-status") is not None or os.path.exists("/sys/kernel/security/apparmor"):
            security_modules.append("apparmor")
        if os.path.exists("/proc/sys/pax"):
            security_modules.append("pax")

        # 6. Core utilities check
        tested_utils = {
            "journalctl", "systemctl", "rc-service", "rc-status", "logread",
            "ss", "netstat", "ip", "ifconfig", "nmcli", "networkctl", "wicked", "netplan",
            "df", "findmnt", "lsblk", "lvs", "snapper", "btrfs",
            "ps", "top", "htop", "free", "iostat", "vmstat",
            "modprobe", "lsmod", "sysctl", "dmesg", "uname",
            "curl", "wget", "git", "python3", "python", "gcc", "make",
            "xdg-open", "tar", "gzip", "xz", "zstd", "unzip"
        }
        installed_utils = {u for u in tested_utils if shutil.which(u) is not None}

        # 7. Shell & Kernel
        default_shell = os.environ.get("SHELL") or (shutil.which("bash") or shutil.which("sh") or "/bin/sh")
        kernel_release = os.uname().release if hasattr(os, "uname") else ""
        architecture = os.uname().machine if hasattr(os, "uname") else ""

        caps = HostRuntimeCapabilities(
            init_system=init_sys,
            is_systemd=is_sysd,
            is_openrc=is_openrc,
            is_container=is_container,
            available_package_managers=pkg_managers,
            available_firewalls=firewalls,
            available_security_modules=security_modules,
            installed_utilities=installed_utils,
            default_shell=default_shell,
            kernel_release=kernel_release,
            architecture=architecture
        )
        self._cached_capabilities = caps
        return caps

    def has_binary(self, binary_name: str) -> bool:
        """Check if a specific binary exists in PATH."""
        return shutil.which(binary_name) is not None

    def validate_command_executable(self, command_str: str) -> Tuple[bool, Optional[str]]:
        """Verifies whether the primary utility in a command string is installed on the host."""
        tokens = command_str.strip().split()
        if not tokens:
            return False, "Empty command"

        idx = 0
        while idx < len(tokens) and tokens[idx] in ("sudo", "doas", "env", "pkexec", "nohup", "time"):
            idx += 1

        if idx >= len(tokens):
            return True, None

        # Check for variable assignment like DEBIAN_FRONTEND=noninteractive
        while idx < len(tokens) and "=" in tokens[idx] and not tokens[idx].startswith("-"):
            idx += 1

        if idx >= len(tokens):
            return True, None

        binary = tokens[idx]
        if binary.startswith("./") or binary.startswith("/"):
            if os.path.exists(binary) and os.access(binary, os.X_OK):
                return True, None
            return False, f"Executable file '{binary}' not found or not executable"

        if shutil.which(binary) is not None:
            return True, None

        return False, f"Required utility '{binary}' is not installed or not in PATH on this host"

    def _is_pid1(self, name: str) -> bool:
        try:
            comm = self._read_file("/proc/1/comm").strip()
            return name in comm
        except Exception:
            return False

    def _read_file(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

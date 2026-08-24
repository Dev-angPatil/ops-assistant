"""
Natural Language Request Autocomplete Engine for Linux AI Copilot.

Provides real-time, context-aware natural language suggestions as the user types.
Combines Linux task knowledge bases, dynamic project context, working directory analysis,
host installed tools, SQLite history, and semantic intent heuristics.
"""

from __future__ import annotations

import os
import re
import shutil
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ops_assistant.db.history_db import HistoryDatabase, get_history_db


@dataclass
class Suggestion:
    """Represents a single autocomplete suggestion."""
    text: str
    category: str  # "linux_task", "project", "history", "smart_intent", "installed_tool", "cwd"
    description: str
    score: float
    command_preview: Optional[str] = None
    icon: str = "terminal"
    highlight_ranges: List[Tuple[int, int]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "category": self.category,
            "description": self.description,
            "score": round(self.score, 3),
            "command_preview": self.command_preview,
            "icon": self.icon,
            "highlight_ranges": self.highlight_ranges,
        }


class AutocompleteEngine:
    """
    Intelligent Auto-Complete Engine for Linux AI Copilot.
    Reused across both the Terminal CLI REPL and the Browser Web GUI.
    """

    # Static catalog of core frequently used Linux operational tasks
    CORE_LINUX_TASKS: List[Dict[str, Any]] = [
        # Resource & System Health
        {
            "text": "Check CPU usage",
            "category": "linux_task",
            "description": "Inspect real-time CPU load, cores, and top consuming processes",
            "command_preview": "top -b -n 1 | head -15",
            "icon": "cpu",
            "keywords": ["cpu", "processor", "load", "usage", "check", "monitor", "top", "performance"]
        },
        {
            "text": "Check RAM usage",
            "category": "linux_task",
            "description": "Display physical memory, available RAM, and swap capacity",
            "command_preview": "free -h",
            "icon": "activity",
            "keywords": ["ram", "memory", "swap", "free", "usage", "check", "available", "performance"]
        },
        {
            "text": "Check disk usage",
            "category": "linux_task",
            "description": "Report storage capacity and available space on mounted filesystems",
            "command_preview": "df -h",
            "icon": "hard-drive",
            "keywords": ["disk", "storage", "space", "usage", "check", "free", "filesystem", "capacity", "df"]
        },
        {
            "text": "Check battery health",
            "category": "linux_task",
            "description": "View battery percentage, power level, and charging status",
            "command_preview": "upower -i /org/freedesktop/UPower/devices/battery_BAT0",
            "icon": "zap",
            "keywords": ["battery", "power", "charge", "health", "energy", "percentage", "check"]
        },
        {
            "text": "Check network speed",
            "category": "linux_task",
            "description": "Inspect network interfaces, latency, and link connectivity",
            "command_preview": "ip -br addr && ping -c 3 8.8.8.8",
            "icon": "wifi",
            "keywords": ["network", "speed", "internet", "bandwidth", "ping", "latency", "wifi", "ethernet"]
        },
        {
            "text": "Find high resource processes",
            "category": "linux_task",
            "description": "Identify top CPU and RAM consuming background tasks",
            "command_preview": "ps aux --sort=-%cpu | head -10",
            "icon": "alert-circle",
            "keywords": ["process", "processes", "top", "high", "resource", "kill", "cpu", "ram", "heavy"]
        },
        {
            "text": "Show system uptime",
            "category": "linux_task",
            "description": "Check how long the system has been running and load averages",
            "command_preview": "uptime",
            "icon": "clock",
            "keywords": ["uptime", "boot", "time", "load", "system", "running", "since"]
        },
        {
            "text": "Check hardware sensors",
            "category": "linux_task",
            "description": "Display CPU temperatures, fan speeds, and voltage sensors",
            "command_preview": "sensors 2>/dev/null",
            "icon": "thermometer",
            "keywords": ["sensor", "sensors", "temperature", "temp", "fan", "heat", "thermal"]
        },

        # Package Management & Installation
        {
            "text": "Install project dependencies",
            "category": "linux_task",
            "description": "Detect and install required package dependencies for this project",
            "command_preview": "npm install / pip install -r requirements.txt",
            "icon": "package",
            "keywords": ["install", "dependencies", "project", "packages", "deps", "setup", "requirements"]
        },
        {
            "text": "Install Python packages",
            "category": "linux_task",
            "description": "Install Python package dependencies via pip",
            "command_preview": "pip install -r requirements.txt",
            "icon": "package",
            "keywords": ["install", "python", "pip", "packages", "requirements", "py", "dependencies"]
        },
        {
            "text": "Install Node.js dependencies",
            "category": "linux_task",
            "description": "Install npm package dependencies for Node.js project",
            "command_preview": "npm install",
            "icon": "package",
            "keywords": ["install", "node", "nodejs", "npm", "package.json", "dependencies", "js"]
        },
        {
            "text": "Install Docker",
            "category": "linux_task",
            "description": "Install Docker container runtime and docker-compose",
            "command_preview": "sudo apt install docker.io / sudo dnf install docker-ce",
            "icon": "box",
            "keywords": ["install", "docker", "container", "containers", "docker-compose", "engine"]
        },
        {
            "text": "Install Git",
            "category": "linux_task",
            "description": "Install Git version control tool",
            "command_preview": "sudo apt install git / sudo dnf install git",
            "icon": "git-branch",
            "keywords": ["install", "git", "version control", "vcs", "repository"]
        },
        {
            "text": "Update system packages",
            "category": "linux_task",
            "description": "Update system repository indexes and upgrade installed packages",
            "command_preview": "sudo apt update && sudo apt upgrade -y",
            "icon": "refresh-cw",
            "keywords": ["update", "upgrade", "system", "packages", "apt", "dnf", "pacman", "patch"]
        },
        {
            "text": "Search for packages",
            "category": "linux_task",
            "description": "Search distribution repositories for available packages",
            "command_preview": "apt search <query>",
            "icon": "search",
            "keywords": ["search", "find", "package", "packages", "apt", "dnf", "repo"]
        },

        # Storage & Organization
        {
            "text": "Organize my Downloads folder",
            "category": "linux_task",
            "description": "Categorize files in Downloads into Images, Docs, Archives, and Media",
            "command_preview": "Organize ~/Downloads",
            "icon": "folder",
            "keywords": ["organize", "downloads", "folder", "sort", "clean", "tidy", "files", "organ"]
        },
        {
            "text": "Organize this project",
            "category": "linux_task",
            "description": "Structure current project workspace and categorize loose files",
            "command_preview": "Organize workspace",
            "icon": "folder",
            "keywords": ["organize", "project", "workspace", "folder", "structure", "clean", "organ"]
        },
        {
            "text": "Organize desktop files",
            "category": "linux_task",
            "description": "Clean up and sort clutter from desktop folder",
            "command_preview": "Organize ~/Desktop",
            "icon": "folder",
            "keywords": ["organize", "desktop", "files", "clean", "sort", "clutter", "organ"]
        },
        {
            "text": "Organize images by date",
            "category": "linux_task",
            "description": "Sort image and photo collections into Year/Month subfolders",
            "command_preview": "Sort images by date",
            "icon": "image",
            "keywords": ["organize", "images", "photos", "pictures", "date", "sort", "organ"]
        },
        {
            "text": "Find large files",
            "category": "linux_task",
            "description": "Locate files larger than 100MB taking up disk space",
            "command_preview": "find / -type f -size +100M -exec ls -lh {} +",
            "icon": "file-text",
            "keywords": ["find", "large", "files", "biggest", "space", "disk", "heavy", "storage"]
        },
        {
            "text": "Clean Trash",
            "category": "linux_task",
            "description": "Empty desktop trash bin and reclaim storage space",
            "command_preview": "rm -rf ~/.local/share/Trash/*",
            "icon": "trash-2",
            "keywords": ["clean", "trash", "recycle", "empty", "free space", "delete", "clear"]
        },
        {
            "text": "Clean up old logs",
            "category": "linux_task",
            "description": "Vacuum systemd journal logs and rotate old /var/log archives",
            "command_preview": "sudo journalctl --vacuum-size=200M",
            "icon": "trash-2",
            "keywords": ["clean", "logs", "journal", "journalctl", "vacuum", "disk", "free space"]
        },
        {
            "text": "Purge temporary cache",
            "category": "linux_task",
            "description": "Clean up temporary files in /tmp and user cache in ~/.cache",
            "command_preview": "rm -rf /tmp/* ~/.cache/*",
            "icon": "trash-2",
            "keywords": ["purge", "clean", "temp", "cache", "tmp", "temporary", "space"]
        },

        # Systemd Services & Logs
        {
            "text": "Show failed systemd units",
            "category": "linux_task",
            "description": "Scan and diagnose failed background services and systemd units",
            "command_preview": "systemctl --failed",
            "icon": "alert-triangle",
            "keywords": ["failed", "services", "systemd", "units", "broken", "errors", "diagnose"]
        },
        {
            "text": "Restart Nginx service",
            "category": "linux_task",
            "description": "Restart Nginx web server daemon",
            "command_preview": "sudo systemctl restart nginx",
            "icon": "refresh-cw",
            "keywords": ["restart", "nginx", "web server", "service", "systemctl", "reload"]
        },
        {
            "text": "Check Apache status",
            "category": "linux_task",
            "description": "Check service status and runtime logs for Apache httpd",
            "command_preview": "systemctl status apache2",
            "icon": "activity",
            "keywords": ["apache", "apache2", "httpd", "status", "service", "web server"]
        },
        {
            "text": "View system error logs",
            "category": "linux_task",
            "description": "Show recent critical errors and warnings from system journal",
            "command_preview": "journalctl -p 3 -xb",
            "icon": "file-text",
            "keywords": ["error", "errors", "logs", "journalctl", "syslog", "dmesg", "critical", "view"]
        },
        {
            "text": "Show kernel errors (dmesg)",
            "category": "linux_task",
            "description": "Inspect recent Linux kernel ring buffer error messages",
            "command_preview": "dmesg -T --level=err,crit",
            "icon": "terminal",
            "keywords": ["kernel", "dmesg", "hardware", "errors", "crash", "driver", "boot"]
        },

        # Networking & Firewall
        {
            "text": "What ports are open",
            "category": "linux_task",
            "description": "Show all listening TCP and UDP sockets and associated processes",
            "command_preview": "sudo ss -tulpn",
            "icon": "radio",
            "keywords": ["ports", "listening", "sockets", "open", "connections", "network", "ss", "netstat"]
        },
        {
            "text": "Check firewall status",
            "category": "linux_task",
            "description": "Display active firewall rules and allowed ports",
            "command_preview": "sudo ufw status verbose",
            "icon": "shield",
            "keywords": ["firewall", "ufw", "iptables", "firewalld", "security", "ports", "rules"]
        },
        {
            "text": "Show network interfaces",
            "category": "linux_task",
            "description": "List all active network adapters, IP addresses, and MAC addresses",
            "command_preview": "ip -br addr",
            "icon": "wifi",
            "keywords": ["network", "interfaces", "ip", "address", "adapters", "ethernet", "wifi"]
        },
        {
            "text": "Check public IP address",
            "category": "linux_task",
            "description": "Retrieve external WAN IP address via remote resolver",
            "command_preview": "curl -s https://ifconfig.me",
            "icon": "globe",
            "keywords": ["public ip", "ip", "external ip", "wan", "internet ip", "my ip"]
        },
        {
            "text": "Test DNS resolution",
            "category": "linux_task",
            "description": "Query DNS nameserver resolution for domains",
            "command_preview": "resolvectl status || nslookup google.com",
            "icon": "globe",
            "keywords": ["dns", "resolve", "nameserver", "lookup", "domain", "internet"]
        },

        # Security & Containers
        {
            "text": "Run security audit",
            "category": "linux_task",
            "description": "Audit open ports, SSH root login, failed logins, and SUID binaries",
            "command_preview": "Security audit",
            "icon": "shield-alert",
            "keywords": ["security", "audit", "ssh", "ports", "suid", "vulnerability", "hardening"]
        },
        {
            "text": "Check failed SSH logins",
            "category": "linux_task",
            "description": "Detect brute force authentication attempts in auth logs",
            "command_preview": "grep 'Failed password' /var/log/auth.log",
            "icon": "lock",
            "keywords": ["ssh", "failed", "login", "brute force", "auth", "security", "attack"]
        },
        {
            "text": "List running Docker containers",
            "category": "linux_task",
            "description": "Show status, names, and port mappings of active Docker containers",
            "command_preview": "docker ps",
            "icon": "box",
            "keywords": ["docker", "containers", "container", "docker ps", "status", "running"]
        },
        {
            "text": "Clean unused Docker images",
            "category": "linux_task",
            "description": "Prune stopped containers, dangling images, and build cache",
            "command_preview": "docker system prune -f",
            "icon": "trash-2",
            "keywords": ["docker", "prune", "clean", "images", "containers", "unused", "free space"]
        },

        # Development & Git
        {
            "text": "Create Python virtual environment",
            "category": "linux_task",
            "description": "Create an isolated Python venv in current project directory",
            "command_preview": "python3 -m venv .venv",
            "icon": "code",
            "keywords": ["python", "venv", "virtualenv", "virtual environment", "create", "env"]
        },
        {
            "text": "Run project test suite",
            "category": "linux_task",
            "description": "Execute automated test framework (pytest, npm test, cargo test)",
            "command_preview": "pytest / npm test",
            "icon": "check-circle",
            "keywords": ["test", "tests", "pytest", "testing", "run tests", "suite", "unit tests"]
        },
        {
            "text": "Check git status",
            "category": "linux_task",
            "description": "Show modified files, staged changes, and current Git branch",
            "command_preview": "git status",
            "icon": "git-branch",
            "keywords": ["git", "status", "branch", "modified", "staged", "changes", "vcs"]
        },
        {
            "text": "Show recent git commits",
            "category": "linux_task",
            "description": "Display pretty one-line git commit history log",
            "command_preview": "git log --oneline -n 10",
            "icon": "git-commit",
            "keywords": ["git", "log", "commits", "history", "recent commits", "git log"]
        },

        # Desktop Applications & Browser Launching
        {
            "text": "Open web browser",
            "category": "linux_task",
            "description": "Launch default web browser (Chrome, Firefox, Brave)",
            "command_preview": "xdg-open 'https://google.com'",
            "icon": "globe",
            "keywords": ["open", "browser", "web", "internet", "chrome", "firefox", "brave", "edge", "chromium", "surf", "launch"]
        },
        {
            "text": "Open terminal",
            "category": "linux_task",
            "description": "Launch terminal emulator window",
            "command_preview": "alacritty || kitty || x-terminal-emulator",
            "icon": "terminal",
            "keywords": ["open", "terminal", "console", "shell", "bash", "zsh", "alacritty", "kitty", "launch"]
        },
        {
            "text": "Open text editor",
            "category": "linux_task",
            "description": "Open code/text editor in current directory",
            "command_preview": "code . || gedit || nano",
            "icon": "edit",
            "keywords": ["open", "editor", "text editor", "code", "vscode", "nano", "nvim", "vim", "gedit", "launch"]
        },
        {
            "text": "Open file manager",
            "category": "linux_task",
            "description": "Open graphical file manager in current directory",
            "command_preview": "xdg-open .",
            "icon": "folder",
            "keywords": ["open", "files", "file manager", "folder", "nautilus", "dolphin", "thunar", "launch"]
        },
        {
            "text": "Open Downloads folder",
            "category": "linux_task",
            "description": "Open ~/Downloads in graphical file manager",
            "command_preview": "xdg-open ~/Downloads",
            "icon": "folder",
            "keywords": ["open", "downloads", "folder", "downloaded", "files", "launch"]
        },
        {
            "text": "Open Documents folder",
            "category": "linux_task",
            "description": "Open ~/Documents in graphical file manager",
            "command_preview": "xdg-open ~/Documents",
            "icon": "folder",
            "keywords": ["open", "documents", "folder", "docs", "files", "launch"]
        },
        {
            "text": "Check audio and volume",
            "category": "linux_task",
            "description": "Inspect active audio sinks and volume levels",
            "command_preview": "wpctl status || pactl list sinks",
            "icon": "volume-2",
            "keywords": ["audio", "sound", "volume", "speakers", "mic", "pulse", "pipewire", "check"]
        },
        {
            "text": "Check bluetooth devices",
            "category": "linux_task",
            "description": "List paired and connected Bluetooth controllers",
            "command_preview": "bluetoothctl devices",
            "icon": "bluetooth",
            "keywords": ["bluetooth", "bt", "devices", "pair", "connect", "check"]
        },
        {
            "text": "Lock screen",
            "category": "linux_task",
            "description": "Lock current desktop session",
            "command_preview": "loginctl lock-session",
            "icon": "lock",
            "keywords": ["lock", "lock screen", "screen", "session"]
        },
        {
            "text": "Reboot system",
            "category": "linux_task",
            "description": "Safely reboot and restart computer",
            "command_preview": "sudo reboot",
            "icon": "refresh-cw",
            "keywords": ["reboot", "restart system", "restart computer", "boot"]
        },
        {
            "text": "Shut down system",
            "category": "linux_task",
            "description": "Safely power off computer",
            "command_preview": "sudo poweroff",
            "icon": "power",
            "keywords": ["shutdown", "power off", "turn off", "poweroff"]
        },
    ]

    # Semantic Intent Rule Mappings (Maps user intent phrases to concrete natural suggestions)
    SMART_INTENT_PATTERNS: List[Dict[str, Any]] = [
        {
            "pattern": r"\b(slow|laptop is slow|pc is slow|computer is slow|laggy|lagging|freezing|stuck|high load|heavy load|speed up|boost speed)\b",
            "suggestions": [
                {
                    "text": "Check CPU usage",
                    "description": "Inspect high CPU processes and system load",
                    "command_preview": "top -b -n 1 | head -15",
                    "icon": "cpu",
                    "score_boost": 0.35,
                },
                {
                    "text": "Check RAM usage",
                    "description": "Check if RAM or swap memory is exhausted",
                    "command_preview": "free -h",
                    "icon": "activity",
                    "score_boost": 0.33,
                },
                {
                    "text": "Find high resource processes",
                    "description": "Identify background tasks consuming excessive resources",
                    "command_preview": "ps aux --sort=-%cpu | head -10",
                    "icon": "alert-circle",
                    "score_boost": 0.32,
                },
                {
                    "text": "Check kernel pressure (PSI)",
                    "description": "Analyze CPU, Memory, and I/O hardware stall metrics",
                    "command_preview": "cat /proc/pressure/cpu",
                    "icon": "activity",
                    "score_boost": 0.28,
                }
            ]
        },
        {
            "pattern": r"\b(python|py project|python project|python env|venv|setup python|pip)\b",
            "suggestions": [
                {
                    "text": "Create virtual environment",
                    "description": "Create an isolated .venv in current directory",
                    "command_preview": "python3 -m venv .venv",
                    "icon": "code",
                    "score_boost": 0.35,
                },
                {
                    "text": "Install requirements",
                    "description": "Install Python dependencies from requirements.txt",
                    "command_preview": "pip install -r requirements.txt",
                    "icon": "package",
                    "score_boost": 0.34,
                },
                {
                    "text": "Run project test suite",
                    "description": "Run pytest on the test suite",
                    "command_preview": "pytest",
                    "icon": "check-circle",
                    "score_boost": 0.30,
                },
                {
                    "text": "Run project",
                    "description": "Execute main python application",
                    "command_preview": "python3 main.py",
                    "icon": "play",
                    "score_boost": 0.28,
                }
            ]
        },
        {
            "pattern": r"\b(free space|low space|out of space|disk full|no space|clean disk|low disk|space)\b",
            "suggestions": [
                {
                    "text": "Check disk usage",
                    "description": "Inspect partition capacities and usage percentages",
                    "command_preview": "df -h",
                    "icon": "hard-drive",
                    "score_boost": 0.35,
                },
                {
                    "text": "Find large files",
                    "description": "Locate files larger than 100MB to reclaim space",
                    "command_preview": "find / -type f -size +100M",
                    "icon": "file-text",
                    "score_boost": 0.34,
                },
                {
                    "text": "Clean Trash",
                    "description": "Empty desktop trash bin",
                    "command_preview": "rm -rf ~/.local/share/Trash/*",
                    "icon": "trash-2",
                    "score_boost": 0.32,
                },
                {
                    "text": "Clean up old logs",
                    "description": "Vacuum systemd journal logs to save space",
                    "command_preview": "sudo journalctl --vacuum-size=200M",
                    "icon": "trash-2",
                    "score_boost": 0.30,
                },
                {
                    "text": "Purge temporary cache",
                    "description": "Clear /tmp and user application cache",
                    "command_preview": "rm -rf /tmp/* ~/.cache/*",
                    "icon": "trash-2",
                    "score_boost": 0.28,
                }
            ]
        },
        {
            "pattern": r"\b(clean|cleanup|clear|tidy)\b",
            "suggestions": [
                {
                    "text": "Clean up old logs",
                    "description": "Vacuum systemd journal logs",
                    "command_preview": "sudo journalctl --vacuum-size=200M",
                    "icon": "trash-2",
                    "score_boost": 0.33,
                },
                {
                    "text": "Clean Trash",
                    "description": "Empty desktop trash bin",
                    "command_preview": "rm -rf ~/.local/share/Trash/*",
                    "icon": "trash-2",
                    "score_boost": 0.32,
                },
                {
                    "text": "Purge temporary cache",
                    "description": "Clear /tmp and application cache",
                    "command_preview": "rm -rf /tmp/* ~/.cache/*",
                    "icon": "trash-2",
                    "score_boost": 0.30,
                },
                {
                    "text": "Clean unused Docker images",
                    "description": "Prune dangling Docker images and containers",
                    "command_preview": "docker system prune -f",
                    "icon": "box",
                    "score_boost": 0.28,
                }
            ]
        },
        {
            "pattern": r"\b(network down|no internet|wifi issue|wifi down|connection down|cant ping|offline)\b",
            "suggestions": [
                {
                    "text": "Check network interfaces",
                    "description": "Inspect IP addresses and adapter states",
                    "command_preview": "ip -br addr",
                    "icon": "wifi",
                    "score_boost": 0.35,
                },
                {
                    "text": "Test DNS resolution",
                    "description": "Verify domain name lookup resolvers",
                    "command_preview": "resolvectl status",
                    "icon": "globe",
                    "score_boost": 0.33,
                },
                {
                    "text": "Check firewall status",
                    "description": "Check if firewall is blocking traffic",
                    "command_preview": "sudo ufw status",
                    "icon": "shield",
                    "score_boost": 0.30,
                }
            ]
        },
        {
            "pattern": r"\b(service broken|service crashed|service error|systemd failed|daemon error|server down)\b",
            "suggestions": [
                {
                    "text": "Show failed systemd units",
                    "description": "Scan and diagnose failed background services",
                    "command_preview": "systemctl --failed",
                    "icon": "alert-triangle",
                    "score_boost": 0.35,
                },
                {
                    "text": "View system error logs",
                    "description": "View recent critical journalctl error entries",
                    "command_preview": "journalctl -p 3 -xb",
                    "icon": "file-text",
                    "score_boost": 0.33,
                },
                {
                    "text": "Restart Nginx service",
                    "description": "Restart web server daemon",
                    "command_preview": "sudo systemctl restart nginx",
                    "icon": "refresh-cw",
                    "score_boost": 0.28,
                }
            ]
        },
        {
            "pattern": r"\b(open|launch|start|run|go to)\s+(browser|web|internet|chrome|firefox|brave|edge|google|youtube|github|site|website|url)\b|\b(browser|chrome|firefox|brave)\b",
            "suggestions": [
                {
                    "text": "Open web browser",
                    "description": "Launch default web browser window",
                    "command_preview": "xdg-open 'https://google.com'",
                    "icon": "globe",
                    "score_boost": 0.40,
                },
                {
                    "text": "Open Google Chrome",
                    "description": "Launch Google Chrome browser",
                    "command_preview": "google-chrome",
                    "icon": "globe",
                    "score_boost": 0.35,
                },
                {
                    "text": "Open Firefox",
                    "description": "Launch Mozilla Firefox browser",
                    "command_preview": "firefox",
                    "icon": "globe",
                    "score_boost": 0.35,
                },
                {
                    "text": "Open Brave browser",
                    "description": "Launch Brave web browser",
                    "command_preview": "brave",
                    "icon": "globe",
                    "score_boost": 0.35,
                }
            ]
        },
        {
            "pattern": r"\b(ports|listening ports|open ports|what ports|check ports|view ports)\b",
            "suggestions": [
                {
                    "text": "What ports are open",
                    "description": "Show all listening TCP and UDP sockets and associated processes",
                    "command_preview": "sudo ss -tulpn",
                    "icon": "radio",
                    "score_boost": 0.40,
                },
                {
                    "text": "Check active network connections",
                    "description": "Show established network sockets and remote endpoints",
                    "command_preview": "ss -ta",
                    "icon": "wifi",
                    "score_boost": 0.35,
                }
            ]
        },
        {
            "pattern": r"\b(terminal|console|editor|code|vscode|files|file manager|explorer)\b",
            "suggestions": [
                {
                    "text": "Open terminal",
                    "description": "Launch terminal emulator window",
                    "command_preview": "alacritty || kitty || x-terminal-emulator",
                    "icon": "terminal",
                    "score_boost": 0.35,
                },
                {
                    "text": "Open text editor",
                    "description": "Open code editor in current directory",
                    "command_preview": "code . || gedit || nano",
                    "icon": "edit",
                    "score_boost": 0.35,
                },
                {
                    "text": "Open file manager",
                    "description": "Open graphical file manager in current directory",
                    "command_preview": "xdg-open .",
                    "icon": "folder",
                    "score_boost": 0.35,
                }
            ]
        },
    ]

    def __init__(
        self,
        history_db: Optional[HistoryDatabase] = None,
        installed_tools_cache_ttl: float = 60.0
    ):
        self.history_db = history_db or get_history_db()
        self._installed_tools_cache_ttl = installed_tools_cache_ttl
        self._cached_installed_tools: Set[str] = set()
        self._installed_tools_cached_at: float = 0.0

        # Fast in-memory query result cache
        self._suggestion_cache: Dict[str, Tuple[float, List[Suggestion]]] = {}
        self._cache_ttl: float = 3.0

    def get_installed_tools(self) -> Set[str]:
        """Returns cached set of detected command-line binaries on host."""
        now = time.time()
        if self._cached_installed_tools and (now - self._installed_tools_cached_at) < self._installed_tools_cache_ttl:
            return self._cached_installed_tools

        tools_to_check = [
            "docker", "git", "nginx", "apache2", "postgresql", "mysql", "redis-server",
            "python3", "python", "node", "npm", "cargo", "go", "ufw", "iptables",
            "systemctl", "journalctl", "htop", "top", "tmux", "curl", "wget",
            "ansible", "terraform", "kubectl", "code", "hyprctl", "playerctl"
        ]
        installed = set()
        for tool in tools_to_check:
            if shutil.which(tool):
                installed.add(tool)

        self._cached_installed_tools = installed
        self._installed_tools_cached_at = now
        return installed

    def get_project_context_suggestions(self, cwd: str) -> List[Suggestion]:
        """Inspects project files in working directory to generate contextual suggestions."""
        suggestions: List[Suggestion] = []
        try:
            cwd_path = Path(cwd).expanduser().resolve()
            if not cwd_path.exists() or not cwd_path.is_dir():
                return suggestions

            has_package_json = (cwd_path / "package.json").exists()
            has_requirements = (cwd_path / "requirements.txt").exists() or (cwd_path / "pyproject.toml").exists()
            has_cargo = (cwd_path / "Cargo.toml").exists()
            has_go = (cwd_path / "go.mod").exists()
            has_docker = (cwd_path / "Dockerfile").exists() or (cwd_path / "docker-compose.yml").exists()
            has_git = (cwd_path / ".git").exists()
            has_makefile = (cwd_path / "Makefile").exists()

            if has_package_json:
                suggestions.append(Suggestion(
                    text="Install Node.js dependencies",
                    category="project",
                    description="Run `npm install` for detected package.json",
                    score=0.92,
                    command_preview="npm install",
                    icon="package"
                ))
                suggestions.append(Suggestion(
                    text="Run project test suite",
                    category="project",
                    description="Run `npm test` in current project",
                    score=0.85,
                    command_preview="npm test",
                    icon="check-circle"
                ))

            if has_requirements:
                suggestions.append(Suggestion(
                    text="Install Python packages",
                    category="project",
                    description="Install packages from requirements.txt",
                    score=0.93,
                    command_preview="pip install -r requirements.txt",
                    icon="package"
                ))
                suggestions.append(Suggestion(
                    text="Create Python virtual environment",
                    category="project",
                    description="Create isolated .venv in current project",
                    score=0.90,
                    command_preview="python3 -m venv .venv",
                    icon="code"
                ))
                suggestions.append(Suggestion(
                    text="Run project test suite",
                    category="project",
                    description="Run pytest suite for Python project",
                    score=0.86,
                    command_preview="pytest",
                    icon="check-circle"
                ))

            if has_cargo:
                suggestions.append(Suggestion(
                    text="Build Rust project",
                    category="project",
                    description="Compile Rust project with `cargo build`",
                    score=0.90,
                    command_preview="cargo build",
                    icon="cpu"
                ))
                suggestions.append(Suggestion(
                    text="Run cargo test",
                    category="project",
                    description="Execute Rust tests with `cargo test`",
                    score=0.85,
                    command_preview="cargo test",
                    icon="check-circle"
                ))

            if has_go:
                suggestions.append(Suggestion(
                    text="Download Go modules",
                    category="project",
                    description="Run `go mod download` for current Go project",
                    score=0.90,
                    command_preview="go mod download",
                    icon="package"
                ))

            if has_docker:
                suggestions.append(Suggestion(
                    text="Build Docker image",
                    category="project",
                    description="Build container image from local Dockerfile",
                    score=0.88,
                    command_preview="docker build -t app .",
                    icon="box"
                ))

            if has_git:
                suggestions.append(Suggestion(
                    text="Check git status",
                    category="project",
                    description="Inspect branch, staged files, and modified files",
                    score=0.87,
                    command_preview="git status",
                    icon="git-branch"
                ))
                suggestions.append(Suggestion(
                    text="Show recent git commits",
                    category="project",
                    description="Display recent commit log",
                    score=0.82,
                    command_preview="git log --oneline -n 10",
                    icon="git-commit"
                ))

            if has_makefile:
                suggestions.append(Suggestion(
                    text="Run make build",
                    category="project",
                    description="Execute default target from Makefile",
                    score=0.83,
                    command_preview="make",
                    icon="terminal"
                ))

        except Exception:
            pass

        return suggestions

    def get_cwd_suggestions(self, cwd: str, query: str) -> List[Suggestion]:
        """Provides directory-aware suggestions (e.g. Downloads, Desktop, or file matching)."""
        suggestions: List[Suggestion] = []
        try:
            cwd_path = Path(cwd).expanduser().resolve()
            dir_name = cwd_path.name.lower()

            if "download" in dir_name:
                suggestions.append(Suggestion(
                    text="Organize my Downloads folder",
                    category="cwd",
                    description="Sort downloaded files into Images, Docs, Archives",
                    score=0.95,
                    command_preview="Organize ~/Downloads",
                    icon="folder"
                ))
                suggestions.append(Suggestion(
                    text="Find large files",
                    category="cwd",
                    description="Find largest files taking up space in Downloads",
                    score=0.88,
                    command_preview="find . -type f -size +50M",
                    icon="hard-drive"
                ))

            if "desktop" in dir_name:
                suggestions.append(Suggestion(
                    text="Organize desktop files",
                    category="cwd",
                    description="Clean up loose files on Desktop",
                    score=0.95,
                    command_preview="Organize ~/Desktop",
                    icon="folder"
                ))

            # If user query begins with file action verbs, suggest local files in cwd
            q_lower = query.lower().strip()
            file_match = re.match(r"^(?:edit|show|open|cat|view|read|delete|trash|rm)\s+(.*)$", q_lower)
            if file_match and cwd_path.exists():
                prefix = file_match.group(1).strip()
                count = 0
                for item in cwd_path.iterdir():
                    if item.name.startswith("."):
                        continue
                    if not prefix or prefix in item.name.lower():
                        verb = query.strip().split()[0].capitalize()
                        suggestions.append(Suggestion(
                            text=f"{verb} {item.name}",
                            category="cwd",
                            description=f"Perform action on local {'directory' if item.is_dir() else 'file'}",
                            score=0.80,
                            command_preview=f"xdg-open '{item.name}'" if item.is_dir() else f"cat '{item.name}'",
                            icon="folder" if item.is_dir() else "file-text"
                        ))
                        count += 1
                        if count >= 3:
                            break
        except Exception:
            pass

        return suggestions

    def get_history_suggestions(self, query: str, limit: int = 5) -> List[Suggestion]:
        """Retrieves matching past queries from persistent SQLite history database."""
        suggestions: List[Suggestion] = []
        if not self.history_db:
            return suggestions

        try:
            q_clean = query.strip().lower()
            recent_rows = self.history_db.get_recent_history(limit=50)
            seen_texts: Set[str] = set()

            for row in recent_rows:
                h_query = (row.get("query") or "").strip()
                if not h_query or h_query.lower() in seen_texts:
                    continue

                h_lower = h_query.lower()
                # Check if it matches query
                if not q_clean or q_clean in h_lower:
                    seen_texts.add(h_lower)
                    suggestions.append(Suggestion(
                        text=h_query,
                        category="history",
                        description=f"Previous request • {row.get('intent') or 'executed'}",
                        score=0.89 if q_clean and h_lower.startswith(q_clean) else 0.78,
                        command_preview=row.get("command"),
                        icon="clock"
                    ))
                    if len(suggestions) >= limit:
                        break
        except Exception:
            pass

        return suggestions

    def calculate_highlight_ranges(self, text: str, query: str) -> List[Tuple[int, int]]:
        """Calculates substring match ranges [start_idx, end_idx] for UI highlight."""
        if not query or not text:
            return []

        ranges: List[Tuple[int, int]] = []
        text_lower = text.lower()
        query_lower = query.lower().strip()

        # 1. Exact query match
        start = text_lower.find(query_lower)
        if start != -1:
            return [(start, start + len(query_lower))]

        # 2. Match individual tokens
        tokens = query_lower.split()
        for tok in tokens:
            if not tok:
                continue
            idx = 0
            while True:
                pos = text_lower.find(tok, idx)
                if pos == -1:
                    break
                ranges.append((pos, pos + len(tok)))
                idx = pos + len(tok)

        # Merge overlapping ranges
        if not ranges:
            return []

        ranges.sort(key=lambda r: r[0])
        merged: List[Tuple[int, int]] = [ranges[0]]
        for curr in ranges[1:]:
            prev = merged[-1]
            if curr[0] <= prev[1]:
                merged[-1] = (prev[0], max(prev[1], curr[1]))
            else:
                merged.append(curr)

        return merged

    def score_match(self, item: Dict[str, Any], query: str, installed_tools: Set[str]) -> Tuple[float, List[Tuple[int, int]]]:
        """Calculates relevance score and highlight ranges for a candidate item."""
        text = item["text"]
        text_lower = text.lower()
        q_lower = query.lower().strip()

        if not q_lower:
            # Default ranking
            return item.get("score", 0.5), []

        highlights = self.calculate_highlight_ranges(text, query)

        # 1. Exact full match
        if text_lower == q_lower:
            return 1.0, [(0, len(text))]

        # 2. Exact prefix match (e.g. 'inst' -> 'Install project dependencies')
        if text_lower.startswith(q_lower):
            score = 0.95 - (len(text) - len(q_lower)) * 0.002
            return max(score, 0.70), [(0, len(q_lower))]

        # 3. Word-boundary prefix match (e.g. 'disk' -> 'Check disk usage')
        words = text_lower.split()
        for w in words:
            if w.startswith(q_lower):
                score = 0.88
                return score, highlights

        # 4. Substring match
        if q_lower in text_lower:
            return 0.82, highlights

        # 5. Keyword match
        keywords = item.get("keywords", [])
        matched_kws = [kw for kw in keywords if q_lower in kw or kw.startswith(q_lower)]
        if matched_kws:
            score = 0.75 + min(len(matched_kws) * 0.05, 0.15)
            # Boost if tool is installed
            for kw in keywords:
                if kw in installed_tools:
                    score += 0.05
                    break
            return min(score, 0.92), highlights

        # 6. Multi-token partial overlap with strict keyword validation
        tokens = [t for t in q_lower.split() if t]
        if len(tokens) > 1:
            STOPWORDS = {"a", "an", "the", "is", "are", "in", "on", "to", "for", "of", "and", "my", "what", "how", "why"}
            meaningful_tokens = [t for t in tokens if t not in STOPWORDS] or tokens
            candidate_words = text_lower.split()

            matched_meaningful = 0
            for tok in meaningful_tokens:
                if any(w.startswith(tok) or tok in w for w in candidate_words) or any(tok in kw for kw in keywords):
                    matched_meaningful += 1

            if matched_meaningful == len(meaningful_tokens):
                score = 0.94 if text_lower.startswith(tokens[0]) else 0.88
                return score, highlights
            elif len(meaningful_tokens) >= 3 and matched_meaningful >= len(meaningful_tokens) - 1:
                return 0.65, highlights
            else:
                return 0.0, []

        return 0.0, []

    def get_action_intent_suggestions(self, query: str, cwd: str) -> List[Suggestion]:
        """Generates dynamic on-the-fly suggestions when typing action requests."""
        suggestions: List[Suggestion] = []
        q = query.strip()
        if not q or len(q) < 2:
            return suggestions

        q_lower = q.lower()
        parts = q_lower.split(maxsplit=1)
        verb = parts[0]
        target = parts[1].strip() if len(parts) > 1 else ""

        # 1. Opening apps, browsers, URLs, and folders
        if verb in ("open", "launch", "start", "run", "go"):
            if not target:
                suggestions.append(Suggestion(
                    text="Open web browser",
                    category="smart_intent",
                    description="Launch default web browser (Chrome, Firefox, Brave)",
                    score=0.92,
                    command_preview="xdg-open 'https://google.com'",
                    icon="globe",
                    highlight_ranges=self.calculate_highlight_ranges("Open web browser", q)
                ))
                suggestions.append(Suggestion(
                    text="Open terminal",
                    category="smart_intent",
                    description="Launch new terminal emulator window",
                    score=0.90,
                    command_preview="alacritty || kitty || x-terminal-emulator",
                    icon="terminal",
                    highlight_ranges=self.calculate_highlight_ranges("Open terminal", q)
                ))
                suggestions.append(Suggestion(
                    text="Open Downloads folder",
                    category="smart_intent",
                    description="Open ~/Downloads in file manager",
                    score=0.88,
                    command_preview="xdg-open ~/Downloads",
                    icon="folder",
                    highlight_ranges=self.calculate_highlight_ranges("Open Downloads folder", q)
                ))
            elif any(b in target for b in ("browser", "web", "internet", "chrome", "firefox", "brave", "edge", "google")):
                suggestions.append(Suggestion(
                    text="Open web browser",
                    category="smart_intent",
                    description="Launch default web browser",
                    score=0.96,
                    command_preview="xdg-open 'https://google.com'",
                    icon="globe",
                    highlight_ranges=self.calculate_highlight_ranges("Open web browser", q)
                ))
                suggestions.append(Suggestion(
                    text="Open Google Chrome",
                    category="smart_intent",
                    description="Launch Google Chrome",
                    score=0.92,
                    command_preview="google-chrome",
                    icon="globe",
                    highlight_ranges=self.calculate_highlight_ranges("Open Google Chrome", q)
                ))
                suggestions.append(Suggestion(
                    text="Open Firefox",
                    category="smart_intent",
                    description="Launch Mozilla Firefox",
                    score=0.91,
                    command_preview="firefox",
                    icon="globe",
                    highlight_ranges=self.calculate_highlight_ranges("Open Firefox", q)
                ))
                suggestions.append(Suggestion(
                    text="Open Brave browser",
                    category="smart_intent",
                    description="Launch Brave web browser",
                    score=0.90,
                    command_preview="brave",
                    icon="globe",
                    highlight_ranges=self.calculate_highlight_ranges("Open Brave browser", q)
                ))
            elif any(t in target for t in ("term", "console", "shell", "kitty", "alacritty")):
                suggestions.append(Suggestion(
                    text="Open terminal",
                    category="smart_intent",
                    description="Launch terminal emulator",
                    score=0.95,
                    command_preview="alacritty || kitty || x-terminal-emulator",
                    icon="terminal",
                    highlight_ranges=self.calculate_highlight_ranges("Open terminal", q)
                ))
            elif any(f in target for f in ("folder", "dir", "downloads", "documents", "desktop", "files")):
                target_title = target.title()
                suggestions.append(Suggestion(
                    text=f"Open {target_title} folder",
                    category="smart_intent",
                    description=f"Open ~/{target_title} in graphical file manager",
                    score=0.94,
                    command_preview=f"xdg-open '~/{target_title}'",
                    icon="folder",
                    highlight_ranges=self.calculate_highlight_ranges(f"Open {target_title} folder", q)
                ))

        # 2. Ports & Network Connections
        elif any(p in q_lower for p in ("port", "ports", "listening", "sockets", "ss", "connections")):
            suggestions.append(Suggestion(
                text="What ports are open",
                category="smart_intent",
                description="Show all listening TCP and UDP sockets and associated processes",
                score=0.95,
                command_preview="sudo ss -tulpn",
                icon="radio",
                highlight_ranges=self.calculate_highlight_ranges("What ports are open", q)
            ))
            suggestions.append(Suggestion(
                text="Check active network connections",
                category="smart_intent",
                description="Show established connections and remote endpoints",
                score=0.90,
                command_preview="ss -ta",
                icon="wifi",
                highlight_ranges=self.calculate_highlight_ranges("Check active network connections", q)
            ))

        # 3. Installing packages
        elif verb in ("install", "setup", "get", "add") and target:
            suggestions.append(Suggestion(
                text=f"Install {target}",
                category="smart_intent",
                description=f"Install package '{target}' via system package manager",
                score=0.93,
                command_preview=f"sudo pacman -S {target} / sudo apt install {target}",
                icon="package",
                highlight_ranges=self.calculate_highlight_ranges(f"Install {target}", q)
            ))

        # 4. Restarting / stopping services
        elif verb in ("restart", "reload", "stop", "start") and target:
            suggestions.append(Suggestion(
                text=f"{verb.capitalize()} {target} service",
                category="smart_intent",
                description=f"{verb.capitalize()} systemd service unit '{target}'",
                score=0.93,
                command_preview=f"sudo systemctl {verb} {target}",
                icon="refresh-cw",
                highlight_ranges=self.calculate_highlight_ranges(f"{verb.capitalize()} {target} service", q)
            ))

        # 5. Killing / terminating processes
        elif verb in ("kill", "terminate", "stop") and target:
            suggestions.append(Suggestion(
                text=f"Kill {target} process",
                category="smart_intent",
                description=f"Terminate all background processes matching '{target}'",
                score=0.93,
                command_preview=f"pkill -f {target}",
                icon="alert-circle",
                highlight_ranges=self.calculate_highlight_ranges(f"Kill {target} process", q)
            ))

        return suggestions

    def suggest(
        self,
        query: str = "",
        cwd: Optional[str] = None,
        max_results: int = 8
    ) -> List[Suggestion]:
        """
        Generate intelligent, real-time natural language auto-complete suggestions.

        Args:
            query: The partial text entered by the user.
            cwd: Optional current working directory context.
            max_results: Maximum number of suggestions to return (typically 5-8).

        Returns:
            List of Suggestion objects sorted by relevance score.
        """
        active_cwd = cwd or os.getcwd()
        q_trimmed = query.strip()
        cache_key = f"{q_trimmed}::{active_cwd}::{max_results}"

        now = time.time()
        if cache_key in self._suggestion_cache:
            ts, cached_suggs = self._suggestion_cache[cache_key]
            if (now - ts) < self._cache_ttl:
                return cached_suggs

        installed_tools = self.get_installed_tools()
        candidates: List[Suggestion] = []
        seen_texts: Set[str] = set()

        def _add_candidate(sugg: Suggestion):
            norm = sugg.text.strip().lower()
            if norm in seen_texts:
                return
            seen_texts.add(norm)
            candidates.append(sugg)

        # 1. Check Dynamic Action Intent Generator
        if q_trimmed:
            action_suggs = self.get_action_intent_suggestions(q_trimmed, active_cwd)
            for as_sugg in action_suggs:
                _add_candidate(as_sugg)

        # 1. Check Smart Intent / Semantic Heuristics First
        if q_trimmed:
            for rule in self.SMART_INTENT_PATTERNS:
                if re.search(rule["pattern"], q_trimmed, re.IGNORECASE):
                    for s_data in rule["suggestions"]:
                        text = s_data["text"]
                        highlights = self.calculate_highlight_ranges(text, q_trimmed)
                        base_score = 0.85 + s_data.get("score_boost", 0.1)
                        _add_candidate(Suggestion(
                            text=text,
                            category="smart_intent",
                            description=s_data["description"],
                            score=min(base_score, 0.99),
                            command_preview=s_data.get("command_preview"),
                            icon=s_data.get("icon", "zap"),
                            highlight_ranges=highlights
                        ))

        # 2. Check Project Context
        project_suggs = self.get_project_context_suggestions(active_cwd)
        for ps in project_suggs:
            score, highlights = self.score_match(
                {"text": ps.text, "keywords": ps.text.lower().split()},
                q_trimmed,
                installed_tools
            )
            if not q_trimmed or score > 0.4:
                ps.score = max(ps.score, score + 0.05 if q_trimmed else ps.score)
                ps.highlight_ranges = highlights
                _add_candidate(ps)

        # 3. Check CWD & Local Files Context
        cwd_suggs = self.get_cwd_suggestions(active_cwd, q_trimmed)
        for cs in cwd_suggs:
            score, highlights = self.score_match(
                {"text": cs.text, "keywords": cs.text.lower().split()},
                q_trimmed,
                installed_tools
            )
            if not q_trimmed or score > 0.4:
                cs.score = max(cs.score, score)
                cs.highlight_ranges = highlights
                _add_candidate(cs)

        # 4. Check Core Linux Tasks
        for task in self.CORE_LINUX_TASKS:
            score, highlights = self.score_match(task, q_trimmed, installed_tools)
            if not q_trimmed:
                # When empty, show high priority curated tasks
                _add_candidate(Suggestion(
                    text=task["text"],
                    category=task["category"],
                    description=task["description"],
                    score=0.75,
                    command_preview=task.get("command_preview"),
                    icon=task.get("icon", "terminal"),
                    highlight_ranges=[]
                ))
            elif score > 0.45:
                _add_candidate(Suggestion(
                    text=task["text"],
                    category=task["category"],
                    description=task["description"],
                    score=score,
                    command_preview=task.get("command_preview"),
                    icon=task.get("icon", "terminal"),
                    highlight_ranges=highlights
                ))

        # 5. Check History Database
        if q_trimmed:
            hist_suggs = self.get_history_suggestions(q_trimmed, limit=3)
            for hs in hist_suggs:
                hs.highlight_ranges = self.calculate_highlight_ranges(hs.text, q_trimmed)
                _add_candidate(hs)

        # Sort candidates descending by score
        candidates.sort(key=lambda s: s.score, reverse=True)
        results = candidates[:max_results]

        # Cache result
        self._suggestion_cache[cache_key] = (now, results)
        return results


# Global singleton instance
_engine_instance: Optional[AutocompleteEngine] = None


def get_autocomplete_engine() -> AutocompleteEngine:
    """Returns global AutocompleteEngine singleton."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AutocompleteEngine()
    return _engine_instance

"""
Synonym and Phrase Normalization Dictionary for LinuxOpsAssistant.

Maps diverse English, Hinglish, and conversational phrasing to standard Linux
operations across 12 core domains.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple


class SynonymDictionary:
    """Provides conversational synonym matching and normalization."""

    # Category synonym tables
    CPU_PATTERNS = [
        r"\b(?:cpu|processor|core|cpu\s+load|processor\s+busy|cpu\s+usage|cpu\s+activity)\b",
        r"\b(?:how\s+much\s+cpu|is\s+my\s+processor\s+busy|check\s+processor|tell\s+me\s+cpu)\b",
        r"\b(?:cpu\s+load\s+batao|processor\s+check\s+karo)\b",
    ]

    RAM_PATTERNS = [
        r"\b(?:ram|memory|swap|physical\s+memory|free\s+memory|used\s+memory|memory\s+usage)\b",
        r"\b(?:how\s+much\s+ram|how\s+much\s+memory|ram\s+left|check\s+memory)\b",
        r"\b(?:memory\s+kitni\s+bachi\s+hai|ram\s+dikhao)\b",
    ]

    DISK_PATTERNS = [
        r"\b(?:disk|storage|hard\s+drive|space|hdd|ssd|filesystem|free\s+space|disk\s+usage)\b",
        r"\b(?:how\s+much\s+disk|disk\s+full|out\s+of\s+space|storage\s+space|check\s+storage)\b",
        r"\b(?:storage\s+kitna\s+hai|disk\s+space\s+dikhao)\b",
    ]

    DELETE_VERBS = [
        "delete", "remove", "erase", "trash", "purge", "destroy", "wipe", "clean up",
        "hatao", "mitao", "ura do", "delete karo", "clear"
    ]

    CREATE_VERBS = [
        "create", "make", "new", "generate", "build", "touch", "add", "banao", "create karo"
    ]

    OPEN_VERBS = [
        "open", "launch", "start", "view", "browse", "run", "kholo", "chalu karo", "shuru karo"
    ]

    STOP_VERBS = [
        "stop", "kill", "terminate", "halt", "end", "pause", "band karo", "rok do"
    ]

    RESTART_VERBS = [
        "restart", "reboot", "reload", "refresh", "respawn", "phir se chalu karo"
    ]

    SEARCH_VERBS = [
        "search", "find", "locate", "look for", "where is", "dhundo", "search karo", "grep"
    ]

    INSTALL_VERBS = [
        "install", "download and install", "setup", "get", "add package", "install karo"
    ]

    PERMISSION_VERBS = [
        "chmod", "chown", "make executable", "give execute permission", "permission badlo", "runnable banao"
    ]

    COMPRESS_VERBS = [
        "compress", "tar", "zip", "archive", "pack", "compress karo"
    ]

    EXTRACT_VERBS = [
        "extract", "untar", "unzip", "decompress", "unpack", "kholo"
    ]

    # Domain Classification Categories
    CATEGORIES: Dict[str, List[str]] = {
        "File Management": [
            "create folder", "delete file", "move file", "copy file", "empty trash",
            "compress archive", "extract zip", "organize downloads", "chmod", "chown"
        ],
        "System Monitoring": [
            "cpu usage", "ram memory", "disk storage", "system uptime", "hardware temperature",
            "psi pressure stall", "system health check"
        ],
        "Networking": [
            "ip address", "open ports", "ping test", "dns lookup", "network routing",
            "firewall status", "curl http request"
        ],
        "Package Management": [
            "install package", "remove package", "update system", "search package",
            "clean package cache", "autoremove unused dependencies"
        ],
        "Process Management": [
            "list processes", "kill process", "top cpu hogs", "fuser port conflict",
            "renice priority", "systemd service status"
        ],
        "Search & Discovery": [
            "find files", "grep log errors", "locate large files", "find python scripts",
            "search directory"
        ],
        "Browser & Desktop Control": [
            "open browser", "open website", "launch application", "open file manager",
            "play media"
        ],
        "Development & Git Tools": [
            "git status", "git commit", "git pull", "git push", "git branch",
            "git log", "run tests"
        ],
        "Docker & Containers": [
            "docker ps", "docker images", "docker compose up", "docker logs",
            "docker prune", "restart container"
        ],
        "Python & Environment": [
            "create venv", "run python script", "pip install", "pytest test suite"
        ],
        "General Linux Commands": [
            "whoami", "show environment variables", "reboot system", "shutdown machine",
            "kernel dmesg", "cron jobs"
        ]
    }

    @classmethod
    def normalize_query_intent(cls, query: str) -> Tuple[str, float]:
        """
        Detects primary semantic intention from diverse phrasings.
        Returns: (normalized_category, confidence)
        """
        q = query.lower().strip()

        # CPU
        for p in cls.CPU_PATTERNS:
            if re.search(p, q, re.IGNORECASE):
                return "System Monitoring (CPU)", 0.95

        # RAM
        for p in cls.RAM_PATTERNS:
            if re.search(p, q, re.IGNORECASE):
                return "System Monitoring (RAM)", 0.95

        # Disk
        for p in cls.DISK_PATTERNS:
            if re.search(p, q, re.IGNORECASE):
                return "System Monitoring (Disk)", 0.95

        # Git
        if re.search(r"\bgit\s+(?:status|commit|push|pull|branch|log|diff|checkout|fetch)\b", q, re.IGNORECASE):
            return "Development & Git Tools", 0.95

        # Docker
        if re.search(r"\bdocker\b", q, re.IGNORECASE):
            return "Docker & Containers", 0.95

        # Networking
        if re.search(r"\b(?:ip|ping|dns|port|ports|firewall|ufw|iptables|curl|ifconfig)\b", q, re.IGNORECASE):
            return "Networking", 0.90

        # Package
        if re.search(r"\b(?:pacman|apt|apt-get|dnf|yum|apk|zypper|install\s+package|upgrade\s+system)\b", q, re.IGNORECASE):
            return "Package Management", 0.95

        # Files
        if re.search(r"\b(?:folder|file|directory|documents|downloads|pdf|move|copy|delete|trash)\b", q, re.IGNORECASE):
            return "File Management", 0.90

        return "General Linux Commands", 0.70

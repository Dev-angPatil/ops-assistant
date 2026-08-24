"""
Fuzzy Entity Matching & Spell Correction Engine for LinuxOpsAssistant.

Provides Damerau-Levenshtein distance and SymSpell (Symmetric Delete) lookup
against active Linux system entities:
  - Installed packages (dpkg/rpm/pacman/apk + fallback index)
  - Active & installed systemd units/services
  - Mounted filesystem paths (/proc/mounts, findmnt, df)
  - Active network interfaces (/sys/class/net, ip link)
  - System operations vocabulary (restart, check, status, install, etc.)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any


def damerau_levenshtein_distance(s1: str, s2: str) -> int:
    """
    Computes Damerau-Levenshtein distance between s1 and s2,
    supporting insertions, deletions, substitutions, and transpositions of adjacent characters.
    """
    if s1 == s2:
        return 0
    len1, len2 = len(s1), len(s2)
    if not len1:
        return len2
    if not len2:
        return len1

    # Matrix initialization
    d = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(len1 + 1):
        d[i][0] = i
    for j in range(len2 + 1):
        d[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,        # Deletion
                d[i][j - 1] + 1,        # Insertion
                d[i - 1][j - 1] + cost  # Substitution
            )
            if i > 1 and j > 1 and s1[i - 1] == s2[j - 2] and s1[i - 2] == s2[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + cost)  # Transposition

    return d[len1][len2]


class SymSpellMatcher:
    """
    Symmetric Delete (SymSpell) fast spell correction engine.
    Generates delete variants up to max_edit_distance for O(1)/O(k) candidate lookup.
    """

    def __init__(self, max_edit_distance: int = 2):
        self.max_edit_distance = max_edit_distance
        self.words: Set[str] = set()
        self.deletes: Dict[str, Set[str]] = {}
        self.word_categories: Dict[str, str] = {}  # word -> category

    def _get_deletes(self, word: str, distance: int) -> Set[str]:
        """Generates delete variants up to specified distance."""
        results: Set[str] = set()
        queue: Set[str] = {word}
        for d in range(distance):
            next_queue: Set[str] = set()
            for w in queue:
                if len(w) > 1:
                    for i in range(len(w)):
                        del_var = w[:i] + w[i + 1:]
                        if del_var not in results:
                            results.add(del_var)
                            next_queue.add(del_var)
            queue = next_queue
        return results

    def add_word(self, word: str, category: str = "general") -> None:
        """Adds a single word to the SymSpell index."""
        w_lower = word.lower().strip()
        if not w_lower or w_lower in self.words:
            return

        self.words.add(w_lower)
        self.word_categories[w_lower] = category

        # Add delete variants
        del_vars = self._get_deletes(w_lower, self.max_edit_distance)
        for dv in del_vars:
            if dv not in self.deletes:
                self.deletes[dv] = set()
            self.deletes[dv].add(w_lower)

    def add_words(self, words: List[str], category: str = "general") -> None:
        """Adds multiple words to the index."""
        for w in words:
            self.add_word(w, category)

    def lookup(self, token: str, max_distance: Optional[int] = None) -> List[Tuple[str, int, str]]:
        """
        Looks up candidates for a given token.
        Returns list of tuples: (candidate_word, distance, category), sorted by distance and length similarity.
        """
        t_lower = token.lower().strip()
        if not t_lower:
            return []

        if t_lower in self.words:
            return [(t_lower, 0, self.word_categories.get(t_lower, "general"))]

        max_d = max_distance if max_distance is not None else self.max_edit_distance
        candidates: Dict[str, int] = {}

        # 1. Direct deletes of input token
        token_deletes = self._get_deletes(t_lower, max_d)
        token_deletes.add(t_lower)

        matched_words: Set[str] = set()

        for td in token_deletes:
            if td in self.deletes:
                matched_words.update(self.deletes[td])
            if td in self.words:
                matched_words.add(td)

        # 2. Compute exact Damerau-Levenshtein distance for matched candidates
        for cand in matched_words:
            if abs(len(cand) - len(t_lower)) > max_d:
                continue
            dist = damerau_levenshtein_distance(t_lower, cand)
            if dist <= max_d:
                candidates[cand] = dist

        def _cat_priority(w: str) -> int:
            cat = self.word_categories.get(w, "general")
            if cat == "ops_verb":
                return 0
            if cat in ("systemd_unit", "package"):
                return 1
            return 2

        # 3. Sort candidates by edit distance first, category priority second, length difference third
        sorted_candidates = sorted(
            candidates.items(),
            key=lambda item: (item[1], _cat_priority(item[0]), abs(len(item[0]) - len(t_lower)), item[0])
        )

        return [
            (w, d, self.word_categories.get(w, "general"))
            for w, d in sorted_candidates
        ]


class SystemEntityCollector:
    """Gathers active runtime system entities from live environment."""

    OPS_VOCABULARY = [
        # Ops action verbs & synonyms
        "restart", "start", "stop", "status", "check", "enable", "disable", "reload",
        "refresh", "install", "remove", "update", "upgrade", "show", "list", "ping",
        "kill", "terminate", "inspect", "clean", "organize", "mount", "unmount", "umount",
        "chmod", "chown", "create", "delete", "erase", "trash", "touch", "open", "launch",
        "find", "search", "locate", "grep", "view", "tail", "reboot", "shutdown", "fetch",
        "make", "build", "run", "get", "set", "add", "move", "copy", "read", "write",
        "scan", "trim", "prune", "vacuum", "saved", "save", "restore", "backup", "recommend",
        "tune", "analyze", "analyse", "audit", "download", "health", "explore", "display",
        "schedule", "scheduled", "allow", "deny", "block", "permit", "organise", "tidy", "sort",
        "info", "information", "version", "uptime", "sysinfo", "uname", "usage", "space",
        # Common English structure, conjunctions, prepositions & tech terms
        "inside", "into", "under", "with", "content", "text", "all", "one", "new", "as",
        "to", "from", "for", "of", "in", "on", "by", "is", "are", "it", "this", "that",
        "my", "your", "me", "you", "please", "can", "could", "would", "should", "how",
        "what", "where", "why", "when", "which", "who", "name", "named", "called", "url",
        "http", "https", "and", "or", "not", "if", "else", "then", "an", "a", "the",
        "saved", "unused", "used", "free", "open", "closed", "active", "inactive", "failed",
        "system", "systems", "hardware", "specs", "model", "models", "gpu", "cpu", "ram",
        "ai", "bottleneck", "bottlenecks", "risk", "risks", "attack", "attacks", "brute",
        "force", "suid", "privilege", "escalation", "apt", "dnf", "yum", "pacman", "apk",
        "snap", "flatpak", "pip", "cache", "ssd", "hdd", "nvme", "boot", "time", "slow",
        "library", "libraries", "handle", "excel", "file", "files", "folder", "folders",
        "directory", "directories", "path", "paths", "myenv", "venv", "virtualenv",
        # Resource names, plurals, & system concepts
        "service", "services", "unit", "units", "daemon", "daemons", "package", "packages",
        "process", "processes", "port", "ports", "firewall", "firewalls", "rule", "rules",
        "network", "interface", "interfaces", "disk", "storage", "memory", "journal",
        "logs", "log", "config", "configuration", "systemctl", "journalctl", "ufw",
        "iptables", "docker", "podman", "container", "containers", "git", "branch",
        "commit", "push", "pull", "cron", "crontab", "backup", "backups", "restore",
        "ip", "address", "dns", "route", "curl", "wget", "whoami", "uptime", "top", "htop",
        "df", "free", "du", "ps", "ss", "netstat", "ifconfig", "user", "users", "project",
        "projects", "dependency", "dependencies", "requirement", "requirements", "detail", "details"
    ]

    COMMON_PACKAGES_FALLBACK = [
        "nginx", "apache2", "ufw", "openssh-server", "sshd", "curl", "wget", "git",
        "python3", "python", "docker", "docker-ce", "containerd", "redis", "postgresql",
        "mysql", "mariadb", "htop", "neofetch", "hyprland", "waybar", "pipewire",
        "wireplumber", "gcc", "make", "vim", "nano", "zsh", "bash", "tar", "unzip",
        "gzip", "rsync", "cron", "anacron", "iptables", "nftables", "fail2ban",
        "net-tools", "iproute2", "networkmanager", "systemd", "procps"
    ]

    COMMON_UNITS_FALLBACK = [
        "nginx", "nginx.service", "ufw", "ufw.service", "sshd", "sshd.service",
        "ssh", "ssh.service", "docker", "docker.service", "bluetooth", "bluetooth.service",
        "NetworkManager", "NetworkManager.service", "cron", "cron.service",
        "crond", "crond.service", "postgresql", "postgresql.service",
        "mysql", "mysql.service", "mariadb", "mariadb.service",
        "redis", "redis.service", "systemd-resolved", "systemd-resolved.service",
        "systemd-timesyncd", "systemd-timesyncd.service", "firewalld", "firewalld.service"
    ]

    COMMON_MOUNTS_FALLBACK = [
        "/", "/home", "/mnt", "/media", "/tmp", "/var", "/boot", "/etc", "/usr", "/opt",
        "/dev/sda1", "/dev/sdb1", "/dev/nvme0n1p1"
    ]

    COMMON_NET_INTERFACES_FALLBACK = [
        "lo", "eth0", "eth1", "wlan0", "wlan1", "enp3s0", "enp2s0", "wlp2s0", "docker0",
        "tun0", "br0", "virbr0"
    ]

    @classmethod
    def get_installed_packages(cls) -> List[str]:
        """Queries ground-truth installed packages or returns fallback list."""
        pkgs: Set[str] = set(cls.COMMON_PACKAGES_FALLBACK)
        try:
            if shutil.which("dpkg-query"):
                res = subprocess.run(
                    ["dpkg-query", "-W", "-f=${Package}\n"],
                    capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0 and res.stdout:
                    for line in res.stdout.splitlines():
                        line = line.strip()
                        if line:
                            pkgs.add(line)
            elif shutil.which("rpm"):
                res = subprocess.run(
                    ["rpm", "-qa", "--qf", "%{NAME}\n"],
                    capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0 and res.stdout:
                    for line in res.stdout.splitlines():
                        line = line.strip()
                        if line:
                            pkgs.add(line)
            elif shutil.which("pacman"):
                res = subprocess.run(
                    ["pacman", "-Qq"],
                    capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0 and res.stdout:
                    for line in res.stdout.splitlines():
                        line = line.strip()
                        if line:
                            pkgs.add(line)
            elif shutil.which("apk"):
                res = subprocess.run(
                    ["apk", "info"],
                    capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0 and res.stdout:
                    for line in res.stdout.splitlines():
                        line = line.strip()
                        if line:
                            pkgs.add(line)
        except Exception:
            pass

        return sorted(list(pkgs))

    @classmethod
    def get_systemd_units(cls) -> List[str]:
        """Queries running and active systemd units or returns fallback list."""
        units: Set[str] = set(cls.COMMON_UNITS_FALLBACK)
        try:
            if shutil.which("systemctl"):
                res = subprocess.run(
                    ["systemctl", "list-unit-files", "--no-legend", "--no-pager"],
                    capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0 and res.stdout:
                    for line in res.stdout.splitlines():
                        parts = line.split()
                        if parts:
                            u = parts[0].strip()
                            units.add(u)
                            if u.endswith(".service"):
                                units.add(u[:-8])
        except Exception:
            pass

        return sorted(list(units))

    @classmethod
    def get_mounted_paths(cls) -> List[str]:
        """Queries live mount points from /proc/mounts or df."""
        mounts: Set[str] = set(cls.COMMON_MOUNTS_FALLBACK)
        try:
            if os.path.exists("/proc/mounts"):
                with open("/proc/mounts", "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2:
                            m_path = parts[1].strip()
                            if m_path.startswith("/"):
                                mounts.add(m_path)
        except Exception:
            pass

        # Also add current directory files/folders
        try:
            cwd = os.getcwd()
            mounts.add(cwd)
            for entry in os.listdir(cwd):
                mounts.add(entry)
        except Exception:
            pass

        return sorted(list(mounts))

    @classmethod
    def get_network_interfaces(cls) -> List[str]:
        """Queries active network interfaces from /sys/class/net."""
        ifaces: Set[str] = set(cls.COMMON_NET_INTERFACES_FALLBACK)
        try:
            if os.path.exists("/sys/class/net"):
                for entry in os.listdir("/sys/class/net"):
                    ifaces.add(entry.strip())
        except Exception:
            pass

        return sorted(list(ifaces))


@dataclass
class CorrectionResult:
    """Result of spell correction and fuzzy entity matching on a query."""
    original_query: str
    corrected_query: str
    replacements: List[Tuple[str, str]] = field(default_factory=list)
    confidence: float = 1.0


class FuzzyEntityMatcher:
    """
    Fuzzy Entity Matcher & Spell Corrector.
    Uses SymSpell + Damerau-Levenshtein distance to correct typos in user queries
    against ops keywords and live system entities.
    """

    _instance: Optional[FuzzyEntityMatcher] = None

    def __init__(self, max_edit_distance: int = 2):
        self.matcher = SymSpellMatcher(max_edit_distance=max_edit_distance)
        self.initialized = False
        self._initialize_index()

    @classmethod
    def get_instance(cls) -> FuzzyEntityMatcher:
        """Singleton accessor for FuzzyEntityMatcher."""
        if cls._instance is None:
            cls._instance = FuzzyEntityMatcher()
        return cls._instance

    def _initialize_index(self) -> None:
        """Indexes ops vocabulary and ground-truth active system entities."""
        if self.initialized:
            return

        # 1. Ops Vocabulary
        self.matcher.add_words(SystemEntityCollector.OPS_VOCABULARY, category="ops_verb")

        # 2. Installed Packages
        packages = SystemEntityCollector.get_installed_packages()
        self.matcher.add_words(packages, category="package")

        # 3. Systemd Units
        units = SystemEntityCollector.get_systemd_units()
        self.matcher.add_words(units, category="systemd_unit")

        # 4. Mounted Paths & directories
        mounts = SystemEntityCollector.get_mounted_paths()
        # Filter for simple basename tokens for spell checking
        path_tokens = [m.rstrip("/").split("/")[-1] for m in mounts if m.rstrip("/").split("/")[-1]]
        self.matcher.add_words(path_tokens, category="mounted_path")

        # 5. Network Interfaces
        ifaces = SystemEntityCollector.get_network_interfaces()
        self.matcher.add_words(ifaces, category="net_interface")

        self.initialized = True

    def correct_token(self, token: str, category: Optional[str] = None) -> Tuple[str, int]:
        """
        Corrects a single word token if a close candidate exists within edit distance <= 2.
        Returns: (best_candidate_or_original, distance)
        """
        raw_token = token.strip()
        t_clean = raw_token.lower()

        # Do not correct numbers, URLs, paths starting with / or ./, flags (-f, --help)
        if not t_clean or t_clean.isdigit() or t_clean.startswith(("-", "/", "./", "~/", "http://", "https://")):
            return raw_token, 0

        # Don't touch short tokens (<=2 chars) unless exact match
        if len(t_clean) <= 2:
            return raw_token, 0

        # Exact match check (including singular/plural)
        if t_clean in self.matcher.words:
            return raw_token, 0
        if t_clean.endswith("s") and t_clean[:-1] in self.matcher.words:
            return raw_token, 0

        # Do not correct all-uppercase acronyms (DBMS, DSA, PDF, URL, IP)
        if raw_token.isupper() and len(raw_token) >= 2:
            return raw_token, 0

        # SymSpell candidate lookup
        candidates = self.matcher.lookup(t_clean, max_distance=2)
        if not candidates:
            return raw_token, 0

        best_word, dist, cand_cat = candidates[0]

        # Do not collapse 3+ letter tokens into 2-letter binary names (like ssd -> ss)
        if len(best_word) <= 2 and len(t_clean) >= 3:
            return raw_token, 0

        # Titlecased proper nouns (Divya, etc.): don't correct unless candidate is an ops_verb or dist <= 1
        if raw_token.istitle() and cand_cat != "ops_verb" and dist > 1:
            return raw_token, 0

        # Require len_diff <= 1 for dist <= 2
        if abs(len(best_word) - len(t_clean)) > 1:
            return raw_token, 0

        # Require dist <= 1 for short words (length <= 4)
        if len(t_clean) <= 4 and dist > 1:
            return raw_token, 0

        # If a category is requested, filter candidates
        if category and cand_cat != category:
            filtered = [c for c in candidates if c[2] == category]
            if filtered:
                best_word, dist, _ = filtered[0]
            else:
                if dist > 1:
                    return raw_token, 0

        # Preserve original capitalization style if uppercase/titlecase
        if raw_token.isupper():
            corrected = best_word.upper()
        elif raw_token.istitle():
            corrected = best_word.capitalize()
        else:
            corrected = best_word

        return corrected, dist

    def correct_query(self, query: str) -> CorrectionResult:
        """
        Corrects typos in natural language query using Damerau-Levenshtein / SymSpell matching.
        Example: "resatrt ngnx" -> "restart nginx", "ckick ufw stauts" -> "check ufw status"
        """
        raw_query = query.strip()
        if not raw_query:
            return CorrectionResult(raw_query, raw_query, [], 1.0)

        # Match tokens while preserving delimiters/spaces
        tokens = re.split(r"(\s+|[;|,|&|\|])", raw_query)
        corrected_tokens: List[str] = []
        replacements: List[Tuple[str, str]] = []

        for token in tokens:
            # If delimiter or empty, pass through
            if not token or re.match(r"^\s+$", token) or token in (";", ",", "&", "|"):
                corrected_tokens.append(token)
                continue

            # Attempt token correction
            corrected, dist = self.correct_token(token)
            if dist > 0 and corrected.lower() != token.lower():
                replacements.append((token, corrected))
                corrected_tokens.append(corrected)
            else:
                corrected_tokens.append(token)

        corrected_query = "".join(corrected_tokens)
        confidence = 1.0 - (0.05 * len(replacements))

        return CorrectionResult(
            original_query=raw_query,
            corrected_query=corrected_query,
            replacements=replacements,
            confidence=max(0.70, confidence)
        )

    def match_entity(self, term: str, category: Optional[str] = None) -> Optional[str]:
        """
        Matches a single entity term against system entities.
        Returns matched string or None.
        """
        corrected, dist = self.correct_token(term, category=category)
        if dist <= 2 and corrected.lower() != term.lower():
            return corrected
        if term.lower() in self.matcher.words:
            return term
        return None

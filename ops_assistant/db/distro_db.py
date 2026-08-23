"""Embedded SQLite Distro Knowledge Base for multi-distribution Linux operations."""

import os
import json
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "distro_knowledge.json"
DEFAULT_PACKS_DIR = Path(__file__).resolve().parent.parent / "data" / "packs"
DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "data" / "distro_prompts"
DEFAULT_DB_PATH = Path.home() / ".config" / "ops_assistant" / "distro_knowledge.db"


class DistroKnowledgeBase:
    """Manages the embedded SQLite database of Linux distribution specifications."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        data_source_path: Optional[str] = None,
        packs_dir: Optional[str] = None,
        target_distro: Optional[str] = None
    ):
        if db_path is None:
            self.db_path = str(DEFAULT_DB_PATH)
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        else:
            self.db_path = db_path
            if self.db_path != ":memory:":
                os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        self._lock = threading.Lock()
        self.data_source_path = str(data_source_path or DEFAULT_DATA_PATH)
        self.packs_dir = Path(packs_dir or DEFAULT_PACKS_DIR)
        self.target_distro = target_distro

        with self._lock:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            if self.db_path != ":memory:":
                try:
                    self.conn.execute("PRAGMA journal_mode=WAL;")
                    self.conn.execute("PRAGMA synchronous=NORMAL;")
                except Exception:
                    pass
            self._profiles_cache: Dict[str, Dict[str, Any]] = {}
            self._commands_cache: Dict[Tuple[str, str, str], str] = {}
            self._all_families_cache: Optional[List[str]] = None
            self._init_schema()
            self._seed_if_needed(target_distro=self.target_distro)

    def _init_schema(self) -> None:
        """Creates the required relational tables if they do not exist."""
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS distro_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS distro_profiles (
                family_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                os_release_ids TEXT NOT NULL,
                os_release_id_like TEXT NOT NULL,
                detection_file TEXT,
                init_system TEXT NOT NULL,
                default_firewall TEXT NOT NULL,
                security_subsystem TEXT NOT NULL,
                log_paths TEXT NOT NULL,
                network_config_paths TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS distro_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                family_id TEXT NOT NULL,
                category TEXT NOT NULL,
                action TEXT NOT NULL,
                command_template TEXT NOT NULL,
                FOREIGN KEY (family_id) REFERENCES distro_profiles(family_id),
                UNIQUE(family_id, category, action)
            );

            CREATE TABLE IF NOT EXISTS distro_locks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                family_id TEXT NOT NULL,
                lock_file TEXT NOT NULL,
                lock_processes TEXT NOT NULL,
                FOREIGN KEY (family_id) REFERENCES distro_profiles(family_id)
            );

            CREATE TABLE IF NOT EXISTS distro_error_signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                family_id TEXT NOT NULL,
                signature_id TEXT NOT NULL,
                pattern TEXT NOT NULL,
                remediation TEXT NOT NULL,
                explanation TEXT NOT NULL,
                FOREIGN KEY (family_id) REFERENCES distro_profiles(family_id),
                UNIQUE(family_id, signature_id)
            );

            CREATE TABLE IF NOT EXISTS distro_quirks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                family_id TEXT NOT NULL,
                quirk_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                do_not_do TEXT NOT NULL,
                FOREIGN KEY (family_id) REFERENCES distro_profiles(family_id),
                UNIQUE(family_id, quirk_id)
            );

            CREATE TABLE IF NOT EXISTS distro_filesystem (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                family_id TEXT NOT NULL,
                path_key TEXT NOT NULL,
                path_value TEXT NOT NULL,
                description TEXT NOT NULL,
                FOREIGN KEY (family_id) REFERENCES distro_profiles(family_id),
                UNIQUE(family_id, path_key)
            );

            CREATE TABLE IF NOT EXISTS desktop_ecosystems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ecosystem_id TEXT NOT NULL,
                category TEXT NOT NULL,
                topic TEXT NOT NULL,
                command_syntax TEXT NOT NULL,
                description TEXT NOT NULL,
                wiki_url TEXT,
                UNIQUE(ecosystem_id, category, topic)
            );
        """)
        self.conn.commit()

    def _seed_if_needed(self, target_distro: Optional[str] = None) -> None:
        """Seeds the database from packs directory or JSON if empty or outdated."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM distro_profiles")
        count = cursor.fetchone()[0]

        cursor.execute("SELECT value FROM distro_meta WHERE key = 'data_version'")
        row = cursor.fetchone()
        db_version = row[0] if row else None

        # Check if packs directory exists
        if self.packs_dir.exists() and any(self.packs_dir.iterdir()):
            if count == 0 or db_version != "2.0.0":
                pack_to_seed = target_distro or "all"
                self.seed_distro_packs(pack_to_seed)
        elif os.path.exists(self.data_source_path):
            if count == 0 or db_version != "2.0.0":
                self.seed_from_json(self.data_source_path)

        # Always seed desktop ecosystems (Hyprland, HyDE, Wayland, Audio)
        self._seed_desktop_ecosystems()

    def seed_distro_packs(self, family_id: str = "all") -> None:
        """Seeds the database from modular pack folders in ops_assistant/data/packs/."""
        self._profiles_cache.clear()
        self._commands_cache.clear()
        self._all_families_cache = None

        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM distro_profiles")
        cursor.execute("DELETE FROM distro_commands")
        cursor.execute("DELETE FROM distro_locks")
        cursor.execute("DELETE FROM distro_error_signatures")
        cursor.execute("DELETE FROM distro_quirks")
        cursor.execute("DELETE FROM distro_filesystem")
        cursor.execute("INSERT OR REPLACE INTO distro_meta (key, value) VALUES ('data_version', '2.0.0')")
        cursor.execute("INSERT OR REPLACE INTO distro_meta (key, value) VALUES ('pack_mode', ?)", (family_id,))

        # 1. Seed Base Linux Core Pack
        base_dir = self.packs_dir / "base"
        if base_dir.exists():
            self._seed_base_pack(base_dir, cursor)

        # 2. Determine target families to load
        available = self.list_available_packs()
        if family_id == "all":
            targets = available
        else:
            # Match family or normalized alias
            matched = self._normalize_family_target(family_id, available)
            targets = [matched] if matched else available

        for fid in targets:
            f_dir = self.packs_dir / fid
            if f_dir.exists() and f_dir.is_dir():
                self._seed_single_pack(fid, f_dir, cursor)

        self.conn.commit()

    def _seed_base_pack(self, base_dir: Path, cursor: sqlite3.Cursor) -> None:
        """Seeds common Linux core commands, signatures, and paths under 'base'."""
        # Base commands
        cmds_file = base_dir / "commands.json"
        if cmds_file.exists():
            try:
                with open(cmds_file, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                category = cdata.get("category", "base")
                for action, cmd in cdata.get("commands", {}).items():
                    cursor.execute("""
                        INSERT OR REPLACE INTO distro_commands (family_id, category, action, command_template)
                        VALUES ('base', ?, ?, ?)
                    """, (category, action, cmd))
            except Exception:
                pass

        # Base error signatures
        sigs_file = base_dir / "signatures.json"
        if sigs_file.exists():
            try:
                with open(sigs_file, "r", encoding="utf-8") as f:
                    sigs = json.load(f)
                for s in sigs:
                    cursor.execute("""
                        INSERT OR REPLACE INTO distro_error_signatures (
                            family_id, signature_id, pattern, remediation, explanation
                        ) VALUES ('base', ?, ?, ?, ?)
                    """, (
                        s.get("id", "BASE_ERR"),
                        s.get("pattern", ""),
                        s.get("remediation", ""),
                        s.get("explanation", "")
                    ))
            except Exception:
                pass

        # Base filesystem paths
        paths_file = base_dir / "paths.json"
        if paths_file.exists():
            try:
                with open(paths_file, "r", encoding="utf-8") as f:
                    pdata = json.load(f)
                for pkey, pval in pdata.items():
                    cursor.execute("""
                        INSERT OR REPLACE INTO distro_filesystem (family_id, path_key, path_value, description)
                        VALUES ('base', ?, ?, 'Base Linux POSIX path')
                    """, (pkey, str(pval)))
            except Exception:
                pass

    def _seed_single_pack(self, fid: str, f_dir: Path, cursor: sqlite3.Cursor) -> None:
        """Seeds a single distribution pack from its folder."""
        # 1. Profile
        prof_file = f_dir / "profile.json"
        if prof_file.exists():
            with open(prof_file, "r", encoding="utf-8") as f:
                prof = json.load(f)
            ident = prof.get("identification", {})
            cursor.execute("""
                INSERT OR REPLACE INTO distro_profiles (
                    family_id, display_name, os_release_ids, os_release_id_like,
                    detection_file, init_system, default_firewall, security_subsystem,
                    log_paths, network_config_paths
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fid,
                prof.get("display_name", fid),
                json.dumps(ident.get("os_release_ids", [fid])),
                json.dumps(ident.get("os_release_id_like", [])),
                ident.get("detection_file"),
                prof.get("init_system", "systemd"),
                prof.get("default_firewall", "iptables"),
                prof.get("security_subsystem", "none"),
                json.dumps(prof.get("log_paths", {})),
                json.dumps(prof.get("network_config_paths", []))
            ))

        # 2. Commands
        cmds_file = f_dir / "commands.json"
        if cmds_file.exists():
            with open(cmds_file, "r", encoding="utf-8") as f:
                cmds_data = json.load(f)
            for cat_name, actions in cmds_data.items():
                for action, cmd in actions.items():
                    cursor.execute("""
                        INSERT OR REPLACE INTO distro_commands (family_id, category, action, command_template)
                        VALUES (?, ?, ?, ?)
                    """, (fid, cat_name, action, cmd))

        # 3. Locks
        locks_file = f_dir / "locks.json"
        if locks_file.exists():
            with open(locks_file, "r", encoding="utf-8") as f:
                locks_data = json.load(f)
            for lfile in locks_data.get("lock_files", []):
                cursor.execute("""
                    INSERT INTO distro_locks (family_id, lock_file, lock_processes)
                    VALUES (?, ?, ?)
                """, (fid, lfile, json.dumps(locks_data.get("lock_processes", []))))

        # 4. Signatures
        sigs_file = f_dir / "signatures.json"
        if sigs_file.exists():
            with open(sigs_file, "r", encoding="utf-8") as f:
                sigs = json.load(f)
            for s in sigs:
                cursor.execute("""
                    INSERT OR REPLACE INTO distro_error_signatures (
                        family_id, signature_id, pattern, remediation, explanation
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    fid,
                    s.get("id", s.get("pattern", "UNKNOWN")),
                    s.get("pattern", ""),
                    s.get("remediation", ""),
                    s.get("explanation", "")
                ))

        # 5. Quirks
        quirks_file = f_dir / "quirks.json"
        if quirks_file.exists():
            with open(quirks_file, "r", encoding="utf-8") as f:
                quirks = json.load(f)
            for q in quirks:
                cursor.execute("""
                    INSERT OR REPLACE INTO distro_quirks (
                        family_id, quirk_id, title, description, recommendation, do_not_do
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    fid,
                    q.get("quirk_id", "UNKNOWN"),
                    q.get("title", ""),
                    q.get("description", ""),
                    q.get("recommendation", ""),
                    q.get("do_not_do", "")
                ))

        # 6. Filesystem Paths
        paths_file = f_dir / "paths.json"
        if paths_file.exists():
            with open(paths_file, "r", encoding="utf-8") as f:
                fs_paths = json.load(f)
            for pkey, pval in fs_paths.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO distro_filesystem (family_id, path_key, path_value, description)
                    VALUES (?, ?, ?, ?)
                """, (fid, pkey, str(pval), f"Path for {pkey} on {fid}"))

    def _normalize_family_target(self, target: str, available: List[str]) -> Optional[str]:
        t = target.lower().strip()
        if t in available:
            return t
        aliases = {
            "ubuntu": "debian", "linuxmint": "debian", "pop": "debian", "kali": "debian", "boss": "debian", "bossos": "debian",
            "centos": "rhel", "rocky": "rhel", "almalinux": "rhel", "fedora": "rhel", "ol": "rhel", "amzn": "rhel",
            "manjaro": "arch", "endeavouros": "arch", "garuda": "arch",
            "opensuse": "suse", "opensuse-leap": "suse", "opensuse-tumbleweed": "suse", "sles": "suse"
        }
        return aliases.get(t)

    def seed_from_json(self, json_path: str) -> None:
        """Loads and populates tables from a legacy single JSON file."""
        self._profiles_cache.clear()
        self._commands_cache.clear()
        self._all_families_cache = None

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        version = data.get("version", "1.0.0")
        updated_at = data.get("updated_at", "")
        families = data.get("families", {})
        cursor = self.conn.cursor()

        cursor.execute("INSERT OR REPLACE INTO distro_meta (key, value) VALUES ('data_version', ?)", (version,))
        cursor.execute("INSERT OR REPLACE INTO distro_meta (key, value) VALUES ('updated_at', ?)", (updated_at,))

        for fid, finfo in families.items():
            ident = finfo.get("identification", {})
            svc = finfo.get("service_manager", {})
            pkg = finfo.get("package_manager", {})
            fw = finfo.get("firewall", {})
            sec = finfo.get("security_subsystem", {})
            log_paths = finfo.get("log_paths", {})
            net_paths = finfo.get("network_config_paths", [])

            cursor.execute("""
                INSERT OR REPLACE INTO distro_profiles (
                    family_id, display_name, os_release_ids, os_release_id_like,
                    detection_file, init_system, default_firewall, security_subsystem,
                    log_paths, network_config_paths
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fid,
                finfo.get("display_name", fid),
                json.dumps(ident.get("os_release_ids", [])),
                json.dumps(ident.get("os_release_id_like", [])),
                ident.get("detection_file"),
                finfo.get("init_system", "systemd"),
                fw.get("default_tool", "iptables"),
                sec.get("type", "none"),
                json.dumps(log_paths),
                json.dumps(net_paths)
            ))

            # Commands
            for cat_key, cat_val in finfo.items():
                if isinstance(cat_val, dict) and "commands" in cat_val:
                    category_name = cat_key.replace("_manager", "").replace("_subsystem", "")
                    for action, cmd in cat_val.get("commands", {}).items():
                        cursor.execute("""
                            INSERT OR REPLACE INTO distro_commands (family_id, category, action, command_template)
                            VALUES (?, ?, ?, ?)
                        """, (fid, category_name, action, cmd))

            # Locks
            for lfile in pkg.get("lock_files", []):
                cursor.execute("""
                    INSERT INTO distro_locks (family_id, lock_file, lock_processes)
                    VALUES (?, ?, ?)
                """, (fid, lfile, json.dumps(pkg.get("lock_processes", []))))

            # Signatures
            for sig in finfo.get("common_error_signatures", []):
                cursor.execute("""
                    INSERT OR REPLACE INTO distro_error_signatures (
                        family_id, signature_id, pattern, remediation, explanation
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    fid,
                    sig.get("id", sig.get("pattern", "UNKNOWN")),
                    sig.get("pattern", ""),
                    sig.get("remediation", ""),
                    sig.get("explanation", "")
                ))

            # Quirks
            for quirk in finfo.get("quirks_and_gotchas", []):
                cursor.execute("""
                    INSERT OR REPLACE INTO distro_quirks (
                        family_id, quirk_id, title, description, recommendation, do_not_do
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    fid,
                    quirk.get("quirk_id", "UNKNOWN"),
                    quirk.get("title", ""),
                    quirk.get("description", ""),
                    quirk.get("recommendation", ""),
                    quirk.get("do_not_do", "")
                ))

            # Paths
            fs_paths = finfo.get("filesystem_paths", {})
            for pkey, pval in fs_paths.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO distro_filesystem (family_id, path_key, path_value, description)
                    VALUES (?, ?, ?, ?)
                """, (fid, pkey, str(pval), f"Path for {pkey} on {fid}"))

        self.conn.commit()

    def list_installed_packs(self) -> List[str]:
        """Returns the list of distribution family IDs currently seeded in SQLite."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT family_id FROM distro_profiles")
            return [row[0] for row in cursor.fetchall()]

    def list_available_packs(self) -> List[str]:
        """Scans the packs directory and returns all available distro pack IDs."""
        if not self.packs_dir.exists():
            return ["debian", "rhel", "arch", "alpine", "suse"]
        packs = []
        for p in self.packs_dir.iterdir():
            if p.is_dir() and p.name != "base" and (p / "profile.json").exists():
                packs.append(p.name)
        return sorted(packs) if packs else ["debian", "rhel", "arch", "alpine", "suse"]

    def add_pack(self, family_id: str) -> bool:
        """Dynamically loads and seeds an additional distro pack into SQLite."""
        with self._lock:
            matched = self._normalize_family_target(family_id, self.list_available_packs())
            if not matched:
                return False
            f_dir = self.packs_dir / matched
            if not f_dir.exists():
                return False

            cursor = self.conn.cursor()
            self._seed_single_pack(matched, f_dir, cursor)
            self.conn.commit()
            self._profiles_cache.clear()
            self._commands_cache.clear()
            self._all_families_cache = None
            return True

    def remove_pack(self, family_id: str) -> bool:
        """Removes a distro pack from the SQLite database."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM distro_profiles WHERE family_id = ?", (family_id,))
            cursor.execute("DELETE FROM distro_commands WHERE family_id = ?", (family_id,))
            cursor.execute("DELETE FROM distro_locks WHERE family_id = ?", (family_id,))
            cursor.execute("DELETE FROM distro_error_signatures WHERE family_id = ?", (family_id,))
            cursor.execute("DELETE FROM distro_quirks WHERE family_id = ?", (family_id,))
            cursor.execute("DELETE FROM distro_filesystem WHERE family_id = ?", (family_id,))
            self.conn.commit()
            self._profiles_cache.clear()
            self._commands_cache.clear()
            self._all_families_cache = None
            return True

    def get_profile(self, family_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves profile configuration for a given distribution family with memory caching."""
        with self._lock:
            if family_id in self._profiles_cache:
                return self._profiles_cache[family_id]

            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM distro_profiles WHERE family_id = ?", (family_id,))
            row = cursor.fetchone()
            if not row:
                return None
            profile = {
                "family_id": row["family_id"],
                "display_name": row["display_name"],
                "os_release_ids": json.loads(row["os_release_ids"]),
                "os_release_id_like": json.loads(row["os_release_id_like"]),
                "detection_file": row["detection_file"],
                "init_system": row["init_system"],
                "default_firewall": row["default_firewall"],
                "security_subsystem": row["security_subsystem"],
                "log_paths": json.loads(row["log_paths"]),
                "network_config_paths": json.loads(row["network_config_paths"])
            }
            self._profiles_cache[family_id] = profile
            return profile

    def get_all_families(self) -> List[str]:
        """Returns all supported distribution family IDs currently installed."""
        with self._lock:
            if self._all_families_cache is not None:
                return self._all_families_cache

            cursor = self.conn.cursor()
            cursor.execute("SELECT family_id FROM distro_profiles")
            self._all_families_cache = [row[0] for row in cursor.fetchall()]
            return self._all_families_cache

    def get_command(
        self,
        family_id: str,
        category: str,
        action: str,
        **kwargs: Any
    ) -> Optional[str]:
        """Resolves a parameterized command template for a distro family with caching (falls back to 'base')."""
        with self._lock:
            cache_key = (family_id, category, action)
            if cache_key in self._commands_cache:
                template = self._commands_cache[cache_key]
            else:
                cursor = self.conn.cursor()
                cursor.execute("""
                    SELECT command_template FROM distro_commands
                    WHERE family_id = ? AND category = ? AND action = ?
                """, (family_id, category, action))
                row = cursor.fetchone()
                if not row:
                    # Fallback to base category
                    cursor.execute("""
                        SELECT command_template FROM distro_commands
                        WHERE family_id = 'base' AND (category = ? OR category = 'base') AND action = ?
                    """, (category, action))
                    row = cursor.fetchone()
                    if not row:
                        return None
                template = row[0]
                self._commands_cache[cache_key] = template

            if kwargs:
                try:
                    return template.format(**kwargs)
                except KeyError:
                    return template
            return template

    def get_commands_by_category(self, family_id: str, category: str) -> Dict[str, str]:
        """Returns all available command templates for a specific category in a distro family."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT action, command_template FROM distro_commands
                WHERE family_id = ? AND category = ?
            """, (family_id, category))
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_locks(self, family_id: str) -> List[Dict[str, Any]]:
        """Returns all package manager lock files and competing processes for a distro."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT lock_file, lock_processes FROM distro_locks WHERE family_id = ?", (family_id,))
            rows = cursor.fetchall()
            return [
                {"lock_file": r[0], "lock_processes": json.loads(r[1])}
                for r in rows
            ]

    def get_error_signatures(self, family_id: str) -> List[Dict[str, Any]]:
        """Returns common error patterns and remediations for a distro family and base core."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT signature_id, pattern, remediation, explanation
                FROM distro_error_signatures WHERE family_id = ? OR family_id = 'base'
            """, (family_id,))
            rows = cursor.fetchall()
            return [
                {
                    "id": r["signature_id"],
                    "pattern": r["pattern"],
                    "remediation": r["remediation"],
                    "explanation": r["explanation"]
                }
                for r in rows
            ]

    def get_quirks(self, family_id: str) -> List[Dict[str, Any]]:
        """Returns distro-specific behavioral quirks, recommendations, and anti-patterns."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT quirk_id, title, description, recommendation, do_not_do
                FROM distro_quirks WHERE family_id = ?
            """, (family_id,))
            rows = cursor.fetchall()
            return [
                {
                    "quirk_id": r["quirk_id"],
                    "title": r["title"],
                    "description": r["description"],
                    "recommendation": r["recommendation"],
                    "do_not_do": r["do_not_do"]
                }
                for r in rows
            ]

    def get_filesystem_paths(self, family_id: str) -> Dict[str, str]:
        """Returns key configuration and system filesystem paths for a distro family."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT path_key, path_value FROM distro_filesystem WHERE family_id = ? OR family_id = 'base'", (family_id,))
            return {r[0]: r[1] for r in cursor.fetchall()}

    def get_log_paths(self, family_id: str) -> Dict[str, str]:
        """Returns the dictionary of log paths for the distro family."""
        profile = self.get_profile(family_id)
        if profile:
            return profile.get("log_paths", {})
        return {
            "system": "/var/log/syslog",
            "auth": "/var/log/auth.log",
            "package_manager": "/var/log/dpkg.log",
            "kernel": "/var/log/kern.log"
        }

    def get_distro_prompt_context(self, family_id: str) -> str:
        """Returns rich markdown system prompt context for LLM grounding for the given distro family."""
        # 1. Check pack prompt.md
        pack_prompt = self.packs_dir / family_id / "prompt.md"
        if pack_prompt.exists():
            try:
                with open(pack_prompt, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass

        # 2. Check legacy prompt directory
        prompt_file = DEFAULT_PROMPTS_DIR / f"{family_id}.md"
        if prompt_file.exists():
            try:
                with open(prompt_file, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass

        # 3. Fallback: synthesize context from database
        profile = self.get_profile(family_id)
        if not profile:
            return f"Distribution: {family_id} (Standard Linux environment)."

        quirks = self.get_quirks(family_id)
        fs = self.get_filesystem_paths(family_id)

        lines = [
            f"# Distribution Environment: {profile['display_name']} ({family_id})",
            f"- **Init System**: {profile['init_system']}",
            f"- **Firewall**: {profile['default_firewall']}",
            f"- **Security Subsystem**: {profile['security_subsystem']}",
            "",
            "## Key Filesystem Paths:"
        ]
        for k, v in fs.items():
            lines.append(f"- `{k}`: `{v}`")

        if quirks:
            lines.append("\n## Distribution Quirks & Rules:")
            for q in quirks:
                lines.append(f"- **{q['title']}**: {q['recommendation']} (Never: {q['do_not_do']})")

        return "\n".join(lines)

    def _seed_desktop_ecosystems(self) -> None:
        """Seeds rich operational knowledge for desktop environments, HyDE, Wayland, and PipeWire."""
        ecosystems_data = [
            # Hyprland Ecosystem
            ("hyprland", "workspace", "switch_workspace", "hyprctl dispatch workspace <ID>", "Switches the active focused workspace to workspace number ID.", "https://wiki.hyprland.org/Configuring/Dispatchers/"),
            ("hyprland", "workspace", "move_to_workspace", "hyprctl dispatch movetoworkspace <ID>", "Moves currently focused window to workspace ID.", "https://wiki.hyprland.org/Configuring/Dispatchers/"),
            ("hyprland", "window", "kill_active", "hyprctl dispatch killactive", "Closes or kills the currently focused window.", "https://wiki.hyprland.org/Configuring/Dispatchers/"),
            ("hyprland", "window", "toggle_floating", "hyprctl dispatch togglefloating", "Toggles floating mode for the currently active window.", "https://wiki.hyprland.org/Configuring/Dispatchers/"),
            ("hyprland", "window", "fullscreen", "hyprctl dispatch fullscreen 1", "Toggles fullscreen mode for the active window.", "https://wiki.hyprland.org/Configuring/Dispatchers/"),
            ("hyprland", "system", "reload_config", "hyprctl reload", "Instantly reloads Hyprland configuration without restarting session.", "https://wiki.hyprland.org/Configuring/Using-hyprctl/"),
            ("hyprland", "system", "list_monitors", "hyprctl monitors", "Displays connected display outputs, resolutions, and refresh rates.", "https://wiki.hyprland.org/Configuring/Monitors/"),
            ("hyprland", "system", "list_windows", "hyprctl clients", "Lists all active open windows, workspaces, and process IDs.", "https://wiki.hyprland.org/Configuring/Using-hyprctl/"),
            ("hyprland", "wallpaper", "set_hyprpaper", "hyprctl hyprpaper preload '<path>' && hyprctl hyprpaper wallpaper ',<path>'", "Preloads and applies wallpaper image via hyprpaper IPC.", "https://wiki.hyprland.org/Hypr-Ecosystem/hyprpaper/"),

            # HyDE Theme Framework
            ("hyde", "theme", "theme_switch", "~/.config/hypr/themes", "HyDE dynamic theme directory for switching global color palettes and assets.", "https://github.com/HyDE-Project/HyDE"),
            ("hyde", "wallpaper", "wallpaper_picker", "waypaper", "Interactive graphical wallpaper picker integrated with HyDE Material You palette generation.", "https://github.com/HyDE-Project/HyDE"),
            ("hyde", "styling", "matugen_theme", "matugen image '<path>'", "Extracts Material You colors from wallpaper and themes Waybar, Rofi, and GTK.", "https://github.com/InioX/matugen"),
            ("hyde", "bar", "reload_waybar", "killall -SIGUSR2 waybar", "Sends reload signal to Waybar to refresh styling and layout modules.", "https://github.com/HyDE-Project/HyDE"),
            ("hyde", "launcher", "app_menu", "rofi -show drun", "Opens HyDE theme application launcher.", "https://github.com/HyDE-Project/HyDE"),
            ("hyde", "shortcuts", "default_keybinds", "Super+Q: Terminal | Super+W: Wallpaper | Super+C: Close | Super+E: Files | Super+Space: Menu", "Primary default keybindings in HyDE environment.", "https://github.com/HyDE-Project/HyDE"),

            # Wayland Core Tools
            ("wayland_core", "clipboard", "copy_text", "wl-copy < '<file>'", "Copies file content or stdin stream into Wayland system clipboard.", "https://wayland.freedesktop.org/"),
            ("wayland_core", "clipboard", "paste_text", "wl-paste", "Outputs current text content stored in Wayland clipboard.", "https://wayland.freedesktop.org/"),
            ("wayland_core", "screenshot", "region_screenshot", "grim -g \"$(slurp)\" ~/Pictures/Screenshots/screenshot_$(date +%Y%m%d_%H%M%S).png", "Captures an interactive region selection and saves to Screenshots directory.", "https://github.com/emersion/grim"),
            ("wayland_core", "screenshot", "full_screenshot", "grim ~/Pictures/Screenshots/screenshot_$(date +%Y%m%d_%H%M%S).png", "Captures full screen and saves to user Screenshots directory.", "https://github.com/emersion/grim"),
            ("wayland_core", "color_picker", "pick_color", "hyprpicker -a", "Launches magnifier color picker and automatically copies hex value to clipboard.", "https://github.com/hyprwm/hyprpicker"),

            # Audio & PipeWire
            ("audio_pipewire", "volume", "increase_volume", "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+", "Increases default audio output volume by 5%.", "https://pipewire.org/"),
            ("audio_pipewire", "volume", "decrease_volume", "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-", "Decreases default audio output volume by 5%.", "https://pipewire.org/"),
            ("audio_pipewire", "volume", "toggle_mute", "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle", "Toggles mute status for the active default audio output sink.", "https://pipewire.org/"),
            ("audio_pipewire", "status", "inspect_nodes", "wpctl status", "Lists active audio endpoints, volume levels, and bluetooth sink connections.", "https://pipewire.org/"),
        ]

        cursor = self.conn.cursor()
        for eco_id, cat, topic, syntax, desc, wiki in ecosystems_data:
            cursor.execute("""
                INSERT OR REPLACE INTO desktop_ecosystems (ecosystem_id, category, topic, command_syntax, description, wiki_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (eco_id, cat, topic, syntax, desc, wiki))
        self.conn.commit()

    def get_desktop_ecosystem_context(self, ecosystem_id: str) -> List[Dict[str, Any]]:
        """Returns all registered topics and operational commands for a desktop ecosystem."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM desktop_ecosystems WHERE ecosystem_id = ? ORDER BY category, topic", (ecosystem_id,))
        return [dict(row) for row in cursor.fetchall()]

    def list_desktop_ecosystems(self) -> List[str]:
        """Lists distinct registered desktop ecosystems in the knowledge base."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT ecosystem_id FROM desktop_ecosystems ORDER BY ecosystem_id")
        return [row[0] for row in cursor.fetchall()]

    def search_desktop_ecosystems(self, query: str) -> List[Dict[str, Any]]:
        """Searches desktop ecosystem operational commands and documentation."""
        cursor = self.conn.cursor()
        pattern = f"%{query}%"
        cursor.execute("""
            SELECT * FROM desktop_ecosystems
            WHERE ecosystem_id LIKE ? OR category LIKE ? OR topic LIKE ? OR description LIKE ? OR command_syntax LIKE ?
            ORDER BY ecosystem_id, category
        """, (pattern, pattern, pattern, pattern, pattern))
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Closes the underlying SQLite database connection."""
        with self._lock:
            self.conn.close()

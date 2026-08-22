"""ReAct Autonomous Agent Core Loop for Linux Operations & Diagnostics."""

import os
import re
import time
import json
from typing import Dict, Any, List, Optional, Tuple, Union

from ops_assistant.models import (
    DiagnosticReport, XAIExplanation, SystemHealthSnapshot, SafetyLevel, LogRecord
)
from ops_assistant.collectors.hub import TelemetryHub
from ops_assistant.collectors.distro_detector import DistroDetector, DistroInfo
from ops_assistant.db.distro_db import DistroKnowledgeBase
from ops_assistant.explainer.xai import XAIExplainer, CommandExplainer, ErrorExplainer
from ops_assistant.explainer.causality_dag import CausalityDAGEngine, CausalityGraphResult
from ops_assistant.tools.safety import CommandSafetyValidator
from ops_assistant.tools.sandbox_probe import EphemeralSandboxProbe
from ops_assistant.tools.executor import SafeExecutor
from ops_assistant.agent.tools_registry import AgentToolsRegistry
from ops_assistant.agent.providers import (
    LLMProvider, GeminiProvider, OllamaProvider, LlamaCppProvider
)


class ReActAgent:
    """
    Autonomous ReAct (Reason + Act) Agent for Linux Operations.
    Observes real system state via tools, reasons over live evidence,
    constructs dynamic causality graphs, and delivers safety-gated remediation.
    """

    COMMON_SERVICES = [
        "nginx", "apache2", "docker", "postgres", "postgresql", "mysql",
        "redis", "systemd-resolved", "ssh", "sshd", "kubelet", "cron", "named",
        "chrony", "timesyncd", "ufw", "iptables", "firewalld"
    ]

    # Baseline taxonomy knowledge for deterministic edge / air-gapped fast path
    DETERMINISTIC_PATTERNS = [
        {
            "id": "PORT_CONFLICT",
            "pattern": r"(Address already in use|bind\(\) to .* failed|port \d+ already in use|EADDRINUSE)",
            "tool_to_run": "inspect_listening_ports",
            "symptom": "Service failed to bind to target TCP/UDP socket.",
            "root_cause": "The configured listening port is already bound by another active process.",
            "commands": [
                ("sudo ss -tulpn | grep -E ':(80|443|8080|5432|3306|6379|22)'", SafetyLevel.READ_ONLY, 0.05, "Inspect which PID currently holds the listening port descriptor."),
                ("sudo systemctl status {service}", SafetyLevel.READ_ONLY, 0.05, "Inspect systemd unit exit status and error journal slice.")
            ],
            "rationale": "Socket collisions prevent daemons from starting. You must either terminate the colliding process or reconfigure the service port."
        },
        {
            "id": "PERMISSION_DENIED",
            "pattern": r"(Permission denied|EACCES|Failed to open .*: Permission denied|could not open directory|access denied for user)",
            "tool_to_run": "query_system_logs",
            "symptom": "File, socket or path access blocked by filesystem permissions.",
            "root_cause": "The service process user does not possess POSIX read/write permissions for the designated path.",
            "commands": [
                ("ls -la /var/log/{service} /etc/{service}", SafetyLevel.READ_ONLY, 0.05, "Check user, group, and mode bits on service paths."),
                ("sudo chown -R {service}:{service} /var/log/{service}", SafetyLevel.MODIFYING, 0.40, "Restore expected service ownership to log directory.")
            ],
            "rationale": "Daemon processes dropped privileges to service accounts (e.g. www-data, postgres) and cannot access root-owned paths."
        },
        {
            "id": "OOM_KILL",
            "pattern": r"(Out of memory|Killed process \d+|oom-killer|invoked oom-killer|fatal error: runtime: out of memory|Memory cgroup out of memory)",
            "tool_to_run": "inspect_processes",
            "symptom": "Process terminated by Linux kernel Out-of-Memory (OOM) killer.",
            "root_cause": "Linux kernel Out-of-Memory (OOM) killer terminated the process due to exhausted system RAM + Swap or exceeded cgroup memory limit.",
            "commands": [
                ("free -h", SafetyLevel.READ_ONLY, 0.05, "Check current physical RAM and swap partition availability."),
                ("ps aux --sort=-%mem | head -n 10", SafetyLevel.READ_ONLY, 0.05, "Identify the top 10 memory-consuming processes."),
                ("dmesg -T --level=err,crit | tail -n 20", SafetyLevel.READ_ONLY, 0.05, "Inspect exact kernel OOM invocation logs and killed process PIDs.")
            ],
            "rationale": "Kernel killed the process to prevent an unrecoverable kernel panic when page allocation failed."
        },
        {
            "id": "DISK_EXHAUSTION",
            "pattern": r"(No space left on device|ENOSPC|disk full|write error: No space)",
            "tool_to_run": "inspect_disk_and_inodes",
            "symptom": "Disk write failure due to 0 remaining blocks or exhausted partition capacity.",
            "root_cause": "Target partition has exhausted available physical disk blocks.",
            "commands": [
                ("df -h", SafetyLevel.READ_ONLY, 0.05, "Verify disk partition block utilization across all mounts."),
                ("sudo du -sh /var/log/* /var/tmp/* /tmp/* 2>/dev/null | sort -rh | head -n 10", SafetyLevel.READ_ONLY, 0.05, "Pinpoint the largest log or temp files consuming disk space."),
                ("sudo journalctl --vacuum-size=200M", SafetyLevel.MODIFYING, 0.30, "Vacuum older systemd journal logs to reclaim disk space.")
            ],
            "rationale": "Logging, cache, or database write failed because the filesystem cannot allocate additional extents."
        },
        {
            "id": "INODE_EXHAUSTION",
            "pattern": r"(No space left on device: inode|cannot create directory: No space|out of inodes|structure needs cleaning)",
            "tool_to_run": "inspect_disk_and_inodes",
            "symptom": "Filesystem metadata exhaustion (0 available inodes despite free block space).",
            "root_cause": "Target filesystem inode allocation table has zero remaining entries due to millions of micro-files or session caches.",
            "commands": [
                ("df -i", SafetyLevel.READ_ONLY, 0.05, "Verify inode allocation table availability across all mounted partitions."),
                ("sudo find /var/spool /tmp /var/tmp -xdev -printf '%h\n' | sort | uniq -c | sort -k 1 -n | tail -n 10", SafetyLevel.READ_ONLY, 0.05, "Pinpoint directory trees hoarding excessive file counts.")
            ],
            "rationale": "Every file requires an inode entry; massive collections of tiny session files deplete inodes while disk blocks appear free."
        },
        {
            "id": "CONFIG_SYNTAX_ERROR",
            "pattern": r"(syntax error|directive .* is not allowed here|unknown directive|Configuration file .* test failed|failed to parse|invalid configuration)",
            "tool_to_run": "run_read_only_command",
            "symptom": "Service configuration file parsing error.",
            "root_cause": "Syntax error, missing closing bracket, or unsupported directive in service configuration file.",
            "commands": [
                ("sudo nginx -t", SafetyLevel.READ_ONLY, 0.05, "Test NGINX configuration syntax and line numbers."),
                ("sudo journalctl -u {service} -n 30 --no-pager", SafetyLevel.READ_ONLY, 0.05, "View recent daemon config parser error messages.")
            ],
            "rationale": "Daemon aborts initialization before binding sockets when syntax validation fails."
        },
        {
            "id": "SSL_CERT_ERROR",
            "pattern": r"(certificate has expired|SSL_ERROR_SSL|certificate verify failed|certificate signed by unknown authority|certificate expired|SSL handshake failed|SSL routines:.*:certificate)",
            "tool_to_run": "query_system_logs",
            "symptom": "TLS handshake failure due to expired, mismatched, or untrusted SSL/TLS certificate.",
            "root_cause": "The active SSL/TLS X.509 certificate passed its Not-After expiration date or lacks valid intermediate CA chains.",
            "commands": [
                ("openssl x509 -enddate -noout -in /etc/ssl/certs/ssl-cert-snakeoil.pem", SafetyLevel.READ_ONLY, 0.05, "Check exact expiry timestamp of local SSL certificate."),
                ("sudo certbot certificates", SafetyLevel.READ_ONLY, 0.05, "Audit status of all Let's Encrypt managed SSL certificates."),
                ("sudo certbot renew --dry-run", SafetyLevel.READ_ONLY, 0.05, "Test automatic TLS certificate renewal pipeline.")
            ],
            "rationale": "Modern clients terminate TLS connections immediately upon encountering expired or invalid certificate chains."
        },
        {
            "id": "DNS_RESOLUTION_FAILURE",
            "pattern": r"(Temporary failure in name resolution|Could not resolve host|EAI_NONAME|Name or service not known|nameserver failure|systemd-resolved.*failed)",
            "tool_to_run": "run_read_only_command",
            "symptom": "Domain name resolution failure (DNS lookup timeout or SERVFAIL).",
            "root_cause": "Upstream DNS resolvers are unreachable, `/etc/resolv.conf` is misconfigured, or `systemd-resolved` cache is stalled.",
            "commands": [
                ("resolvectl status", SafetyLevel.READ_ONLY, 0.05, "Inspect active DNS link upstream servers and query statistics."),
                ("cat /etc/resolv.conf", SafetyLevel.READ_ONLY, 0.05, "Inspect active nameserver directives in resolver configuration."),
                ("sudo systemd-resolve --flush-caches", SafetyLevel.MODIFYING, 0.20, "Flush stale DNS query cache.")
            ],
            "rationale": "System cannot translate domain names into IP addresses, causing network timeouts for external APIs and services."
        },
        {
            "id": "DPKG_LOCK_BLOCKED",
            "pattern": r"(Could not get lock /var/lib/dpkg/lock|Resource temporarily unavailable|dpkg: error: dpkg frontend lock is held|Unable to acquire the dpkg frontend lock|Could not open lock file /var/lib/apt/lists/lock)",
            "tool_to_run": "query_system_logs",
            "symptom": "Package manager execution blocked by another running apt/dpkg instance.",
            "root_cause": "An automated background unattended-upgrades job or another package manager session holds the exclusive dpkg frontend lock.",
            "commands": [
                ("sudo lsof /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock", SafetyLevel.READ_ONLY, 0.05, "Identify the active PID holding the dpkg lock descriptor."),
                ("sudo ps aux | grep -E 'apt|dpkg|unattended-upgrade'", SafetyLevel.READ_ONLY, 0.05, "Inspect running package manager processes."),
                ("sudo dpkg --configure -a", SafetyLevel.HIGH_RISK, 0.70, "Cleanly resume and repair pending package installation states.")
            ],
            "rationale": "Debian/Ubuntu package management uses advisory locks to guarantee atomic database updates."
        },
        {
            "id": "SYSTEMD_CRASH_LOOP",
            "pattern": r"(Start request repeated too quickly|Unit .* entered failed state|Failed with result 'exit-code'|Main process exited, code=dumped|Holdoff time finished, scheduling restart)",
            "tool_to_run": "inspect_service",
            "symptom": "Systemd unit entered crash loop and exceeded restart burst limit (`StartLimitBurst`).",
            "root_cause": "Service crashed immediately upon boot repeatedly, triggering systemd rate-limiting backoff to protect CPU.",
            "commands": [
                ("sudo systemctl status {service} -l --no-pager", SafetyLevel.READ_ONLY, 0.05, "Inspect full failure callstack and unit properties."),
                ("sudo journalctl -u {service} -xeu {service} -n 40 --no-pager", SafetyLevel.READ_ONLY, 0.05, "Inspect crash error messages with systemd catalog explanations."),
                ("sudo systemctl reset-failed {service}", SafetyLevel.MODIFYING, 0.30, "Reset the rate-limit failure counter on the unit.")
            ],
            "rationale": "Systemd suspends automatic restarts when `StartLimitBurst` is breached to prevent spinning CPU cores."
        },
        {
            "id": "DB_CONN_EXHAUSTION",
            "pattern": r"(too many connections|remaining connection slots are reserved|Connection pool exhausted|max_connections exceeded|Can't connect to MySQL server|server closed the connection unexpectedly)",
            "tool_to_run": "inspect_listening_ports",
            "symptom": "Database connection pool saturated (clients receiving connection refused).",
            "root_cause": "Active concurrent client connections reached database `max_connections` limit or file descriptor `ulimit`.",
            "commands": [
                ("sudo ss -tan state established '( dport = :5432 or dport = :3306 or dport = :6379 )' | wc -l", SafetyLevel.READ_ONLY, 0.05, "Count total active established database client connections."),
                ("sudo systemctl status postgresql mysql redis", SafetyLevel.READ_ONLY, 0.05, "Inspect database daemon health status.")
            ],
            "rationale": "Database engines reject new connection requests once backend worker limits or OS socket descriptors are exhausted."
        },
        {
            "id": "FIREWALL_PORT_BLOCKED",
            "pattern": r"(Connection refused|Connection timed out.*port|Host unreachable|No route to host|iptables: DROP|UFW BLOCK|filtered port)",
            "tool_to_run": "run_read_only_command",
            "symptom": "Network ingress or egress traffic dropped by kernel packet filter.",
            "root_cause": "Firewall rules (UFW / iptables / nftables) are dropping packets targeting the specified port or IP range.",
            "commands": [
                ("sudo ufw status verbose", SafetyLevel.READ_ONLY, 0.05, "Check active UFW firewall rule configuration and status."),
                ("sudo iptables -L -n -v --line-numbers", SafetyLevel.READ_ONLY, 0.05, "Inspect low-level netfilter chains and dropped packet counters."),
                ("sudo ufw allow 80/tcp", SafetyLevel.HIGH_RISK, 0.70, "Allow HTTP traffic through UFW firewall.")
            ],
            "rationale": "Default-drop firewall policies isolate unconfigured ports to prevent unauthorized remote network access."
        },
        {
            "id": "ZOMBIE_PROCESS_ACCUMULATION",
            "pattern": r"(defunct|zombie process|defunct process accumulating|maximum number of processes reached|fork: Resource temporarily unavailable)",
            "tool_to_run": "inspect_processes",
            "symptom": "Process table saturated by defunct zombie child processes.",
            "root_cause": "Parent processes terminated or failed to invoke `wait()`/`waitpid()` on exited children, causing zombie PID accumulation.",
            "commands": [
                ("ps aux | awk '{if ($8 ~ /Z/) print $0}'", SafetyLevel.READ_ONLY, 0.05, "List all current defunct zombie processes with their PIDs."),
                ("ps -ef | grep defunct | head -n 10", SafetyLevel.READ_ONLY, 0.05, "Identify parent PIDs responsible for uncollected zombie children.")
            ],
            "rationale": "Zombies occupy PID slots in the kernel process table without consuming RAM until their parent is terminated."
        },
        {
            "id": "IOWAIT_BOTTLENECK",
            "pattern": r"(high\s+iowait|iowait.*high|task .* blocked for more than \d+ seconds|blk_update_request: I/O error|Buffer I/O error on dev|high disk latency|iowait\s+spike)",
            "tool_to_run": "inspect_system_health",
            "symptom": "High kernel CPU I/O wait state causing sluggish system response.",
            "root_cause": "Disk block layer is bottlenecked by saturated write throughput, degrading storage drive, or failing hardware controller.",
            "commands": [
                ("iostat -x 1 3", SafetyLevel.READ_ONLY, 0.05, "Inspect device await, r/s, w/s, and disk %utilization."),
                ("dmesg -T --level=err,crit | grep -i -E 'i/o|ata|nvme|scsi|error'", SafetyLevel.READ_ONLY, 0.05, "Inspect kernel ring buffer for disk hardware errors.")
            ],
            "rationale": "Processes enter uninterruptible sleep ('D' state) while waiting for slow or unresponsive storage controllers."
        },
        {
            "id": "SELINUX_APPARMOR_DENIAL",
            "pattern": r"(type=AVC msg=audit|apparmor=\"DENIED\"|avc:\s+denied|permission=requested_mask|audit: type=1400)",
            "tool_to_run": "run_read_only_command",
            "symptom": "Mandatory Access Control (MAC) security policy denial.",
            "root_cause": "SELinux or AppArmor security profile prevented service executable from reading/writing confined resources.",
            "commands": [
                ("sudo aa-status", SafetyLevel.READ_ONLY, 0.05, "Check AppArmor profile status and confined applications."),
                ("sudo dmesg -T | grep -i -E 'apparmor|audit|avc' | tail -n 20", SafetyLevel.READ_ONLY, 0.05, "Inspect exact security policy violation audit records.")
            ],
            "rationale": "Linux Security Modules (LSM) enforce least-privilege security profiles overriding standard DAC permissions."
        },
        {
            "id": "NTP_CLOCK_DRIFT",
            "pattern": r"(Time has been changed|Server has gone too long without receiving time|system clock desynchronized|NTP sync failed|clock skew detected)",
            "tool_to_run": "run_read_only_command",
            "symptom": "System clock drift desynchronizing authentication tokens and TLS certificates.",
            "root_cause": "Network Time Protocol (NTP) service is stopped, blocked by firewall, or upstream time servers are unreachable.",
            "commands": [
                ("timedatectl status", SafetyLevel.READ_ONLY, 0.05, "Check local RTC time, UTC time, and NTP synchronization state."),
                ("timedatectl timesync-status", SafetyLevel.READ_ONLY, 0.05, "Inspect upstream time server jitter, delay, and offset."),
                ("sudo timedatectl set-ntp true", SafetyLevel.MODIFYING, 0.35, "Enable automatic systemd network time synchronization.")
            ],
            "rationale": "Clock drift breaks Kerberos tokens, JWT signatures, SSL certificate validation, and distributed clustering."
        }
    ]

    FAILURE_TAXONOMY = DETERMINISTIC_PATTERNS

    def __init__(
        self,
        llm_provider: Optional[Union[LLMProvider, str]] = None,
        distro_db: Optional[DistroKnowledgeBase] = None,
        distro_detector: Optional[DistroDetector] = None,
        model_path: Optional[str] = None,
        session: Optional[Any] = None
    ):
        self.session = session
        self.distro_db = distro_db or DistroKnowledgeBase()
        self.distro_detector = distro_detector or DistroDetector(self.distro_db)
        self.hub = TelemetryHub(distro_detector=self.distro_detector)
        self.explainer = XAIExplainer()
        self.causality_engine = CausalityDAGEngine()
        self.sandbox_probe = EphemeralSandboxProbe()
        self.safety_validator = CommandSafetyValidator()
        self.tools_registry = AgentToolsRegistry(
            distro_info=None,
            safety_validator=self.safety_validator
        )

        from ops_assistant.hardware.advisor import HardwareAdvisor
        self.hardware_advisor = HardwareAdvisor()

        if isinstance(llm_provider, str):
            prov_str = llm_provider.lower().strip()
            if prov_str in ["gemini", "google"]:
                self.llm_provider = GeminiProvider()
            elif prov_str in ["gguf", "llama_cpp", "local"]:
                self.llm_provider = LlamaCppProvider(model_path=model_path)
            elif prov_str in ["ollama", "remote"]:
                self.llm_provider = OllamaProvider()
            elif prov_str == "auto":
                try:
                    from ops_assistant.config import get_config
                    cfg = get_config()
                    cfg_prov = cfg.get("provider", "auto")
                except Exception:
                    cfg_prov = "auto"
                    cfg = {}

                if cfg_prov == "gemini":
                    self.llm_provider = GeminiProvider()
                elif cfg_prov == "deterministic":
                    self.llm_provider = None
                elif cfg_prov == "ollama":
                    self.llm_provider = OllamaProvider(
                        endpoint=cfg.get("ollama_endpoint", "http://localhost:11434/api/generate"),
                        model=cfg.get("ollama_model", "llama3:8b")
                    )
                elif cfg_prov == "gguf":
                    target_model_path = model_path or cfg.get("active_model_path")
                    gguf_p = LlamaCppProvider(model_path=target_model_path)
                    avail = False
                    if hasattr(gguf_p, "is_available"):
                        try:
                            res_av = gguf_p.is_available()
                            avail = bool(res_av[0] if isinstance(res_av, tuple) else res_av)
                        except Exception:
                            pass
                    self.llm_provider = gguf_p if avail else None
                else:
                    gemini_p = GeminiProvider()
                    avail_gemini = False
                    try:
                        res_av = gemini_p.is_available()
                        avail_gemini = bool(res_av[0] if isinstance(res_av, tuple) else res_av)
                    except Exception:
                        pass

                    if avail_gemini:
                        self.llm_provider = gemini_p
                    else:
                        target_model_path = model_path or cfg.get("active_model_path")
                        gguf_p = LlamaCppProvider(model_path=target_model_path)
                        avail_gguf = False
                        try:
                            res_av = gguf_p.is_available()
                            avail_gguf = bool(res_av[0] if isinstance(res_av, tuple) else res_av)
                        except Exception:
                            pass
                        self.llm_provider = gguf_p if avail_gguf else None
            else:
                self.llm_provider = None
        else:
            self.llm_provider = llm_provider

    def extract_subsystem(self, query: str) -> Optional[str]:
        query_lower = query.lower()
        for svc in self.COMMON_SERVICES:
            if svc in query_lower:
                return svc
        return None

    def _adapt_commands_for_distro(
        self,
        matched_id: Optional[str],
        default_cmds: List[Tuple[str, SafetyLevel, float, str]],
        distro_info: DistroInfo,
        svc_name: str
    ) -> List[Tuple[str, SafetyLevel, float, str]]:
        """Adapts diagnostic and remediation commands to target distribution syntax."""
        fid = distro_info.family_id

        # Package manager lock collision adaptations
        if matched_id == "DPKG_LOCK_BLOCKED":
            if fid == "rhel":
                return [
                    ("sudo fuser /var/run/dnf.pid /var/lib/rpm/.rpm.lock 2>/dev/null", SafetyLevel.READ_ONLY, 0.05, "Inspect PID holding DNF/RPM package lock."),
                    ("sudo dnf check", SafetyLevel.READ_ONLY, 0.05, "Check package database consistency and duplicates."),
                    ("sudo rpm --rebuilddb", SafetyLevel.HIGH_RISK, 0.70, "Rebuild corrupted Berkeley DB RPM package database.")
                ]
            elif fid == "arch":
                return [
                    ("sudo fuser /var/lib/pacman/db.lck 2>/dev/null", SafetyLevel.READ_ONLY, 0.05, "Identify process locking pacman database."),
                    ("sudo pacman -Sy --noconfirm archlinux-keyring && sudo pacman -Syu", SafetyLevel.HIGH_RISK, 0.70, "Refresh Arch keyring and sync pacman repositories.")
                ]
            elif fid == "alpine":
                return [
                    ("sudo pidof apk", SafetyLevel.READ_ONLY, 0.05, "Inspect active APK package processes."),
                    ("sudo apk fix --purge", SafetyLevel.HIGH_RISK, 0.70, "Purge and repair broken packages and reinstall missing files.")
                ]
            elif fid == "suse":
                return [
                    ("sudo fuser /var/run/zypp.pid 2>/dev/null", SafetyLevel.READ_ONLY, 0.05, "Identify PID holding Zypper package lock."),
                    ("sudo systemctl stop packagekit", SafetyLevel.MODIFYING, 0.35, "Stop competing PackageKit background daemon."),
                    ("sudo zypper clean -a && sudo zypper ref -f", SafetyLevel.HIGH_RISK, 0.70, "Clean cache and force refresh Zypper repositories.")
                ]

        # Firewall adaptations
        elif matched_id == "FIREWALL_PORT_BLOCKED":
            if fid in ["rhel", "suse"]:
                return [
                    ("sudo firewall-cmd --state && sudo firewall-cmd --list-all", SafetyLevel.READ_ONLY, 0.05, "Check active Firewalld status and rules."),
                    ("sudo iptables -L -n -v --line-numbers", SafetyLevel.READ_ONLY, 0.05, "Inspect low-level netfilter chains and dropped packet counters."),
                    ("sudo firewall-cmd --permanent --add-port=80/tcp && sudo firewall-cmd --reload", SafetyLevel.HIGH_RISK, 0.70, "Allow HTTP traffic through firewalld.")
                ]
            elif fid == "arch":
                return [
                    ("sudo nft list ruleset", SafetyLevel.READ_ONLY, 0.05, "Inspect active nftables ruleset."),
                    ("sudo nft add rule inet filter input tcp dport 80 accept", SafetyLevel.HIGH_RISK, 0.70, "Allow HTTP traffic via nftables.")
                ]
            elif fid == "alpine":
                return [
                    ("sudo awall list", SafetyLevel.READ_ONLY, 0.05, "Inspect Alpine Wall firewall status."),
                    ("sudo awall activate -f", SafetyLevel.HIGH_RISK, 0.70, "Apply Alpine Wall configuration.")
                ]

        # Security Subsystem adaptations
        elif matched_id == "SELINUX_APPARMOR_DENIAL":
            if fid == "rhel":
                return [
                    ("sestatus", SafetyLevel.READ_ONLY, 0.05, "Check SELinux mode and policy status."),
                    ("sudo ausearch -m avc -ts recent | audit2why", SafetyLevel.READ_ONLY, 0.05, "Explain exact SELinux denial reasons with audit2why."),
                    (f"sudo restorecon -Rv /var/log/{svc_name}", SafetyLevel.MODIFYING, 0.40, "Restore standard SELinux security contexts.")
                ]
            elif fid == "alpine":
                return [
                    ("dmesg | grep -i pax", SafetyLevel.READ_ONLY, 0.05, "Check PaX / hardened kernel security logs.")
                ]

        # Alpine OpenRC Service Command Translations
        if fid == "alpine":
            adapted_cmds = []
            for cmd_str, level, risk, rationale in default_cmds:
                c = cmd_str
                c = re.sub(r"sudo systemctl status (\S+)", r"sudo rc-service \1 status", c)
                c = re.sub(r"systemctl status (\S+)", r"rc-service \1 status", c)
                c = re.sub(r"sudo systemctl restart (\S+)", r"sudo rc-service \1 restart", c)
                c = re.sub(r"systemctl restart (\S+)", r"rc-service \1 restart", c)
                c = re.sub(r"sudo systemctl stop (\S+)", r"sudo rc-service \1 stop", c)
                c = re.sub(r"systemctl stop (\S+)", r"rc-service \1 stop", c)
                c = re.sub(r"sudo systemctl start (\S+)", r"sudo rc-service \1 start", c)
                c = re.sub(r"systemctl start (\S+)", r"rc-service \1 start", c)
                c = re.sub(r"sudo journalctl -u (\S+).*", r"logread | grep \1", c)
                c = re.sub(r"journalctl -u (\S+).*", r"logread | grep \1", c)
                c = re.sub(r"journalctl.*", r"logread", c)
                adapted_cmds.append((c, level, risk, rationale))
            return adapted_cmds

        return default_cmds

    def diagnose(
        self,
        query: str,
        custom_logs: Optional[List[LogRecord]] = None,
        distro_override: Optional[str] = None
    ) -> DiagnosticReport:
        """
        Autonomous ReAct Diagnostic Loop:
        1. Multi-turn Session & Pronoun Resolution
        2. Context & Distro Discovery
        3. Dynamic ReAct Tool Observation Loop (LLM-directed planning & execution)
        4. Causal DAG Construction & Telemetry Correlation
        5. Grounded Root Cause Synthesis & Remediation
        6. AST Safety Gating & Sandbox Validation
        7. Session State Update
        """
        start_time = time.perf_counter()

        # 1. Multi-turn session resolution
        resolved_query = query
        session_ctx = ""
        if self.session is not None:
            resolved_query = self.session.resolve_pronouns(query)
            session_ctx = self.session.get_context_for_llm()

        subsystem = self.extract_subsystem(resolved_query)

        # 2. Distro Detection & System Health Snapshot
        distro_info = self.distro_detector.detect(override_family=distro_override)
        health = self.hub.get_health_snapshot(distro_override=distro_override)
        svc_name = subsystem or ("service" if distro_info.family_id == "alpine" else "systemd")

        cpu_util = (100.0 - health.cpu.idle_pct) if health and health.cpu else 0.0
        ram_used = health.memory.used_percent if health and health.memory else 0.0

        system_context = {
            "query": resolved_query,
            "raw_query": query,
            "subsystem": svc_name,
            "distro_name": distro_info.distro_name,
            "family_id": distro_info.family_id,
            "init_system": distro_info.init_system,
            "package_manager": distro_info.package_manager,
            "pressure_status": getattr(health, "pressure_status", "NORMAL"),
            "cpu_util": cpu_util,
            "ram_used_pct": ram_used,
            "conversation_history": session_ctx
        }

        # Check LLM availability
        llm_avail = False
        if self.llm_provider:
            if hasattr(self.llm_provider, "is_available"):
                try:
                    res_avail = self.llm_provider.is_available()
                    if isinstance(res_avail, tuple) and len(res_avail) >= 2:
                        llm_avail = bool(res_avail[0])
                    elif isinstance(res_avail, bool):
                        llm_avail = res_avail
                    else:
                        llm_avail = True
                except Exception:
                    llm_avail = True
            else:
                llm_avail = True

        observations: List[Dict[str, Any]] = []
        executed_tool_names = set()

        # 3. Dynamic ReAct Observation Phase (LLM-directed planning)
        if llm_avail and hasattr(self.llm_provider, "plan_observations"):
            try:
                tool_schemas = self.tools_registry.get_schemas()
                planned_tool_calls = self.llm_provider.plan_observations(
                    resolved_query, system_context, tool_schemas
                )
                if planned_tool_calls and isinstance(planned_tool_calls, list):
                    for tc in planned_tool_calls:
                        if not isinstance(tc, dict):
                            continue
                        t_name = tc.get("tool") or tc.get("name")
                        t_args = tc.get("arguments") or tc.get("args") or {}
                        if not isinstance(t_args, dict):
                            t_args = {}
                        if t_name and self.tools_registry.get_tool(t_name) and t_name not in executed_tool_names:
                            t_res = self.tools_registry.execute(t_name, t_args)
                            executed_tool_names.add(t_name)
                            observations.append({
                                "tool": t_name,
                                "arguments": t_args,
                                "status": t_res.get("status", "success"),
                                "output": t_res.get("result", t_res)
                            })
            except Exception:
                pass

        # Baseline health telemetry is always collected if not already observed
        if "inspect_system_health" not in executed_tool_names:
            health_obs = self.tools_registry.execute("inspect_system_health", {})
            executed_tool_names.add("inspect_system_health")
            observations.insert(0, {
                "tool": "inspect_system_health",
                "arguments": {},
                "status": "success",
                "output": health_obs.get("result", {})
            })

        # Ensure target service state is inspected if subsystem is present and not yet checked
        if subsystem and "inspect_service" not in executed_tool_names:
            svc_obs = self.tools_registry.execute("inspect_service", {"service_name": subsystem})
            executed_tool_names.add("inspect_service")
            observations.append({
                "tool": "inspect_service",
                "arguments": {"service_name": subsystem},
                "status": "success",
                "output": svc_obs.get("result", {})
            })

        # Collect logs for the causality engine and evidence traces
        if custom_logs is not None:
            logs = custom_logs
        else:
            log_obs = self.tools_registry.execute("query_system_logs", {
                "unit": f"{subsystem}.service" if subsystem else None,
                "subsystem": subsystem,
                "lines": 50
            })
            logs_res = log_obs.get("result", {}).get("logs", [])
            logs = [LogRecord(timestamp="now", source="tool", priority="3", message=l) for l in logs_res]
            if not logs:
                logs = self.hub.journal.query_all_relevant_logs(
                    unit=f"{subsystem}.service" if subsystem else None,
                    subsystem=subsystem,
                    lines=50
                )

        log_messages = [l.message for l in logs]
        combined_text = resolved_query + "\n" + "\n".join(log_messages)

        # 4. Dynamic Causality Graph from Ingested Logs & Tool Observations
        dag_result = self.causality_engine.build_dag_from_events(log_messages)

        # 5. Hybrid Reasoning: LLM Synthesis with Grounded Tool Evidence vs Deterministic Fast Path
        llm_diagnosis = None
        if llm_avail:
            if hasattr(self.llm_provider, "generate_diagnosis"):
                try:
                    llm_diagnosis = self.llm_provider.generate_diagnosis(resolved_query, system_context)
                except Exception:
                    pass
            if not llm_diagnosis and hasattr(self.llm_provider, "synthesize_diagnosis"):
                try:
                    llm_diagnosis = self.llm_provider.synthesize_diagnosis(resolved_query, system_context, observations)
                except Exception:
                    pass

        evidence: List[str] = []
        if llm_diagnosis and isinstance(llm_diagnosis, dict) and "symptom" in llm_diagnosis:
            symptom = llm_diagnosis.get("symptom", "LLM-detected anomaly")
            root_cause = llm_diagnosis.get("root_cause", "Root cause identified via LLM tool synthesis")
            rationale = llm_diagnosis.get("rationale", "Synthesized from observed tool outputs.")
            confidence = float(llm_diagnosis.get("confidence", 0.92))
            provider_label = type(self.llm_provider).__name__
            reasoning_engine = f"{provider_label}-ReAct-Tool-Agent ({distro_info.distro_name})"

            parsed_cmds = []
            for cmd in llm_diagnosis.get("proposed_commands", []):
                if isinstance(cmd, (list, tuple)) and len(cmd) >= 4:
                    sec_str = str(cmd[1]).upper()
                    sec_lvl = SafetyLevel.READ_ONLY
                    for s in SafetyLevel:
                        if s.name == sec_str or s.value == sec_str:
                            sec_lvl = s
                            break
                    parsed_cmds.append((str(cmd[0]), sec_lvl, float(cmd[2]), str(cmd[3])))
                elif isinstance(cmd, (list, tuple)) and len(cmd) >= 1:
                    parsed_cmds.append((str(cmd[0]), SafetyLevel.READ_ONLY, 0.05, "Proposed remediation command."))

            raw_cmds = parsed_cmds
        else:
            # Deterministic Pattern Match Fallback (Offline / Air-Gapped)
            matched_item = None
            for item in self.DETERMINISTIC_PATTERNS:
                matches = re.findall(item["pattern"], combined_text, flags=re.IGNORECASE)
                if matches:
                    matched_item = item
                    for l in logs:
                        if re.search(item["pattern"], l.message, flags=re.IGNORECASE):
                            evidence.append(f"[{l.source}] {l.message}")
                    break

            if not matched_item:
                distro_sigs = self.distro_db.get_error_signatures(distro_info.family_id)
                for sig in distro_sigs:
                    if re.search(sig["pattern"], combined_text, flags=re.IGNORECASE):
                        matched_item = {
                            "id": sig["id"],
                            "pattern": sig["pattern"],
                            "symptom": f"Distro-specific issue ({distro_info.distro_name}): {sig['id']}",
                            "root_cause": sig["explanation"],
                            "commands": [
                                (sig["remediation"].replace("{service}", svc_name).replace("{path}", f"/var/log/{svc_name}"), SafetyLevel.HIGH_RISK, 0.70, sig["explanation"])
                            ],
                            "rationale": sig["explanation"]
                        }
                        for l in logs:
                            if re.search(sig["pattern"], l.message, flags=re.IGNORECASE):
                                evidence.append(f"[{l.source}] {l.message}")
                        break

            if matched_item:
                symptom = matched_item["symptom"]
                root_cause = matched_item["root_cause"]
                rationale = matched_item["rationale"]
                raw_cmds = [
                    (cmd[0].replace("{service}", svc_name), cmd[1], cmd[2], cmd[3])
                    for cmd in matched_item["commands"]
                ]
                raw_cmds = self._adapt_commands_for_distro(
                    matched_item.get("id"), raw_cmds, distro_info, svc_name
                )
                confidence = 0.96
                reasoning_engine = f"ReAct-Grounded-Deterministic ({distro_info.distro_name})"
            else:
                symptom = f"Unclassified anomaly detected on {svc_name}."
                root_cause = "General service startup or operational failure."
                rationale = "Inspect recent service logs and process state to identify failure root cause."
                if distro_info.family_id == "alpine":
                    raw_cmds = [
                        (f"logread | grep {svc_name}", SafetyLevel.READ_ONLY, 0.05, "Retrieve recent service logs from syslogd buffer."),
                        (f"sudo rc-service {svc_name} status", SafetyLevel.READ_ONLY, 0.05, "Inspect OpenRC service status and PID.")
                    ]
                else:
                    raw_cmds = [
                        (f"sudo journalctl -u {svc_name} -n 50 --no-pager", SafetyLevel.READ_ONLY, 0.05, "Retrieve recent systemd service logs."),
                        (f"systemctl status {svc_name}", SafetyLevel.READ_ONLY, 0.05, "Inspect unit status and active process ID.")
                    ]
                confidence = 0.80
                reasoning_engine = f"ReAct-General-Triage ({distro_info.distro_name})"

        # 6. Synthesize XAI Explanation & Rollback Plans
        xai = self.explainer.synthesize_xai(
            symptom=symptom,
            root_cause=root_cause,
            evidence_logs=evidence if evidence else ([f"[{l.source}] {l.message}" for l in logs[:2]] if logs else ["Telemetry inspection active."]),
            commands=raw_cmds,
            rationale=rationale,
            confidence=confidence
        )

        # 7. Ephemeral Namespace Probe Verification
        for cmd_prop in xai.proposed_commands:
            probe_res = self.sandbox_probe.verify_command(cmd_prop.command)
            cmd_prop.sandbox_verified = probe_res.is_verified

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # 8. Record Turn in Session Memory
        if self.session is not None:
            self.session.add_turn(
                query=query,
                response_summary=f"{symptom} — {root_cause}",
                intent="diagnose",
                subsystem=subsystem,
                commands=[c.command for c in xai.proposed_commands],
                symptom=symptom,
                root_cause=root_cause
            )

        return DiagnosticReport(
            query=query,
            target_subsystem=subsystem,
            health_snapshot=health,
            explanation=xai,
            causality_dag=dag_result.to_dict(),
            latency_ms=round(elapsed_ms, 2),
            reasoning_engine=reasoning_engine
        )

    def explain_command(self, command_str: str) -> Dict[str, Any]:
        """Explain a Linux command using CommandExplainer and optional Gemini LLM elaboration."""
        explanation = CommandExplainer.explain(command_str)
        if isinstance(self.llm_provider, GeminiProvider):
            avail = False
            try:
                res_av = self.llm_provider.is_available()
                avail = bool(res_av[0] if isinstance(res_av, tuple) else res_av)
            except Exception:
                pass
            if avail:
                prompt = (
                    f"Explain the purpose, flags, security risks, and side-effects of this Linux command in 2 clear sentences.\n"
                    f"Command: {command_str}\n"
                    f"Respond in plain text."
                )
                gemini_exp = self.llm_provider._call_gemini_api(prompt, response_json=False)
                if gemini_exp:
                    explanation["ai_summary"] = gemini_exp.strip()
        return explanation

    def explain_error(self, command_str: str, returncode: int, stderr: str = "", stdout: str = "") -> Dict[str, Any]:
        """Explain a failed shell command execution using ErrorExplainer."""
        return ErrorExplainer.explain_error(command_str, returncode, stderr=stderr, stdout=stdout)

    def interpret_command(self, text: str) -> Dict[str, Any]:
        """Classify and plan a natural-language command without executing anything."""
        result = self.execute_agent_action(text, execute=False)
        raw_summary = result.get("summary", "").strip()
        if raw_summary and not raw_summary.lower().startswith("ready to"):
            understanding = raw_summary
        else:
            intent_label = result.get("intent", "perform an action").replace("_", " ")
            understanding = f"You want me to {intent_label}: {text.rstrip('.')}."

        planned = result.get("planned_commands") or []
        if not planned and result.get("command"):
            planned = [{
                "command": result["command"],
                "description": result.get("command_description") or result.get("summary", ""),
                "safety_level": result.get("safety_level", SafetyLevel.READ_ONLY.value),
                "risk_score": result.get("risk_score", 0.05),
            }]

        plan_steps: List[Dict[str, Any]] = [
            {
                "index": i,
                "description": cmd.get("description") or cmd.get("command", ""),
                "command": cmd.get("command", ""),
                "safety_level": cmd.get("safety_level", SafetyLevel.READ_ONLY.value),
                "risk_score": float(cmd.get("risk_score", 0.05)),
            }
            for i, cmd in enumerate(planned)
        ]

        safety_level = result.get("safety_level", SafetyLevel.READ_ONLY.value)
        safety_level_val = (
            safety_level.value if hasattr(safety_level, "value") else str(safety_level)
        )
        requires_confirmation = safety_level_val in ("HIGH_RISK", "DESTRUCTIVE")

        return {
            "understanding": understanding,
            "plan_steps": plan_steps,
            "requires_confirmation": requires_confirmation,
            "safety_level": safety_level_val,
            "intent": result.get("intent", "unknown"),
            "confidence": result.get("confidence", 1.0),
        }

    def execute_agent_action(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        execute: bool = True,
        distro_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """Unified Natural Language Agent Action Dispatcher."""
        from ops_assistant.nlp.intent_router import IntentRouter, IntentType
        from ops_assistant.nlp.nl_compiler import NaturalLanguageCompiler, generate_natural_explanation
        from ops_assistant.tools import (
            desktop_ops, download_ops, storage_ops, process_ops, network_ops,
            log_ops, system_ops, docker_ops, security_ops, backup_ops
        )

        resolved_query = query
        if self.session is not None:
            resolved_query = self.session.resolve_pronouns(query)

        router = getattr(self, "_router", None)
        if router is None:
            router = IntentRouter(llm_provider=self.llm_provider)
            self._router = router

        intent = router.classify(resolved_query)
        args = intent.args or {}

        compiled = NaturalLanguageCompiler.compile(resolved_query)
        if compiled and compiled.get("command"):
            if intent.type in (IntentType.UNKNOWN, IntentType.GENERIC_COMMAND, IntentType.SHELL_RUN, IntentType.DIAGNOSE) or "mkdir" in compiled.get("command", ""):
                cmd = compiled["command"]
                summary = compiled.get("summary", f"Run `{cmd}`")
                safety_lvl = compiled.get("safety_level", SafetyLevel.MODIFYING.value)
                risk_sc = float(compiled.get("risk_score", 0.35))
                rollback_cmd = compiled.get("rollback_command")
                explanation_p = generate_natural_explanation(resolved_query, cmd, 0, "", "")

                res_action: Dict[str, Any] = {
                    "query": query,
                    "intent": compiled.get("intent", "desktop_command"),
                    "confidence": 0.95,
                    "steps": [summary],
                    "summary": summary,
                    "command": cmd,
                    "command_description": summary,
                    "explanation_paragraph": explanation_p,
                    "planned_commands": [{
                        "command": cmd,
                        "description": summary,
                        "safety_level": safety_lvl,
                        "risk_score": risk_sc
                    }],
                    "safety_level": safety_lvl,
                    "risk_score": risk_sc,
                    "output": None,
                    "rollback_command": rollback_cmd,
                    "diagnostic_report": None,
                    "requires_permission": safety_lvl in ("HIGH_RISK", "DESTRUCTIVE") or compiled.get("requires_permission", False),
                    "executed": execute,
                    "timestamp": time.time()
                }

                if execute:
                    executor = SafeExecutor()
                    exec_res = executor.execute(cmd)
                    res_action["output"] = exec_res
                    res_action["summary"] = f"Executed: `{cmd}`" if exec_res.get("returncode") == 0 else f"Failed: `{cmd}`"
                else:
                    res_action["summary"] = f"Ready to run: `{cmd}` — {summary}"

                return res_action

        # Standard Intent Handling
        result: Dict[str, Any] = {
            "query": query,
            "intent": intent.type.value,
            "confidence": intent.confidence,
            "steps": [],
            "summary": "",
            "command": "",
            "command_description": "",
            "planned_commands": [],
            "safety_level": SafetyLevel.READ_ONLY.value,
            "risk_score": 0.05,
            "output": None,
            "rollback_command": None,
            "diagnostic_report": None,
            "requires_permission": False,
            "executed": execute,
            "timestamp": time.time()
        }

        # 1. Desktop & OS
        if intent.type == IntentType.DESKTOP_OPEN_FOLDER:
            target_path = args.get("path") or args.get("target", "~")
            create_missing = args.get("create_if_missing", False)
            result["command"] = f"xdg-open '{target_path}'"
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["summary"] = f"Opened folder {target_path}"
            if execute:
                result["output"] = desktop_ops.open_folder(target_path, create_if_missing=create_missing)
            return result

        elif intent.type == IntentType.DESKTOP_OPEN_BROWSER:
            url = args.get("url", "https://google.com")
            if not url.startswith("http"):
                url = f"https://{url}"
            result["command"] = f"xdg-open '{url}'"
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["summary"] = f"Opened browser to {url}"
            if execute:
                result["output"] = desktop_ops.open_browser(url)
            return result

        elif intent.type == IntentType.DESKTOP_OPEN_FILE:
            target = args.get("path") or args.get("target", "")
            result["command"] = f"xdg-open '{target}'"
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["summary"] = f"Opened file {target}"
            if execute:
                result["output"] = desktop_ops.open_file(target)
            return result

        elif intent.type == IntentType.DESKTOP_OPEN_IMAGE:
            target = args.get("path") or args.get("target", "")
            result["command"] = f"xdg-open '{target}'"
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["summary"] = f"Opened image {target}"
            if execute:
                result["output"] = desktop_ops.open_image(target)
            return result

        # 2. Storage
        elif intent.type == IntentType.STORAGE_CLEAN:
            result["requires_permission"] = True
            result["safety_level"] = SafetyLevel.HIGH_RISK.value
            result["risk_score"] = 0.70
            result["command"] = "sudo journalctl --vacuum-size=100M ; sudo apt clean"
            result["summary"] = "Clean system cache and temporary log files"
            if execute:
                result["output"] = storage_ops.clean_system()
            return result

        elif intent.type == IntentType.STORAGE_ORGANISE:
            target = args.get("path") or args.get("target", "~/Downloads")
            result["requires_permission"] = True
            result["safety_level"] = SafetyLevel.MODIFYING.value
            result["risk_score"] = 0.35
            result["command"] = f"organise_directory '{target}'"
            result["summary"] = f"Organize directory {target}"
            if execute:
                result["output"] = storage_ops.organize_folder(target, dry_run=False)
            else:
                result["output"] = storage_ops.organize_folder(target, dry_run=True)
            return result

        elif intent.type == IntentType.STORAGE_ANALYSE:
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = "df -h"
            result["summary"] = "Analyze disk storage utilization"
            if execute:
                result["output"] = storage_ops.analyze_storage()
            return result

        elif intent.type == IntentType.STORAGE_FIND_LARGE:
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = "du -sh /* 2>/dev/null | sort -rh | head -10"
            result["summary"] = "Find large files consuming disk storage"
            if execute:
                result["output"] = storage_ops.find_large_files()
            return result

        # 3. Processes
        elif intent.type == IntentType.PROCESS_LIST:
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = "ps aux --sort=-%mem | head -n 15"
            result["summary"] = "List top running processes"
            result["output"] = process_ops.list_top_processes(n=15, sort_by=args.get("sort_by", "mem"))
            return result

        elif intent.type == IntentType.PROCESS_KILL:
            pid = args.get("pid")
            name = args.get("name") or args.get("process")
            result["requires_permission"] = True
            result["safety_level"] = SafetyLevel.HIGH_RISK.value
            result["risk_score"] = 0.70
            if pid:
                result["command"] = f"sudo kill -15 {pid}"
                result["summary"] = f"Terminate process PID {pid}"
            else:
                result["command"] = f"sudo pkill -f '{name}'"
                result["summary"] = f"Terminate process '{name}'"
            if execute:
                result["output"] = process_ops.kill_process(name=name, pid=pid)
            return result

        # 4. Services
        elif intent.type in (IntentType.SERVICE_STATUS, IntentType.SERVICE_START, IntentType.SERVICE_STOP,
                             IntentType.SERVICE_RESTART, IntentType.SERVICE_ENABLE, IntentType.SERVICE_DISABLE):
            svc = args.get("service", "")
            action = intent.type.value.replace("service_", "")
            d_info = self.distro_detector.detect(override_family=distro_override)

            if d_info.init_system == "openrc":
                result["command"] = f"sudo rc-service {svc} {action}" if action != "status" else f"rc-service {svc} status"
            else:
                result["command"] = f"sudo systemctl {action} {svc}" if action != "status" else f"systemctl status {svc}"

            result["summary"] = f"{action.capitalize()} service {svc}"
            if action == "status":
                result["safety_level"] = SafetyLevel.READ_ONLY.value
            else:
                result["safety_level"] = SafetyLevel.MODIFYING.value
                result["risk_score"] = 0.35
                result["requires_permission"] = True
                if d_info.init_system == "openrc":
                    if action == "start":
                        result["rollback_command"] = f"sudo rc-service '{svc}' stop"
                    elif action == "stop":
                        result["rollback_command"] = f"sudo rc-service '{svc}' start"
                    elif action == "restart":
                        result["rollback_command"] = f"sudo rc-service '{svc}' restart"
                else:
                    if action == "start":
                        result["rollback_command"] = f"sudo systemctl stop '{svc}'"
                    elif action == "stop":
                        result["rollback_command"] = f"sudo systemctl start '{svc}'"
                    elif action == "restart":
                        result["rollback_command"] = f"sudo systemctl restart '{svc}'"
            if execute:
                result["output"] = system_ops.manage_service(action=action, service=svc)
            return result

        # 5. Network & Firewall
        elif intent.type == IntentType.NETWORK_PING:
            host = args.get("host", "google.com")
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = f"ping -c 4 {host}"
            result["summary"] = f"Ping network host {host}"
            if execute:
                result["output"] = network_ops.ping_host(host)
            return result

        elif intent.type == IntentType.NETWORK_DNS:
            host = args.get("host", "github.com")
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = f"resolvectl query {host} || host {host}"
            result["summary"] = f"DNS lookup for {host}"
            if execute:
                result["output"] = network_ops.dns_lookup(host)
            return result

        elif intent.type in (IntentType.FIREWALL_ALLOW, IntentType.FIREWALL_DENY):
            port = args.get("port", 80)
            action = "allow" if intent.type == IntentType.FIREWALL_ALLOW else "deny"
            d_info = self.distro_detector.detect(override_family=distro_override)
            result["safety_level"] = SafetyLevel.HIGH_RISK.value
            result["risk_score"] = 0.70
            result["requires_permission"] = True

            if d_info.default_firewall == "firewalld":
                fw_flag = "--add-port" if action == "allow" else "--remove-port"
                result["command"] = f"sudo firewall-cmd {fw_flag}={port}/tcp --permanent && sudo firewall-cmd --reload"
                rb_flag = "--remove-port" if action == "allow" else "--add-port"
                result["rollback_command"] = f"sudo firewall-cmd {rb_flag}={port}/tcp --permanent && sudo firewall-cmd --reload"
            elif d_info.default_firewall == "nftables":
                result["command"] = f"sudo nft add rule inet filter input tcp dport {port} {'accept' if action == 'allow' else 'drop'}"
                result["rollback_command"] = f"sudo nft delete rule inet filter input tcp dport {port}"
            elif d_info.default_firewall == "awall":
                result["command"] = f"sudo awall {'allow-port' if action == 'allow' else 'deny-port'} {port}"
                result["rollback_command"] = f"sudo awall {'deny-port' if action == 'allow' else 'allow-port'} {port}"
            else:
                result["command"] = f"sudo ufw {action} {port}/tcp"
                result["rollback_command"] = f"sudo ufw delete {action} {port}/tcp"

            result["summary"] = f"Firewall {action} port {port}"
            if execute:
                result["output"] = network_ops.manage_firewall(action=action, port=port)
            return result

        # 6. Security
        elif intent.type == IntentType.SECURITY_AUDIT:
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = "audit_security"
            result["summary"] = "Run comprehensive system security audit"
            result["output"] = security_ops.run_security_scan()
            return result

        elif intent.type == IntentType.SECURITY_BRUTEFORCE:
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = "sudo grep -i 'failed password' /var/log/auth.log"
            result["summary"] = "Check SSH authentication brute-force attempts"
            result["output"] = security_ops.check_ssh_bruteforce()
            return result

        elif intent.type == IntentType.SECURITY_SUID:
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = "find / -perm -4000 2>/dev/null"
            result["summary"] = "Scan for SUID root binaries"
            result["output"] = security_ops.check_suid_binaries()
            return result

        # 7. System Info & Logs
        elif intent.type == IntentType.SYSTEM_INFO:
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = "uname -a ; uptime"
            result["summary"] = "Show system information"
            if execute:
                result["output"] = system_ops.get_system_info()
            return result

        elif intent.type == IntentType.SYSTEM_UPTIME:
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = "uptime"
            result["summary"] = "Show system uptime"
            if execute:
                result["output"] = system_ops.get_uptime()
            return result

        elif intent.type == IntentType.LOGS_ERRORS:
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = "journalctl -p 3 -xb"
            result["summary"] = "Show system error logs"
            if execute:
                result["output"] = log_ops.query_logs(grep="error", lines=30)
            return result

        elif intent.type == IntentType.LOGS_KERNEL:
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = "dmesg -T --level=err,warn"
            result["summary"] = "Show kernel logs"
            if execute:
                result["output"] = log_ops.query_logs(unit="kernel", lines=30)
            return result

        elif intent.type == IntentType.USER_WHO:
            result["safety_level"] = SafetyLevel.READ_ONLY.value
            result["command"] = "who"
            result["summary"] = "List currently logged in users"
            if execute:
                result["output"] = system_ops.get_logged_in_users()
            return result

        # Default fallback to diagnostic ReAct loop
        rep = self.diagnose(query)
        result["diagnostic_report"] = rep.to_dict()
        result["summary"] = f"Diagnostic complete: {rep.explanation.symptom} -> {rep.explanation.root_cause}"
        if rep.explanation.proposed_commands:
            p = rep.explanation.proposed_commands[0]
            result["command"] = p.command
            result["command_description"] = p.rationale
            result["safety_level"] = p.safety_level.value
            result["risk_score"] = p.risk_score
            result["rollback_command"] = p.rollback_command
            result["planned_commands"] = [
                {
                    "command": cmd.command,
                    "description": cmd.rationale,
                    "safety_level": cmd.safety_level.value,
                    "risk_score": cmd.risk_score
                }
                for cmd in rep.explanation.proposed_commands
            ]
        return result

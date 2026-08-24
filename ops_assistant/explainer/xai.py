"""Explainable AI (XAI) Engine for transparent root-cause reasoning and command deconstruction."""

import os
import re
import shlex
from typing import List, Dict, Tuple, Optional, Any
from ops_assistant.models import (
    XAIExplanation, CommandProposal, CommandFlagExplanation, SafetyLevel
)

RE_SYS_START = re.compile(r"\bsystemctl\s+start\s+([a-zA-Z0-9_-]+)")
RE_SYS_STOP = re.compile(r"\bsystemctl\s+stop\s+([a-zA-Z0-9_-]+)")
RE_SYS_ENABLE = re.compile(r"\bsystemctl\s+enable\s+([a-zA-Z0-9_-]+)")
RE_UFW_ALLOW = re.compile(r"\bufw\s+allow\s+([a-zA-Z0-9_/]+)")
RE_UFW_DENY = re.compile(r"\bufw\s+deny\s+([a-zA-Z0-9_/]+)")

class XAIExplainer:
    FLAG_DICTIONARY: Dict[str, Dict[str, str]] = {
        "journalctl": {
            "-u": "Filters logs strictly to the specified systemd unit name.",
            "-n": "Limits output to the N most recent log lines.",
            "-p": "Filters by syslog priority level (e.g. 0:emerg to 3:err).",
            "-xeu": "Combines: -x (catalog explanation), -e (jump to end), -u (unit filter).",
            "-f": "Follows active log stream in real time.",
            "--since": "Filters log events starting from specified timestamp.",
            "--no-pager": "Outputs raw stream directly without launching terminal pager (less/more)."
        },
        "ss": {
            "-t": "Displays TCP sockets.",
            "-u": "Displays UDP sockets.",
            "-l": "Shows only listening sockets.",
            "-p": "Shows process holding the socket descriptor.",
            "-n": "Renders numeric port numbers rather than resolving service names.",
            "-tulpn": "Combined: TCP, UDP, Listening, Process info, Numeric ports."
        },
        "systemctl": {
            "status": "Displays active/sub state, PID, memory, and recent log journal slice.",
            "restart": "Issues stop followed by start transition on the target unit.",
            "reload": "Asks service daemon to re-read configuration without terminating active connections.",
            "start": "Initiates unit activation sequence.",
            "stop": "Gracefully terminates unit processes via SIGTERM/SIGKILL.",
            "enable": "Creates systemd symlinks so unit automatically starts at boot.",
            "disable": "Removes systemd symlinks to prevent automatic startup at boot.",
            "daemon-reload": "Reloads all systemd unit configuration files from disk.",
            "reset-failed": "Resets the 'failed' state on units that exceeded restart rate limits.",
            "--failed": "Lists all units currently in failed state."
        },
        "df": {
            "-h": "Prints filesystem capacity and usage in human-readable units (MB/GB).",
            "-i": "Prints inode allocation statistics instead of disk block usage.",
            "-T": "Displays filesystem type (ext4, xfs, btrfs, tmpfs) for each partition."
        },
        "free": {
            "-h": "Displays RAM and Swap memory utilization in human-readable gigabytes/megabytes.",
            "-m": "Displays memory statistics in megabytes.",
            "-w": "Displays wide output separating active buffers and cache columns."
        },
        "ps": {
            "aux": "Lists all running processes across all users with CPU/MEM percentages.",
            "--sort=-%mem": "Sorts process table descending by memory consumption.",
            "--sort=-%cpu": "Sorts process table descending by CPU utilization.",
            "-ef": "Standard full-format process listing.",
            "axjf": "Displays hierarchical process tree showing parent-child PID relationships."
        },
        "nginx": {
            "-t": "Tests configuration files for syntax errors and structural validity without restarting.",
            "-T": "Dumps entire merged configuration with syntax test output.",
            "-s": "Sends signal (stop, quit, reopen, reload) to running master process."
        },
        "apache2ctl": {
            "configtest": "Parses and verifies Apache HTTP server configuration files for errors.",
            "status": "Displays live Apache runtime worker thread statistics."
        },
        "ip": {
            "-br": "Renders concise one-line brief network interface table.",
            "a": "Displays IP addresses assigned to all network interfaces.",
            "addr": "Displays IP addresses assigned to all network interfaces.",
            "link": "Displays link-layer status (UP/DOWN/CARRIER) for interfaces.",
            "route": "Displays kernel routing table with default gateways and metrics.",
            "neigh": "Displays ARP neighbor cache entries."
        },
        "lsof": {
            "-i": "Lists all open internet network sockets.",
            "-P": "Inhibits conversion of port numbers to service names.",
            "-n": "Inhibits IP address resolution to hostnames for faster output.",
            "+D": "Recursively searches for open file handles within target directory."
        },
        "curl": {
            "-I": "Fetches HTTP response headers only (HEAD request).",
            "-v": "Enables verbose debugging output including TLS handshake logs.",
            "-k": "Allows insecure SSL connections (ignores untrusted certificates).",
            "-s": "Silent mode (suppresses progress bar and error messages).",
            "--connect-timeout": "Maximum time in seconds allowed for network connection attempt."
        },
        "dmesg": {
            "-T": "Renders human-readable timestamps on kernel log messages.",
            "--level=err,crit": "Filters kernel ring buffer strictly to errors and critical faults.",
            "-w": "Follows new kernel messages in real time.",
            "-c": "Clears the kernel ring buffer after printing."
        },
        "iostat": {
            "-x": "Displays extended disk I/O metrics including %util, await, and queue size.",
            "-d": "Displays block device throughput in sectors/second.",
            "-z": "Omits devices with zero activity for cleaner output."
        },
        "vmstat": {
            "-s": "Displays cumulative event counter statistics (page faults, context switches).",
            "-d": "Displays disk statistics summary table."
        },
        "timedatectl": {
            "status": "Displays local time, UTC time, RTC time, and NTP synchronization state.",
            "set-ntp": "Enables or disables automatic network time synchronization.",
            "timesync-status": "Displays offset, jitter, and upstream NTP server details."
        },
        "ufw": {
            "status": "Displays firewall operational state and active allow/deny rule table.",
            "allow": "Adds firewall rule allowing ingress traffic on specified port/protocol.",
            "deny": "Adds firewall rule dropping ingress traffic on specified port/protocol.",
            "reload": "Re-reads firewall rule tables without dropping active connection state."
        },
        "iptables": {
            "-L": "Lists all active firewall filter rules.",
            "-n": "Displays IP addresses and port numbers numerically.",
            "-v": "Displays packet and byte counters for matching rules.",
            "-F": "Flushes (deletes) all rules in target chain or table."
        },
        "dpkg": {
            "--configure": "Reconfigures unpacked packages that failed during previous install.",
            "-a": "Applies configuration action to all pending unconfigured packages.",
            "-l": "Lists all installed packages matching pattern."
        },
        "apt": {
            "update": "Fetches updated package index files from configured repository sources.",
            "-f": "Fixes broken package dependencies and incomplete installations.",
            "clean": "Clears downloaded .deb package cache from /var/cache/apt/archives/."
        },
        "openssl": {
            "s_client": "Initiates generic SSL/TLS client connection to test server certificates.",
            "-connect": "Specifies target host:port endpoint for TLS handshake testing.",
            "-servername": "Passes SNI (Server Name Indication) extension for virtual hosting.",
            "x509": "Displays certificate fields, expiration dates, and issuer fingerprints."
        },
        "tar": {
            "-c": "Creates a new archive.",
            "-x": "Extracts files from an archive.",
            "-v": "Verbosely lists files being processed.",
            "-f": "Specifies the archive filename.",
            "-z": "Filters the archive through gzip compression (.tar.gz).",
            "-j": "Filters the archive through bzip2 compression (.tar.bz2).",
            "-J": "Filters the archive through xz compression (.tar.xz).",
            "-C": "Changes to directory before performing archive extraction.",
            "-czvf": "Combined: Create, Gzip compress, Verbose progress, Archive File target.",
            "-xzvf": "Combined: Extract, Gzip decompress, Verbose progress, Archive File target."
        },
        "chmod": {
            "+x": "Adds executable execution permission to the target file.",
            "-x": "Removes executable execution permission from the target file.",
            "-R": "Recursively changes file permissions across subdirectories.",
            "755": "Owner: Read+Write+Exec (rwx); Group & Others: Read+Exec (r-x).",
            "644": "Owner: Read+Write (rw-); Group & Others: Read only (r--).",
            "600": "Owner: Read+Write (rw-); Group & Others: No access (---).",
            "777": "Grants full Read+Write+Exec permissions to all users (HIGH RISK)."
        },
        "chown": {
            "-R": "Recursively changes user/group ownership across all subdirectories.",
            "-v": "Outputs diagnostic details for every file processed."
        },
        "find": {
            "-name": "Searches for files matching the specified filename glob pattern.",
            "-type": "Restricts search by file type (f: regular file, d: directory, l: symlink).",
            "-size": "Filters files by size (e.g. +100M for files greater than 100 Megabytes).",
            "-mtime": "Filters files modified within N days.",
            "-exec": "Executes specified command on each matched file.",
            "-delete": "Deletes matched files directly (DESTRUCTIVE)."
        },
        "grep": {
            "-r": "Recursively searches subdirectories.",
            "-rn": "Recursively searches with line numbers.",
            "-i": "Performs case-insensitive pattern matching.",
            "-v": "Inverts match to select non-matching lines.",
            "-E": "Treats pattern as extended regular expression (regex).",
            "-l": "Prints only filenames of files containing matches."
        },
        "kill": {
            "-9": "Sends SIGKILL signal to immediately terminate process without cleanup (non-catchable).",
            "-15": "Sends SIGTERM signal to request graceful process termination.",
            "-KILL": "Sends SIGKILL signal for immediate termination.",
            "-TERM": "Sends SIGTERM signal for graceful shutdown."
        },
        "pkill": {
            "-f": "Matches against full command line instead of just process name.",
            "-9": "Forces immediate SIGKILL termination of all matching processes."
        },
        "xdg-open": {
            "default": "Opens a file or URL in the user's preferred desktop application."
        },
        "docker": {
            "ps": "Lists running container instances.",
            "logs": "Fetches stdout and stderr streams from specified container.",
            "inspect": "Displays low-level JSON configuration and state of container or image.",
            "restart": "Stops and re-creates container process."
        }
    }

    def generate_rollback_command(self, command_str: str) -> Tuple[Optional[str], Optional[str]]:
        """Synthesizes safe undo/rollback commands for state-modifying actions with precompiled regex patterns."""
        stripped = command_str.strip()
        
        # Systemctl start -> stop
        m = RE_SYS_START.search(stripped)
        if m:
            svc = m.group(1)
            return f"sudo systemctl stop {svc}", f"Stops {svc} if newly started service proves unstable."

        # Systemctl stop -> start
        m = RE_SYS_STOP.search(stripped)
        if m:
            svc = m.group(1)
            return f"sudo systemctl start {svc}", f"Restarts {svc} to return to previous running state."

        # Systemctl enable -> disable
        m = RE_SYS_ENABLE.search(stripped)
        if m:
            svc = m.group(1)
            return f"sudo systemctl disable {svc}", f"Disables {svc} boot startup symlink."

        # UFW allow -> delete allow
        m = RE_UFW_ALLOW.search(stripped)
        if m:
            rule = m.group(1)
            return f"sudo ufw delete allow {rule}", f"Deletes firewall allow rule for {rule}."

        # UFW deny -> delete deny
        m = RE_UFW_DENY.search(stripped)
        if m:
            rule = m.group(1)
            return f"sudo ufw delete deny {rule}", f"Deletes firewall deny rule for {rule}."

        return None, None

    def deconstruct_command(self, command_str: str) -> List[CommandFlagExplanation]:
        """Breaks down command flags and verbs into transparent human explanations with fast tokenizer."""
        explanations: List[CommandFlagExplanation] = []
        if '"' not in command_str and "'" not in command_str and "\\" not in command_str:
            tokens = command_str.split()
        else:
            try:
                tokens = shlex.split(command_str)
            except Exception:
                tokens = command_str.split()

        if not tokens:
            return []

        has_sudo = tokens[0] == "sudo"
        exec_tokens = tokens[1:] if has_sudo and len(tokens) > 1 else tokens
        base_cmd = exec_tokens[0] if exec_tokens else ""

        dict_entries = self.FLAG_DICTIONARY.get(base_cmd)

        if dict_entries is not None:
            for token in exec_tokens[1:]:
                purpose = dict_entries.get(token)
                if purpose is not None:
                    explanations.append(CommandFlagExplanation(flag=token, purpose=purpose))
                elif token.startswith("-"):
                    explanations.append(CommandFlagExplanation(flag=token, purpose=f"Option flag passed to {base_cmd}."))
        else:
            for token in exec_tokens[1:]:
                if token.startswith("-"):
                    explanations.append(CommandFlagExplanation(flag=token, purpose=f"Option flag passed to {base_cmd}."))

        return explanations

    def synthesize_xai(
        self,
        symptom: str,
        root_cause: str,
        evidence_logs: List[str],
        commands: List[Tuple[str, SafetyLevel, float, str]],
        rationale: str,
        confidence: float = 0.95,
        mitigation_steps: Optional[List[str]] = None
    ) -> XAIExplanation:
        """Synthesizes a fully grounded XAIExplanation object."""
        proposals: List[CommandProposal] = []

        for cmd_str, safety, risk_score, cmd_rationale in commands:
            flags = self.deconstruct_command(cmd_str)
            requires_sudo = cmd_str.startswith("sudo ") or safety in [SafetyLevel.MODIFYING, SafetyLevel.HIGH_RISK]
            rollback_cmd, rollback_rat = self.generate_rollback_command(cmd_str)
            proposals.append(CommandProposal(
                command=cmd_str,
                safety_level=safety,
                risk_score=risk_score,
                flag_breakdown=flags,
                rationale=cmd_rationale,
                requires_sudo=requires_sudo,
                rollback_command=rollback_cmd,
                rollback_rationale=rollback_rat
            ))

        steps = mitigation_steps or [
            "Verify current service and system state with read-only diagnostic commands.",
            "Review proposed remediation command rationale and safety tier.",
            "Execute remediation with step-by-step confirmation.",
            "Verify service recovery and monitor logs for residual anomalies."
        ]

        return XAIExplanation(
            symptom=symptom,
            root_cause=root_cause,
            evidence_logs=evidence_logs[:5],
            confidence_score=confidence,
            rationale=rationale,
            proposed_commands=proposals,
            mitigation_steps=steps
        )


class CommandExplainer:
    """Dedicated module for deconstructing and explaining any Linux command in plain English."""

    def __init__(self):
        self.xai = XAIExplainer()

    @classmethod
    def explain(cls, command_str: str) -> Dict[str, Any]:
        xai = XAIExplainer()
        cmd = command_str.strip()
        flags = xai.deconstruct_command(cmd)
        tokens = cmd.split()
        base_cmd = tokens[0] if tokens else ""
        if base_cmd == "sudo" and len(tokens) > 1:
            base_cmd = tokens[1]

        # Determine general description
        general_descriptions = {
            "tar": "Archives or extracts compressed files (tarballs).",
            "chmod": "Modifies file system access permissions (read, write, execute).",
            "chown": "Changes file or directory user and group ownership.",
            "find": "Searches directory hierarchy for files matching filters (name, size, age).",
            "grep": "Searches text or files for matching regular expression patterns.",
            "ps": "Reports a snapshot of the current active system processes.",
            "top": "Displays real-time dynamic view of system processor activity.",
            "htop": "Interactive real-time process viewer and system resource monitor.",
            "kill": "Sends a termination or control signal to a specific process by PID.",
            "pkill": "Sends a termination signal to processes based on name matching.",
            "systemctl": "Controls the systemd system and service manager.",
            "journalctl": "Queries and displays logs from systemd journald logging daemon.",
            "df": "Reports file system disk space usage and availability.",
            "free": "Displays amount of free and used physical memory (RAM) and swap.",
            "ip": "Configures and monitors network interfaces, IP addresses, and routing tables.",
            "curl": "Transfers data to or from a server using supported network protocols.",
            "wget": "Non-interactive network downloader for HTTP, HTTPS, and FTP.",
            "mkdir": "Creates new directories in the file system.",
            "rm": "Removes files or directories from storage.",
            "cp": "Copies files and directories.",
            "mv": "Moves or renames files and directories.",
            "cat": "Concatenates and displays file contents in the terminal.",
            "touch": "Creates an empty file or updates the timestamps of an existing file.",
            "xdg-open": "Opens a file or URL in the user's preferred desktop application."
        }

        desc = general_descriptions.get(base_cmd, f"Executes system binary '{base_cmd}'.")
        flag_list = [{"flag": f.flag, "purpose": f.purpose} for f in flags]

        return {
            "command": cmd,
            "base_command": base_cmd,
            "base_binary": base_cmd,
            "description": desc,
            "requires_sudo": cmd.startswith("sudo ") or "chmod" in cmd or "chown" in cmd,
            "flags": flag_list,
            "flags_detected": flag_list,
            "plain_summary": f"`{cmd}` — {desc}" + (f" ({len(flag_list)} options decoded)" if flag_list else ""),
            "summary": f"`{cmd}` — {desc}" + (f" ({len(flag_list)} options decoded)" if flag_list else "")
        }


class ErrorExplainer:
    """Diagnoses and provides actionable solutions for non-zero Linux shell execution errors."""

    EXIT_CODE_MAP = {
        1: "General catchall error code.",
        2: "Misuse of shell builtins or syntax error.",
        126: "Command invoked cannot execute (permission denied or not executable).",
        127: "Command not found (binary not installed or missing from PATH).",
        128: "Invalid exit argument.",
        130: "Process terminated by user via SIGINT (Ctrl+C).",
        137: "Process forcibly killed by SIGKILL (often triggered by Linux Out-Of-Memory OOM-killer).",
        139: "Process crashed due to Segmentation Fault (SIGSEGV).",
        143: "Process terminated gracefully by SIGTERM."
    }

    @classmethod
    def explain(cls, command: str, returncode: int, stderr: str = "", stdout: str = "") -> Dict[str, Any]:
        return cls.explain_error(command, returncode, stderr, stdout)

    @classmethod
    def explain_error(cls, command: str, returncode: int, stderr: str = "", stdout: str = "") -> Dict[str, Any]:
        combined_err = (stderr + "\n" + stdout).strip()
        combined_lower = combined_err.lower()
        code_desc = cls.EXIT_CODE_MAP.get(returncode, f"Subprocess exited with non-zero return code {returncode}.")

        diagnosis = "Execution failed."
        recommendation = "Check command syntax and system state."
        err_class = "UNKNOWN_ERROR"

        # Heuristic pattern diagnosis
        if returncode == 127 or "command not found" in combined_lower or "not found" in combined_lower and "no such file" not in combined_lower:
            err_class = "COMMAND_NOT_FOUND"
            tokens = command.split()
            bin_name = tokens[0] if tokens else "command"
            if bin_name == "sudo" and len(tokens) > 1:
                bin_name = tokens[1]
            if bin_name == "open":
                diagnosis = "On Linux, the 'open' command is not installed by default. Linux uses 'xdg-open' or direct browser launchers."
                recommendation = "Use 'xdg-open' or run with OpsAssistant natural language: 'open browser'."
            else:
                diagnosis = f"Binary '{bin_name}' is not installed on this system or not in your PATH."
                recommendation = f"Install the missing package using your distro package manager (e.g. 'sudo pacman -S {bin_name}' or 'sudo apt install {bin_name}')."

        elif returncode == 126 or any(k in combined_lower for k in [
            "permission denied", "operation not permitted", "authentication required",
            "interactive authentication", "must be root", "need to be root", "are you root",
            "access denied", "eacces", "eperm"
        ]):
            err_class = "PERMISSION_DENIED"
            diagnosis = "The process lacks filesystem permissions or requires root/superuser privileges (sudo)."
            recommendation = "Prepend 'sudo' to run as root, or adjust file permissions with 'chmod +x <file>' or ownership with 'sudo chown $USER <file>'."

        elif "no such file or directory" in combined_lower:
            err_class = "FILE_NOT_FOUND"
            diagnosis = "The target file or parent directory path does not exist on the filesystem."
            recommendation = "Check the path spelling, create parent directories using 'mkdir -p', or verify file existence with 'ls -la'."

        elif "file exists" in combined_lower:
            err_class = "FILE_ALREADY_EXISTS"
            diagnosis = "A file or directory already exists at the destination path."
            recommendation = "Choose a different name, use '--force' / '-f' to overwrite if intended, or backup the existing file."

        elif "is a directory" in combined_lower or "not a directory" in combined_lower:
            err_class = "PATH_TYPE_MISMATCH"
            diagnosis = "The command expected a regular file but encountered a directory, or vice versa."
            recommendation = "Specify a file path instead of a directory, or pass recursive flags (e.g., '-r' / '-R')."

        elif any(k in combined_lower for k in ["address already in use", "port already in use", "eaddrinuse", "bind() to"]):
            err_class = "PORT_CONFLICT"
            m_port = re.search(r":(\d{2,5})", combined_lower) or re.search(r"port\s+(\d{2,5})", combined_lower)
            port_num = m_port.group(1) if m_port else None
            if port_num:
                diagnosis = f"TCP/UDP network port {port_num} is already occupied by another running daemon or process."
                recommendation = f"Run 'sudo ss -tulpn | grep :{port_num}' or 'sudo fuser -k {port_num}/tcp' to identify/kill the conflicting process, or reconfigure the service port."
            else:
                diagnosis = "A TCP/UDP network port is already occupied by another running daemon or process."
                recommendation = "Run 'sudo ss -tulpn' to identify which process PID holds the port, then terminate it or reconfigure the service port."

        elif "no space left on device" in combined_lower or "enospc" in combined_lower:
            err_class = "DISK_EXHAUSTION"
            diagnosis = "The storage disk partition or inode table is 100% full."
            recommendation = "Run 'df -h' and 'df -i' to inspect capacity, and run 'clean space' to purge temporary files and reclaim disk capacity."

        elif "could not get lock" in combined_lower or "lock-frontend" in combined_lower or "db.lck" in combined_lower:
            err_class = "LOCK_CONFLICT"
            diagnosis = "Package manager database lock is currently held by another background update process or daemon."
            recommendation = "Wait for the active update process to complete, or inspect running package managers via 'ps aux | grep -E \"apt|dpkg|pacman|dnf\"'."

        elif returncode == 137 or "oom-killer" in combined_lower or "out of memory" in combined_lower:
            err_class = "OOM_KILL"
            diagnosis = "The process was abruptly terminated by the Linux kernel Out-Of-Memory (OOM) Killer."
            recommendation = "Free up memory with 'free -h', terminate high-memory processes, reduce memory limits, or configure swap space."

        elif "timed out" in combined_lower or "timeout" in combined_lower or returncode == 124:
            err_class = "TIMEOUT"
            diagnosis = "The command exceeded the maximum allocated execution time limit before completing."
            recommendation = "Check network connectivity, reduce the data payload, or run the command in background mode."

        elif "connection refused" in combined_lower or "network is unreachable" in combined_lower or "temporary failure in name resolution" in combined_lower:
            err_class = "NETWORK_ERROR"
            diagnosis = "Failed to establish a network connection (remote endpoint down, firewall blocking, or DNS resolution failure)."
            recommendation = "Verify internet access, test DNS with 'ping -c 1 8.8.8.8', or check firewall status with 'sudo ufw status'."

        elif "invalid option" in combined_lower or "unknown option" in combined_lower or "syntax error" in combined_lower or returncode == 2:
            err_class = "SYNTAX_ERROR"
            diagnosis = "The command string contains invalid command-line flags, option arguments, or shell syntax."
            recommendation = "Check the command man page or help with '<command> --help' to verify valid flags and syntax."

        return {
            "command": command,
            "returncode": returncode,
            "error_class": err_class,
            "exit_code_description": code_desc,
            "diagnosis": diagnosis,
            "recommendation": recommendation,
            "raw_stderr": stderr[:2000] if stderr else ""
        }


class ExecutionOutcomeExplainer:
    """
    Synthesizes rich, human-friendly natural language explanations of executed commands,
    computes detailed system changes made (on success), and provides deep root-cause failure
    analysis with remediation steps (on failure).
    """

    @classmethod
    def explain_outcome(
        cls,
        command: str,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        query: Optional[str] = None,
        elapsed_ms: float = 0.0,
        intent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        llm_provider: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes a complete outcome explanation object.
        """
        cmd = (command or "").strip()
        is_success = (returncode == 0)
        query_str = (query or "").strip()

        # 1. Detect System / Filesystem Changes
        changes_made: List[str] = []
        changes_summary = ""

        # Parse command tokens
        tokens = cmd.split()
        base_cmd = tokens[0] if tokens else ""
        if base_cmd == "sudo" and len(tokens) > 1:
            base_cmd = tokens[1]

        # Detailed change detection
        if is_success:
            if "mkdir" in cmd:
                # Extract directory path
                m_dir = re.search(r"mkdir\s+(?:-[a-zA-Z]+\s+)*['\"]?([^'\";|&]+)['\"]?", cmd)
                target_dir = m_dir.group(1).strip() if m_dir else "target directory"
                exp_path = os.path.expanduser(target_dir)
                changes_made.append(f"Created directory `{target_dir}` (resolved to `{exp_path}`)")
                changes_summary = f"Created directory '{target_dir}' on the filesystem."

            elif "touch" in cmd or ("echo" in cmd and ">" in cmd):
                m_file = re.search(r"(?:touch|>)\s+['\"]?([^'\";|&]+)['\"]?", cmd)
                target_file = m_file.group(1).strip() if m_file else "target file"
                exp_file = os.path.expanduser(target_file)
                changes_made.append(f"Created/modified file `{target_file}` (resolved to `{exp_file}`)")
                changes_summary = f"Wrote file '{target_file}' with specified content and permissions."

            elif "rm " in cmd or "rmdir" in cmd or base_cmd in ("rm", "rmdir"):
                rm_args = [t for t in tokens if not t.startswith("-") and t not in ("sudo", "rm", "rmdir")]
                target_rm = ", ".join(f"`{a}`" for a in rm_args) if rm_args else "`target path`"
                target_plain = ", ".join(rm_args) if rm_args else "target path"
                changes_made.append(f"Deleted {target_rm} from storage")
                changes_summary = f"Deleted '{target_plain}' from the filesystem."

            elif "systemctl" in cmd:
                m_svc = re.search(r"systemctl\s+(start|stop|restart|reload|enable|disable)\s+([a-zA-Z0-9_\-\.@]+)", cmd)
                if m_svc:
                    action, svc_name = m_svc.group(1), m_svc.group(2)
                    changes_made.append(f"Systemd service `{svc_name}` state transitioned to `{action}`")
                    changes_summary = f"Executed systemd {action} on service unit '{svc_name}'."
                else:
                    changes_made.append(f"Executed systemd management command `{cmd}`")
                    changes_summary = f"Updated systemd service configuration."

            elif any(p in cmd for p in ["pacman", "apt", "apt-get", "dnf", "apk", "zypper"]):
                subcmd_tokens = [t for t in tokens if not t.startswith("-") and t not in ("sudo", "apt", "apt-get", "pacman", "dnf", "apk", "zypper")]
                action_word = ""
                if any(k in cmd for k in ["-S", "install", "add"]):
                    action_word = "install"
                elif any(k in cmd for k in ["-R", "remove", "del", "purge"]):
                    action_word = "remove"
                elif any(k in cmd for k in ["update", "upgrade", "-Syu"]):
                    action_word = "update"

                pkgs = [t for t in subcmd_tokens if t not in ("install", "remove", "del", "purge", "add", "update", "upgrade", "-S", "-R", "-Syu")]

                if action_word == "install":
                    pkg_str = ", ".join(f"`{p}`" for p in pkgs) if pkgs else "software packages"
                    changes_made.append(f"Installed software package(s) {pkg_str} into the system")
                    changes_summary = f"Installed package(s) {', '.join(pkgs) if pkgs else 'requested software'} and updated local package database."
                elif action_word == "remove":
                    pkg_str = ", ".join(f"`{p}`" for p in pkgs) if pkgs else "software packages"
                    changes_made.append(f"Removed package(s) {pkg_str} from the system")
                    changes_summary = f"Uninstalled package(s) {', '.join(pkgs) if pkgs else 'requested software'}."
                else:
                    changes_made.append("Synchronized system package repositories and refreshed cache")
                    changes_summary = "System package repository metadata updated."

            elif "kill" in cmd or "pkill" in cmd:
                m_pid = re.search(r"kill\s+(?:-[a-zA-Z0-9]+\s+)*(\d+)", cmd)
                if m_pid:
                    pid = m_pid.group(1)
                    changes_made.append(f"Sent termination signal to process PID `{pid}`")
                    changes_summary = f"Terminated process PID {pid}."
                else:
                    changes_made.append(f"Sent process termination signal via `{cmd}`")
                    changes_summary = f"Terminated matching processes."

            elif "chmod" in cmd:
                m_chmod = re.search(r"chmod\s+(?:-[a-zA-Z]+\s+)*([0-9\+\-rwx]+)\s+['\"]?([^'\";|&]+)['\"]?", cmd)
                if m_chmod:
                    mode, target = m_chmod.group(1), m_chmod.group(2)
                    changes_made.append(f"Changed filesystem access permissions of `{target}` to `{mode}`")
                    changes_summary = f"Updated permissions of '{target}' to {mode}."

            elif "chown" in cmd:
                m_chown = re.search(r"chown\s+(?:-[a-zA-Z]+\s+)*([a-zA-Z0-9_\-\.:]+)\s+['\"]?([^'\";|&]+)['\"]?", cmd)
                if m_chown:
                    owner, target = m_chown.group(1), m_chown.group(2)
                    changes_made.append(f"Changed ownership of `{target}` to `{owner}`")
                    changes_summary = f"Assigned user/group ownership of '{target}' to {owner}."

            elif "ufw" in cmd or "iptables" in cmd or "nft" in cmd:
                changes_made.append(f"Applied network firewall security policy: `{cmd}`")
                changes_summary = "Updated firewall rules."

            elif "xdg-open" in cmd or any(g in cmd for g in ["google-chrome", "firefox", "brave", "chromium"]):
                m_url = re.search(r"['\"]?(https?://[^'\";\s]+|www\.[^'\";\s]+)['\"]?", cmd)
                if m_url:
                    url = m_url.group(1)
                    changes_made.append(f"Launched web browser window pointing to `{url}`")
                    changes_summary = f"Opened URL '{url}' in default browser."
                else:
                    changes_made.append(f"Launched default desktop application for `{cmd}`")
                    changes_summary = "Opened desktop application."

            elif "vacuum" in cmd or ("cache" in cmd and "rm" in cmd) or "clean" in cmd:
                changes_made.append("Cleaned ephemeral cache and purged older logs to reclaim disk space")
                changes_summary = "Reclaimed disk storage by purging temporary and cache files."

            elif base_cmd in ("top", "htop", "ps", "df", "free", "journalctl", "dmesg", "who", "uptime", "ss", "ip", "ls"):
                changes_made.append("Queried real-time system state (Read-Only inspection, no filesystem changes made)")
                changes_summary = "Inspected live system metrics without modifying state."

            else:
                changes_made.append(f"Successfully executed command `{cmd}` (Exit Code 0)")
                changes_summary = f"Executed command successfully in {elapsed_ms:.1f}ms."

        # 2. Failure Analysis
        failure_analysis = None
        if not is_success:
            failure_analysis = ErrorExplainer.explain_error(cmd, returncode, stderr=stderr, stdout=stdout)

        # 3. Natural Language Explanation Paragraph Synthesis
        if is_success:
            if query_str:
                natural_explanation = (
                    f"You requested: \"{query_str}\". "
                    f"The assistant translated this into the Linux command `{cmd}` and executed it successfully (exit code 0 in {elapsed_ms:.1f}ms). "
                    f"{changes_summary}"
                )
            else:
                natural_explanation = (
                    f"Successfully executed the Linux command `{cmd}` (exit code 0 in {elapsed_ms:.1f}ms). "
                    f"{changes_summary}"
                )
        else:
            diag_text = failure_analysis.get("diagnosis", "Execution encountered an error.") if failure_analysis else "Command failed."
            recom_text = failure_analysis.get("recommendation", "Review command parameters.") if failure_analysis else ""
            err_cls = failure_analysis.get("error_class", "EXECUTION_ERROR") if failure_analysis else "ERROR"
            
            if query_str:
                natural_explanation = (
                    f"You requested: \"{query_str}\". "
                    f"The assistant attempted to execute `{cmd}`, but the command failed with exit code {returncode} ({err_cls}). "
                    f"{diag_text} Suggested fix: {recom_text}"
                )
            else:
                natural_explanation = (
                    f"Command `{cmd}` failed with exit code {returncode} ({err_cls}). "
                    f"{diag_text} Suggested fix: {recom_text}"
                )

        # 4. Optional AI Provider Elaboration
        ai_elaboration = None
        if llm_provider is not None:
            try:
                avail = True
                if hasattr(llm_provider, "is_available"):
                    res_av = llm_provider.is_available()
                    avail = bool(res_av[0] if isinstance(res_av, tuple) else res_av)
                if avail:
                    status_desc = "succeeded (exit code 0)" if is_success else f"failed with exit code {returncode}"
                    out_sample = (stdout or stderr)[:300]
                    ai_prompt = (
                        f"Provide a 2-sentence natural language summary explaining what happened when this command ran on Linux:\n"
                        f"User Request: {query_str or 'Execute command'}\n"
                        f"Command: {cmd}\n"
                        f"Outcome: {status_desc}\n"
                        f"Output/Error: {out_sample}\n"
                        f"Respond in plain English."
                    )
                    if hasattr(llm_provider, "_call_gemini_api"):
                        ai_res = llm_provider._call_gemini_api(ai_prompt, response_json=False)
                        if ai_res:
                            ai_elaboration = ai_res.strip()
                    elif hasattr(llm_provider, "generate_raw"):
                        ai_res = llm_provider.generate_raw(ai_prompt)
                        if ai_res:
                            ai_elaboration = ai_res.strip()
                    elif hasattr(llm_provider, "generate"):
                        ai_res = llm_provider.generate(ai_prompt)
                        if ai_res:
                            ai_elaboration = ai_res.strip()
            except Exception:
                pass


        return {
            "query": query_str,
            "command": cmd,
            "returncode": returncode,
            "is_success": is_success,
            "elapsed_ms": elapsed_ms,
            "natural_explanation": natural_explanation,
            "explanation_paragraph": natural_explanation,
            "ai_elaboration": ai_elaboration,
            "changes_made": changes_made,
            "changes_summary": changes_summary,
            "failure_analysis": failure_analysis
        }




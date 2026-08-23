"""Agent Tool Registry: Structured system observation & diagnostic tools for the ReAct Agent."""

import os
import re
import json
import subprocess
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict

from ops_assistant.models import SafetyLevel
from ops_assistant.tools.safety import CommandSafetyValidator
from ops_assistant.collectors.distro_detector import DistroDetector, DistroInfo
from ops_assistant.db.distro_db import DistroKnowledgeBase
from ops_assistant.explainer.xai import CommandExplainer, XAIExplainer


@dataclass
class AgentTool:
    """Definition of an executable agent diagnostic/operational tool."""
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable[..., Any]
    is_read_only: bool = True

    def to_schema(self) -> Dict[str, Any]:
        """Export tool definition in OpenAPI / Gemini / Ollama compatible JSON schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


class AgentToolsRegistry:
    """Registry providing grounded system inspection and diagnosis tools."""

    def __init__(
        self,
        distro_info: Optional[DistroInfo] = None,
        safety_validator: Optional[CommandSafetyValidator] = None
    ):
        self.distro_db = DistroKnowledgeBase()
        self.distro_detector = DistroDetector(self.distro_db)
        self.distro_info = distro_info or self.distro_detector.detect()
        self.safety_validator = safety_validator or CommandSafetyValidator()
        self.tools: Dict[str, AgentTool] = {}
        self._register_default_tools()

    def register(self, tool: AgentTool) -> None:
        self.tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[AgentTool]:
        return self.tools.get(name)

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [tool.to_schema() for tool in self.tools.values()]

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool safely and return structured output."""
        tool = self.get_tool(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found in registry."}

        try:
            res = tool.func(**arguments)
            return {"status": "success", "result": res}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # -------------------------------------------------------------------------
    # Core Diagnostic Tool Implementations
    # -------------------------------------------------------------------------

    def _inspect_system_health(self) -> Dict[str, Any]:
        """Inspect CPU, RAM, swap, and kernel PSI pressure metrics."""
        from ops_assistant.collectors.hub import TelemetryHub
        hub = TelemetryHub(distro_detector=self.distro_detector)
        snapshot = hub.get_health_snapshot()
        cpu_util = (100.0 - snapshot.cpu.idle_pct) if snapshot.cpu else 0.0
        psi = snapshot.psi_metrics or {}
        distro_n = (snapshot.distro_info.get("distro_name") if snapshot.distro_info else None) or self.distro_info.distro_name
        return {
            "hostname": snapshot.hostname,
            "distro": distro_n,
            "kernel": snapshot.kernel_release,
            "uptime_seconds": snapshot.uptime_seconds,
            "cpu_util_pct": round(cpu_util, 2),
            "ram_used_mb": snapshot.memory.used_mb if snapshot.memory else 0.0,
            "ram_total_mb": snapshot.memory.total_mb if snapshot.memory else 0.0,
            "ram_used_pct": snapshot.memory.used_percent if snapshot.memory else 0.0,
            "swap_used_mb": snapshot.memory.swap_used_mb if snapshot.memory else 0.0,
            "swap_total_mb": snapshot.memory.swap_total_mb if snapshot.memory else 0.0,
            "load_averages": [snapshot.load.load_1m, snapshot.load.load_5m, snapshot.load.load_15m] if snapshot.load else [0.0, 0.0, 0.0],
            "zombie_processes": snapshot.cpu.zombie_count if snapshot.cpu else 0,
            "pressure_status": snapshot.pressure_status,
            "psi_memory_some_avg10": psi.get("memory", {}).get("some", {}).get("avg10", 0.0),
            "psi_io_some_avg10": psi.get("io", {}).get("some", {}).get("avg10", 0.0),
            "psi_cpu_some_avg10": psi.get("cpu", {}).get("some", {}).get("avg10", 0.0)
        }

    def _inspect_service(self, service_name: str) -> Dict[str, Any]:
        """Inspect systemd or OpenRC unit status, exit code, and recent logs."""
        raw_name = service_name.strip()
        has_custom_ext = any(raw_name.endswith(ext) for ext in (".socket", ".timer", ".slice", ".mount", ".target", ".path"))
        if has_custom_ext:
            clean_name = raw_name
            unit_query = raw_name
        else:
            clean_name = raw_name.removesuffix(".service")
            unit_query = f"{clean_name}.service"

        if self.distro_info.family_id == "alpine":
            cmd = f"rc-service {clean_name} status"
        else:
            cmd = f"systemctl status {unit_query} --no-pager -l"

        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            output = proc.stdout if proc.stdout else proc.stderr
            return {
                "service": clean_name,
                "unit": unit_query,
                "exit_code": proc.returncode,
                "status_output": output[:2000],
                "is_running": "active (running)" in output.lower() or "is started" in output.lower(),
                "is_failed": "failed" in output.lower() or proc.returncode != 0
            }
        except Exception as e:
            return {"service": clean_name, "error": str(e)}

    def _inspect_listening_ports(self, port: Optional[int] = None) -> Dict[str, Any]:
        """Check socket listeners and bound processes via ss/netstat."""
        cmd = "ss -tulpn"
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            lines = proc.stdout.splitlines()
            header = lines[0] if lines else ""
            matching_lines = []
            port_str = f":{port}" if port else ""

            for line in lines[1:]:
                if not port_str or port_str in line:
                    matching_lines.append(line.strip())

            return {
                "port_filter": port,
                "total_listening": len(matching_lines),
                "listeners": matching_lines[:30]
            }
        except Exception as e:
            return {"error": str(e)}

    def _query_system_logs(
        self,
        unit: Optional[str] = None,
        subsystem: Optional[str] = None,
        pattern: Optional[str] = None,
        lines: int = 40
    ) -> Dict[str, Any]:
        """Query journalctl, dmesg, and log files for error traces."""
        from ops_assistant.collectors.hub import TelemetryHub
        hub = TelemetryHub(distro_detector=self.distro_detector)
        unit_name = f"{unit}.service" if unit and not unit.endswith(".service") else unit
        log_records = hub.journal.query_all_relevant_logs(
            unit=unit_name,
            subsystem=subsystem,
            lines=min(lines, 100)
        )

        filtered = []
        for r in log_records:
            if pattern:
                if re.search(pattern, r.message, re.IGNORECASE):
                    filtered.append(f"[{r.timestamp}] [{r.source}] {r.message}")
            else:
                filtered.append(f"[{r.timestamp}] [{r.source}] {r.message}")

        return {
            "unit": unit,
            "subsystem": subsystem,
            "count": len(filtered),
            "logs": filtered[:lines]
        }

    def _inspect_disk_and_inodes(self, mount_point: Optional[str] = None) -> Dict[str, Any]:
        """Inspect storage partition block and inode capacity."""
        try:
            df_proc = subprocess.run("df -h", shell=True, capture_output=True, text=True, timeout=5)
            df_i_proc = subprocess.run("df -i", shell=True, capture_output=True, text=True, timeout=5)

            return {
                "block_usage": df_proc.stdout[:1500],
                "inode_usage": df_i_proc.stdout[:1500]
            }
        except Exception as e:
            return {"error": str(e)}

    def _inspect_processes(self, sort_by: str = "mem", limit: int = 10) -> Dict[str, Any]:
        """Inspect top resource-consuming and zombie processes."""
        sort_flag = "--sort=-%mem" if sort_by == "mem" else "--sort=-%cpu"
        cmd = f"ps aux {sort_flag} | head -n {max(2, limit + 1)}"
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            zombie_proc = subprocess.run("ps aux | awk '{if ($8 ~ /Z/) print $0}'", shell=True, capture_output=True, text=True, timeout=5)
            zombies = [z.strip() for z in zombie_proc.stdout.splitlines() if z.strip()]

            return {
                "sorted_by": sort_by,
                "top_processes": proc.stdout[:2000],
                "zombie_count": len(zombies),
                "zombies": zombies[:10]
            }
        except Exception as e:
            return {"error": str(e)}

    def _run_read_only_command(self, command: str) -> Dict[str, Any]:
        """Execute a verified read-only diagnostic command (e.g. nginx -t, resolvectl status, ufw status)."""
        level, score, reason = self.safety_validator.evaluate_safety(command)
        if level != SafetyLevel.READ_ONLY:
            return {
                "blocked": True,
                "reason": f"Command '{command}' is classified as {level.value} (Risk: {score}). Only READ_ONLY diagnostic commands can be executed automatically by the agent observation loop."
            }

        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=8)
            output = proc.stdout if proc.stdout else proc.stderr
            return {
                "command": command,
                "returncode": proc.returncode,
                "output": output[:3000]
            }
        except Exception as e:
            return {"command": command, "error": str(e)}

    def _explain_command(self, command: str) -> Dict[str, Any]:
        """Deconstruct Linux command flags into plain English."""
        return CommandExplainer.explain(command)

    def _verify_safety(self, command: str) -> Dict[str, Any]:
        """Evaluate command safety level, risk score, and rollback command."""
        val = self.safety_validator.validate(command)
        return val.to_dict()

    # -------------------------------------------------------------------------
    # Tool Registration
    # -------------------------------------------------------------------------

    def _register_default_tools(self) -> None:
        self.register(AgentTool(
            name="inspect_system_health",
            description="Inspect system-wide telemetry: CPU%, RAM/Swap utilization, load averages, zombie counts, and kernel PSI pressure stall metrics.",
            parameters={"type": "object", "properties": {}},
            func=self._inspect_system_health,
            is_read_only=True
        ))

        self.register(AgentTool(
            name="inspect_service",
            description="Inspect systemd or OpenRC service unit status, active state, exit code, and recent unit logs.",
            parameters={
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "description": "Name of the service daemon (e.g. 'nginx', 'postgresql', 'docker', 'apache2')"}
                },
                "required": ["service_name"]
            },
            func=self._inspect_service,
            is_read_only=True
        ))

        self.register(AgentTool(
            name="inspect_listening_ports",
            description="Inspect listening TCP/UDP sockets and bound processes (ss -tulpn) to detect port collisions or check if a daemon is bound.",
            parameters={
                "type": "object",
                "properties": {
                    "port": {"type": "integer", "description": "Optional port number to filter by (e.g. 80, 443, 3000, 5432)"}
                }
            },
            func=self._inspect_listening_ports,
            is_read_only=True
        ))

        self.register(AgentTool(
            name="query_system_logs",
            description="Query journalctl, dmesg kernel ring buffer, and /var/log for error traces, crashes, or specific log patterns.",
            parameters={
                "type": "object",
                "properties": {
                    "unit": {"type": "string", "description": "Optional systemd unit name (e.g. 'nginx', 'ssh')"},
                    "subsystem": {"type": "string", "description": "Optional subsystem name (e.g. 'kernel', 'nginx', 'systemd')"},
                    "pattern": {"type": "string", "description": "Optional regex pattern or search term"},
                    "lines": {"type": "integer", "description": "Number of log lines to retrieve (default: 40)"}
                }
            },
            func=self._query_system_logs,
            is_read_only=True
        ))

        self.register(AgentTool(
            name="inspect_disk_and_inodes",
            description="Check filesystem block utilization (df -h) and inode allocation (df -i) to diagnose disk or inode exhaustion.",
            parameters={"type": "object", "properties": {}},
            func=self._inspect_disk_and_inodes,
            is_read_only=True
        ))

        self.register(AgentTool(
            name="inspect_processes",
            description="List top CPU or memory consuming processes and detect defunct/zombie processes.",
            parameters={
                "type": "object",
                "properties": {
                    "sort_by": {"type": "string", "enum": ["mem", "cpu"], "description": "Sort criterion ('mem' or 'cpu')"},
                    "limit": {"type": "integer", "description": "Number of top processes to return (default: 10)"}
                }
            },
            func=self._inspect_processes,
            is_read_only=True
        ))

        self.register(AgentTool(
            name="run_read_only_command",
            description="Execute an approved read-only diagnostic command (e.g. 'nginx -t', 'resolvectl status', 'timedatectl status', 'openssl x509', 'sudo ss -tulpn').",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Exact shell command to execute"}
                },
                "required": ["command"]
            },
            func=self._run_read_only_command,
            is_read_only=True
        ))

        self.register(AgentTool(
            name="explain_command_flags",
            description="Deconstruct Linux command flags into plain English explanations and safety summaries.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command string to explain"}
                },
                "required": ["command"]
            },
            func=self._explain_command,
            is_read_only=True
        ))

        self.register(AgentTool(
            name="verify_command_safety",
            description="Verify AST safety risk score (0.0 to 1.0), safety level tier, and rollback command for a proposed shell command.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Proposed shell command"}
                },
                "required": ["command"]
            },
            func=self._verify_safety,
            is_read_only=True
        ))

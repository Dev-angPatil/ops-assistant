"""
Embedded HTTP REST & SSE Streaming Server for the Linux Ops Assistant GUI.
Zero external dependencies — standard library Python 3.9+ HTTP server.
"""

from __future__ import annotations

import os
import sys
import json
import time
import uuid
import queue
import shutil
import urllib.parse
import webbrowser
import threading
from pathlib import Path
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from ops_assistant.agent import OpsAssistantAgent
from ops_assistant.collectors.hub import TelemetryHub
from ops_assistant.collectors.distro_detector import DistroDetector
from ops_assistant.tools.executor import SafeExecutor
from ops_assistant.tools.safety import CommandSafetyValidator
from ops_assistant.tools.sandbox_probe import EphemeralSandboxProbe
from ops_assistant.tools import desktop_ops, download_ops, storage_ops, process_ops, network_ops, log_ops
from ops_assistant.models import SafetyLevel
from ops_assistant.explainer.xai import ExecutionOutcomeExplainer


STATIC_DIR = Path(__file__).parent / "static"

# ---------------------------------------------------------------------------
# CommandCenter Session Store — thread-safe in-memory dict, 5-min TTL
# ---------------------------------------------------------------------------
_COMMAND_SESSIONS: Dict[str, Any] = {}
_SESSIONS_LOCK = threading.Lock()
_SESSION_TTL = 300  # seconds


def _create_session(data: Dict[str, Any]) -> str:
    session_id = str(uuid.uuid4())
    with _SESSIONS_LOCK:
        _COMMAND_SESSIONS[session_id] = {
            "created_at": time.time(),
            "events_queue": queue.Queue(),
            "events_log": [],
            **data,
        }
    return session_id


def _get_session(session_id: str) -> Optional[Dict[str, Any]]:
    with _SESSIONS_LOCK:
        sess = _COMMAND_SESSIONS.get(session_id)
        if sess is None:
            return None
        if time.time() - sess.get("created_at", 0) > _SESSION_TTL:
            del _COMMAND_SESSIONS[session_id]
            return None
        return sess


class OpsAssistantHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    agent: OpsAssistantAgent = None
    hub: TelemetryHub = None
    executor: SafeExecutor = None

    def log_message(self, format, *args):
        # Suppress noisy access logs
        pass

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message: str, status: int = 400):
        self._send_json({"error": message, "success": False}, status=status)

    def _read_json(self) -> Dict[str, Any]:
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len > 0:
                raw = self.rfile.read(content_len).decode("utf-8")
                return json.loads(raw)
        except Exception:
            pass
        return {}

    def do_HEAD(self):
        self.do_GET()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. Root & Static Files
        if path in ("/", "/index.html"):
            self._serve_static_file("index.html", "text/html")
            return
        elif path.startswith("/static/") or path.startswith("/assets/"):
            if path.startswith("/static/"):
                rel_name = path[len("/static/"):]
            else:
                rel_name = "assets/" + path[len("/assets/"):]
            ext = os.path.splitext(rel_name)[1].lower()
            mime_map = {
                ".css": "text/css",
                ".js": "application/javascript",
                ".html": "text/html",
                ".json": "application/json",
                ".svg": "image/svg+xml",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".ico": "image/x-icon"
            }
            mime = mime_map.get(ext, "application/octet-stream")
            self._serve_static_file(rel_name, mime)
            return

        # 2. Server-Sent Events (SSE) Live Telemetry Stream
        elif path == "/api/stream/telemetry":
            self._handle_telemetry_sse()
            return

        # 3. REST API Endpoints
        elif path == "/api/health":
            distro_override = query.get("distro", [None])[0]
            snap = self.hub.get_health_snapshot(distro_override=distro_override)
            self._send_json(snap.to_dict())
            return

        elif path == "/api/services":
            services = self._get_services_list()
            self._send_json({"services": services, "count": len(services)})
            return

        elif path == "/api/processes":
            n = int(query.get("n", [50])[0])
            procs_res = process_ops.list_processes(sort_by="cpu", top_n=n)
            self._send_json({"processes": procs_res.get("processes", []), "count": len(procs_res.get("processes", []))})
            return

        elif path == "/api/storage/analysis":
            raw_path = query.get("path", ["/"])[0]
            snap = self.hub.get_health_snapshot()
            large_res = storage_ops.find_large_files(search_path=raw_path, threshold_mb=100, top_n=20)
            self._send_json({
                "disks": [asdict(d) if hasattr(d, "__dataclass_fields__") else d.__dict__ for d in snap.disks],
                "large_files": large_res.get("files", [])
            })
            return

        elif path == "/api/network/status":
            interfaces = network_ops.show_interfaces()
            ports = network_ops.show_listening_ports()
            fw = network_ops.show_firewall_rules()
            self._send_json({
                "interfaces": interfaces.get("interfaces", []),
                "ports": ports.get("ports", []),
                "firewall": fw
            })
            return

        elif path == "/api/taxonomy/scenarios":
            scenarios = []
            for item in self.agent.FAILURE_TAXONOMY:
                scenarios.append({
                    "id": item.get("id"),
                    "symptom": item.get("symptom"),
                    "root_cause": item.get("root_cause"),
                    "rationale": item.get("rationale"),
                    "commands": [
                        {
                            "command": cmd[0],
                            "safety_level": cmd[1].value if hasattr(cmd[1], "value") else str(cmd[1]),
                            "risk_score": cmd[2],
                            "rationale": cmd[3]
                        }
                        for cmd in item.get("commands", [])
                    ]
                })
            self._send_json({"scenarios": scenarios, "count": len(scenarios)})
            return

        elif path == "/api/hardware/profile":
            from ops_assistant.hardware.advisor import HardwareAdvisor
            adv = HardwareAdvisor().get_full_advisory()
            self._send_json(adv)
            return

        elif path == "/api/setup/status":
            from ops_assistant.hardware.advisor import HardwareAdvisor, MODEL_CATALOG
            from ops_assistant.model_manager.downloader import ModelDownloader
            from ops_assistant.config import get_config, is_setup_completed
            from ops_assistant.install_tracker import get_tracker
            adv = HardwareAdvisor()
            prof = adv.profiler.profile()
            rec = adv.get_full_advisory()["recommended_model"]
            dl = ModelDownloader()
            cfg = get_config()
            tracker = get_tracker()
            self._send_json({
                "setup_completed": is_setup_completed(),
                "install_phase": cfg.get("install_phase", "complete"),
                "pending_model_key": cfg.get("pending_model_key"),
                "active_model_key": cfg.get("active_model_key"),
                "has_models": dl.has_any_model_installed(),
                "config": cfg,
                "hardware": prof.to_dict(),
                "recommended_model": rec,
                "catalog": MODEL_CATALOG,
                "installed_models": dl.list_available_models(),
                "download_progress": dl.get_download_progress(),
                "tracker_status": tracker.get_status(),
            })
            return

        elif path == "/api/install-status":
            from ops_assistant.install_tracker import get_tracker
            from ops_assistant.config import get_config
            from ops_assistant.model_manager.downloader import ModelDownloader
            tracker = get_tracker()
            cfg = get_config()
            st = tracker.get_status()
            dl = ModelDownloader()
            self._send_json({
                "status": st,
                "install_phase": cfg.get("install_phase", "complete"),
                "pending_model_key": cfg.get("pending_model_key"),
                "active_model_key": cfg.get("active_model_key"),
                "provider": cfg.get("provider", "deterministic"),
                "downloads": dl.get_download_progress(),
                "installed_models": dl.list_available_models(),
            })
            return

        elif path == "/api/models/list":
            from ops_assistant.model_manager.downloader import ModelDownloader
            dl = ModelDownloader()
            active_p = dl.get_active_model_path()
            self._send_json({
                "models": dl.list_available_models(),
                "active_model_path": str(active_p) if active_p else None
            })
            return

        elif path == "/api/models/download/progress":
            from ops_assistant.model_manager.downloader import ModelDownloader
            dl = ModelDownloader()
            self._send_json({"downloads": dl.get_download_progress()})
            return

        elif path == "/api/proactive/audit":
            from ops_assistant.tools import proactive_engine
            res = proactive_engine.run_proactive_audit()
            self._send_json(res)
            return

        elif path == "/api/docker/status":
            from ops_assistant.tools import docker_ops
            containers = docker_ops.list_containers(all_containers=True)
            conflicts = docker_ops.inspect_container_conflicts()
            self._send_json({
                "containers": containers.get("containers", []),
                "conflicts": conflicts.get("conflicts", []),
                "count": containers.get("count", 0),
                "running_count": containers.get("running_count", 0),
                "failed_count": containers.get("failed_count", 0)
            })
            return

        elif path == "/api/security/audit":
            from ops_assistant.tools import security_ops
            res = security_ops.audit_security()
            self._send_json(res)
            return

        elif path == "/api/backups":
            from ops_assistant.tools import backup_ops
            res = backup_ops.list_backups()
            self._send_json(res)
            return

        elif path == "/api/system/boot":
            from ops_assistant.tools import system_ops
            res = system_ops.analyze_boot_time()
            self._send_json(res)
            return

        elif path == "/api/distro":
            detector = DistroDetector()
            d_info = detector.detect()
            self._send_json(d_info.to_dict() if hasattr(d_info, "to_dict") else d_info.__dict__)
            return

        elif path == "/api/history/sessions":
            from ops_assistant.db.history_db import get_history_db
            sessions = get_history_db().list_sessions(limit=50)
            self._send_json({"sessions": sessions})
            return

        elif path == "/api/history/session":
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            sid = params.get("id", [""])[0]
            from ops_assistant.db.history_db import get_history_db
            history = get_history_db().get_session_history(sid)
            self._send_json({"session_id": sid, "history": history})
            return

        elif path == "/api/config/gemini":
            from ops_assistant.config import get_gemini_api_key, get_config
            cfg = get_config()
            key = get_gemini_api_key() or ""
            masked = f"{key[:4]}...{key[-4:]}" if len(key) >= 8 else ("****" if key else "")
            self._send_json({
                "configured": bool(key),
                "masked_key": masked,
                "model": cfg.get("gemini_model", "gemini-2.0-flash"),
                "provider": cfg.get("provider", "auto")
            })
            return

        elif path == "/api/system/cwd":
            from ops_assistant.config import get_working_dir
            self._send_json({"cwd": get_working_dir()})
            return

        elif path == "/api/autocomplete":
            from ops_assistant.nlp.autocomplete import get_autocomplete_engine
            q = query.get("q", [""])[0] or query.get("query", [""])[0]
            cwd = query.get("cwd", [None])[0]
            try:
                limit = int(query.get("limit", [8])[0])
            except (ValueError, TypeError):
                limit = 8
            engine = get_autocomplete_engine()
            suggs = engine.suggest(query=q, cwd=cwd, max_results=limit)
            self._send_json({
                "success": True,
                "query": q,
                "count": len(suggs),
                "suggestions": [s.to_dict() for s in suggs]
            })
            return

        elif path == "/api/sandbox/status":
            probe = EphemeralSandboxProbe()
            self._send_json(probe.get_status())
            return

        elif path == "/api/voice/status":
            from ops_assistant.voice.recorder import VoiceRecorder
            rec = VoiceRecorder()
            avail, details = rec.is_microphone_available()
            self._send_json({
                "success": True,
                "available": avail,
                "details": details,
                "supported_languages": [
                    {"code": "en-IN", "label": "English (India)"},
                    {"code": "hi-IN", "label": "Hinglish / Hindi"},
                    {"code": "en-US", "label": "English (US)"},
                    {"code": "en-GB", "label": "English (UK)"}
                ]
            })
            return

        elif path == "/api/installer/sources":
            from ops_assistant.installer.sources import SourceResolver
            caps = SourceResolver.probe_host()
            self._send_json(caps.to_dict())
            return

        elif path == "/api/installer/project-detect":
            from ops_assistant.installer.project_detector import ProjectDependencyDetector
            from ops_assistant.config import get_working_dir
            cwd_target = query.get("cwd", [get_working_dir()])[0]
            distro_override = query.get("distro", [None])[0]
            plan = ProjectDependencyDetector.detect_and_plan(root_dir=cwd_target, distro_family=distro_override or "arch")
            if plan:
                self._send_json({"detected": True, "plan": plan.to_dict()})
            else:
                self._send_json({"detected": False, "message": "No recognized project dependency manifest found."})
            return

        elif path == "/api/installer/catalog":
            from ops_assistant.installer.knowledge_base import APP_CATALOG
            self._send_json({"catalog": APP_CATALOG, "count": len(APP_CATALOG)})
            return

        elif path.startswith("/api/installer/stream/"):
            session_id = path[len("/api/installer/stream/"):]
            self._handle_command_stream_sse(session_id)
            return

        elif path.startswith("/api/command/stream/"):
            session_id = path[len("/api/command/stream/"):]
            self._handle_command_stream_sse(session_id)
            return

        elif path == "/api/terminal/status":
            from ops_assistant.tools.terminal_fallback import TerminalFallbackDetector
            term = TerminalFallbackDetector.find_available_terminal_emulator()
            can_launch = bool(term is not None and ("DISPLAY" in os.environ or "WAYLAND_DISPLAY" in os.environ))
            self._send_json({
                "success": True,
                "supported": can_launch,
                "terminal": term,
                "display_active": bool("DISPLAY" in os.environ or "WAYLAND_DISPLAY" in os.environ)
            })
            return

        else:
            self._send_error("Endpoint not found", status=404)


    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Voice Transcription Endpoint
        if path == "/api/voice/transcribe":
            content_type = self.headers.get("Content-Type", "")
            content_len = int(self.headers.get("Content-Length", 0))
            from ops_assistant.voice.transcriber import SpeechTranscriber, PhoneticNormalizer
            transcriber = SpeechTranscriber()

            if "application/json" in content_type:
                body = self._read_json()
                raw_text = body.get("text", "").strip()
                lang = body.get("language", "en-IN")
                if raw_text:
                    clean = PhoneticNormalizer.normalize(raw_text)
                    self._send_json({
                        "success": True,
                        "text": clean,
                        "raw_text": raw_text,
                        "confidence": 0.95,
                        "engine": "web_speech_normalized"
                    })
                    return
                elif "audio_base64" in body:
                    import base64
                    try:
                        wav_data = base64.b64decode(body["audio_base64"])
                        res = transcriber.transcribe_wav_bytes(wav_data, language=lang)
                        self._send_json(res)
                        return
                    except Exception as e:
                        self._send_error(f"Base64 audio decode failed: {e}")
                        return

            # Raw binary WAV upload
            if content_len > 0:
                raw_audio = self.rfile.read(content_len)
                res = transcriber.transcribe_wav_bytes(raw_audio)
                self._send_json(res)
                return

            self._send_error("No audio data or text provided for transcription.")
            return

        body = self._read_json()

        # 1. AI Agent Interactive Chat & Command Dispatch
        if path == "/api/agent/chat":
            prompt = body.get("prompt", "").strip()
            if not prompt:
                self._send_error("Prompt is required")
                return
            context = body.get("context", {})
            execute = bool(body.get("execute", True))
            result = self.agent.execute_agent_action(prompt, context=context, execute=execute)
            self._send_json(result)
            return

        # 1.1 Autocomplete Suggestions (POST)
        elif path == "/api/autocomplete":
            from ops_assistant.nlp.autocomplete import get_autocomplete_engine
            q = body.get("query", "") or body.get("q", "")
            cwd = body.get("cwd")
            try:
                limit = int(body.get("limit", 8))
            except (ValueError, TypeError):
                limit = 8
            engine = get_autocomplete_engine()
            suggs = engine.suggest(query=q, cwd=cwd, max_results=limit)
            self._send_json({
                "success": True,
                "query": q,
                "count": len(suggs),
                "suggestions": [s.to_dict() for s in suggs]
            })
            return

        # 2. Diagnostics
        elif path == "/api/diagnose":
            query = body.get("query", "").strip()
            distro_override = body.get("distro")
            if not query:
                self._send_error("Query is required")
                return
            report = self.agent.diagnose(query, distro_override=distro_override)
            self._send_json(report.to_dict())
            return

        # 3. Desktop Actions
        elif path == "/api/desktop/action":
            action = body.get("action")
            target_path = body.get("path", "~")
            url = body.get("url", "https://google.com")
            src = body.get("src", "")
            dst = body.get("dst", "")

            if action == "open_folder":
                res = desktop_ops.open_folder(target_path)
            elif action == "open_file":
                res = desktop_ops.open_file(target_path)
            elif action == "open_image":
                res = desktop_ops.open_image(target_path)
            elif action == "open_browser":
                res = desktop_ops.open_browser(url)
            elif action == "move_path":
                res = desktop_ops.move_path(src, dst)
            elif action == "copy_path":
                res = desktop_ops.copy_path(src, dst)
            elif action == "trash_path":
                res = desktop_ops.trash_path(target_path)
            else:
                res = {"success": False, "error": f"Unknown desktop action: {action}"}
            self._send_json(res)
            return

        # 4. Universal Downloader
        elif path == "/api/download":
            url = body.get("url", "").strip()
            dest_dir = body.get("destination_dir", "~/Downloads")
            filename = body.get("filename")
            auto_extract = bool(body.get("auto_extract", False))

            if not url:
                self._send_error("URL is required for download")
                return

            res = download_ops.download_file(
                url=url,
                destination_dir=dest_dir,
                filename=filename,
                auto_extract=auto_extract
            )
            self._send_json(res)
            return

        # 5. Service Controller
        elif path == "/api/services/action":
            svc = body.get("service", "").strip()
            action = body.get("action", "status").strip()
            if not svc:
                self._send_error("Service name required")
                return

            if action == "logs":
                res = log_ops.tail_log(service=svc, lines=100)
            elif action == "start":
                res = process_ops.start_service(svc)
            elif action == "stop":
                res = process_ops.stop_service(svc)
            elif action == "restart":
                res = process_ops.restart_service(svc)
            elif action == "reload":
                res = process_ops.reload_service(svc)
            elif action == "enable":
                res = process_ops.enable_service(svc)
            elif action == "disable":
                res = process_ops.disable_service(svc)
            elif action == "status":
                res = process_ops.show_service_status(svc)
            else:
                res = {"success": False, "error": f"Unknown service action: {action}"}
            self._send_json(res)
            return

        # 6. Process Kill
        elif path == "/api/processes/kill":
            pid = body.get("pid")
            sig = str(body.get("signal", "TERM"))
            if not pid:
                self._send_error("PID required")
                return
            res = process_ops.kill_process(pid=int(pid), signal=sig)
            self._send_json(res)
            return

        # 7. Storage Organisation & Cleaning
        elif path == "/api/storage/organise":
            target_path = body.get("path", "~/Downloads")
            dry_run = bool(body.get("dry_run", True))
            res = storage_ops.organise_directory(target_path, dry_run=dry_run)
            self._send_json(res)
            return

        elif path == "/api/storage/clean":
            dry_run = bool(body.get("dry_run", True))
            res = storage_ops.clean_logs(dry_run=dry_run)
            self._send_json(res)
            return

        # 8. Command Execution with AST Safety Guardrails, Sandbox Probe & Terminal Fallback
        elif path == "/api/execute":
            command = body.get("command", "").strip()
            dry_run = bool(body.get("dry_run", False))
            if not command:
                self._send_error("Command required")
                return

            from ops_assistant.tools.terminal_fallback import TerminalFallbackDetector
            from ops_assistant.config import get_working_dir

            # Safety validation
            val = CommandSafetyValidator.validate(command)
            if val.level == SafetyLevel.DESTRUCTIVE:
                fallback = TerminalFallbackDetector.build_fallback_payload(
                    command_or_commands=command,
                    returncode=1,
                    stdout="",
                    stderr=f"DESTRUCTIVE command blocked: {val.matched_rule}",
                    blocked=True,
                    safety_level=val.level,
                    risk_score=val.risk_score,
                    cwd=get_working_dir()
                )
                self._send_json({
                    "success": False,
                    "blocked": True,
                    "safety_level": val.level.value,
                    "risk_score": val.risk_score,
                    "error": f"DESTRUCTIVE command blocked: {val.matched_rule}",
                    "command": command,
                    "terminal_fallback": fallback.to_dict()
                }, status=403)
                return

            # Run Ephemeral Sandbox Verification probe
            probe = EphemeralSandboxProbe()
            probe_result = probe.verify_command(command)

            res = self.executor.execute(command, dry_run=dry_run)
            returncode = res.get("returncode", -1)

            # Generate comprehensive natural language outcome and system changes explanation
            outcome = ExecutionOutcomeExplainer.explain_outcome(
                command=command,
                returncode=returncode,
                stdout=res.get("stdout", ""),
                stderr=res.get("stderr", ""),
                query=body.get("query"),
                elapsed_ms=res.get("elapsed_ms", 0.0),
                context={"cwd": get_working_dir()},
                llm_provider=getattr(self.agent, "llm_provider", None) if self.agent else None
            )

            fallback = outcome.get("terminal_fallback")
            if not fallback:
                fallback_obj = TerminalFallbackDetector.build_fallback_payload(
                    command_or_commands=command,
                    returncode=returncode,
                    stdout=res.get("stdout", ""),
                    stderr=res.get("stderr", ""),
                    safety_level=val.level,
                    risk_score=val.risk_score,
                    cwd=get_working_dir()
                )
                fallback = fallback_obj.to_dict()

            self._send_json({
                "success": returncode == 0,
                "returncode": returncode,
                "stdout": res.get("stdout", ""),
                "stderr": res.get("stderr", ""),
                "latency_ms": res.get("elapsed_ms", 0.0),
                "command": command,
                "safety_level": val.level.value,
                "risk_score": val.risk_score,
                "dry_run": dry_run,
                "rollback_command": val.suggested_rollback,
                "sandbox_probe": probe_result.to_dict(),
                "explanation_paragraph": outcome.get("explanation_paragraph", ""),
                "natural_explanation": outcome.get("natural_explanation", ""),
                "ai_explanation": outcome.get("ai_elaboration") or outcome.get("natural_explanation", ""),
                "changes_made": outcome.get("changes_made", []),
                "changes_summary": outcome.get("changes_summary", ""),
                "failure_analysis": outcome.get("failure_analysis"),
                "terminal_fallback": fallback
            })
            return

        # 8a. Dedicated GUI-to-Terminal Fallback Payload Resolution Endpoint
        elif path == "/api/terminal/fallback":
            from ops_assistant.tools.terminal_fallback import TerminalFallbackDetector
            from ops_assistant.config import get_working_dir
            cmd = body.get("command") or body.get("commands", "")
            rc = int(body.get("returncode", 0))
            stdout_val = body.get("stdout", "")
            stderr_val = body.get("stderr", "")
            blocked_val = bool(body.get("blocked", False))
            cwd_val = body.get("cwd") or get_working_dir()
            payload = TerminalFallbackDetector.build_fallback_payload(
                command_or_commands=cmd,
                returncode=rc,
                stdout=stdout_val,
                stderr=stderr_val,
                blocked=blocked_val,
                cwd=cwd_val,
                force_fallback=bool(body.get("force", False))
            )
            self._send_json({"success": True, "fallback": payload.to_dict()})
            return

        # 8a2. Launch Command in Desktop Terminal Emulator
        elif path == "/api/terminal/run":
            from ops_assistant.tools.terminal_fallback import TerminalFallbackDetector
            from ops_assistant.config import get_working_dir
            cmd = body.get("command", "").strip()
            if not cmd:
                self._send_error("Command required to launch in terminal")
                return
            cwd_val = body.get("cwd") or get_working_dir()
            hold_open = bool(body.get("hold_open", True))
            res = TerminalFallbackDetector.launch_command_in_desktop_terminal(
                command=cmd,
                cwd=cwd_val,
                hold_open=hold_open
            )
            self._send_json(res)
            return



        # 8b. Dedicated Ephemeral Sandbox Probe Verification Endpoint
        elif path == "/api/sandbox/verify":
            command = body.get("command", "").strip()
            if not command:
                self._send_error("Command required")
                return
            probe = EphemeralSandboxProbe()
            probe_res = probe.verify_command(command)
            self._send_json(probe_res.to_dict())
            return

        # 9. Rollback Execution
        elif path == "/api/rollback":
            rollback_cmd = body.get("rollback_command", "").strip()
            if not rollback_cmd:
                self._send_error("Rollback command required")
                return
            res = self.executor.execute(rollback_cmd)
            returncode = res.get("returncode", -1)
            self._send_json({
                "success": returncode == 0,
                "returncode": returncode,
                "stdout": res.get("stdout", ""),
                "stderr": res.get("stderr", ""),
                "command": rollback_cmd
            })
            return

        # 10. Firewall Rule Update
        elif path == "/api/network/firewall":
            action = body.get("action")
            port = body.get("port")
            proto = body.get("proto", "tcp")
            if action == "allow" and port:
                res = network_ops.allow_port(port, proto)
            elif action == "deny" and port:
                res = network_ops.deny_port(port, proto)
            else:
                res = {"success": False, "error": "Invalid firewall parameters"}
            self._send_json(res)
            return

        # 11. Hardware Auto-Tune & Model Selection
        elif path == "/api/hardware/tune":
            from ops_assistant.hardware.advisor import HardwareAdvisor, ModelSelector
            from ops_assistant.model_manager.downloader import ModelDownloader
            adv = HardwareAdvisor()
            prof = adv.profiler.profile()
            rec = ModelSelector.recommend_model(prof)
            dl = ModelDownloader()
            if rec.get("download_required") and rec.get("model_key"):
                mkey = rec["model_key"]
                avail = dl.list_available_models()
                if mkey in avail and not avail[mkey]["is_downloaded"]:
                    try:
                        dl.download_model(mkey)
                    except Exception:
                        pass
            self._send_json({"success": True, "advisory": adv.get_full_advisory(), "recommended_model": rec})
            return

        # 11b. Setup Configuration Apply
        elif path == "/api/setup/apply":
            from ops_assistant.config import set_setup_completed, get_config
            from ops_assistant.hardware.advisor import MODEL_CATALOG, HardwareAdvisor
            from ops_assistant.model_manager.downloader import ModelDownloader
            provider = body.get("provider", "auto")
            model_key = body.get("model_key")
            adv = HardwareAdvisor()
            prof = adv.profiler.profile()
            caps = adv.generate_capability_matrix(prof)

            dl = ModelDownloader()
            model_path = None
            if model_key and model_key in MODEL_CATALOG:
                m_info = MODEL_CATALOG[model_key]
                p = dl.target_dir / m_info["filename"]
                if p.exists():
                    model_path = str(p)

            res_cfg = set_setup_completed(
                provider=provider,
                model_key=model_key,
                model_path=model_path,
                hardware_tier=prof.compute_tier,
                threads=caps.recommended_threads,
                ctx_size=caps.recommended_ctx_size,
                gpu_layers=caps.recommended_gpu_layers
            )
            self._send_json({"success": True, "config": res_cfg})
            return

        # 11c. Background Model Download
        elif path == "/api/models/download":
            from ops_assistant.model_manager.downloader import ModelDownloader
            mkey = body.get("model_key", "")
            force = bool(body.get("force", False))
            dl = ModelDownloader()
            res = dl.start_background_download(mkey, force=force)
            self._send_json(res)
            return

        # 11d. Switch Active AI Model
        elif path == "/api/models/switch":
            from ops_assistant.config import finalize_enhancement, set_setup_completed, get_config
            from ops_assistant.model_manager.downloader import ModelDownloader
            from ops_assistant.hardware.advisor import MODEL_CATALOG, HardwareAdvisor

            mkey = body.get("model_key", "").strip()
            provider = body.get("provider", "gguf")

            if mkey == "deterministic" or provider == "deterministic":
                res_cfg = set_setup_completed(provider="deterministic")
                self._send_json({"success": True, "message": "Switched active engine to Deterministic Fast-Path (0 MB)", "config": res_cfg})
                return
            elif mkey == "ollama" or provider == "ollama":
                res_cfg = set_setup_completed(provider="ollama")
                self._send_json({"success": True, "message": "Switched active engine to Ollama backend", "config": res_cfg})
                return

            dl = ModelDownloader()
            avail = dl.list_available_models()
            if mkey not in avail or not avail[mkey]["is_downloaded"]:
                self._send_json({"success": False, "error": f"Model '{mkey}' is not downloaded yet. Please download it first."})
                return

            adv = HardwareAdvisor()
            prof = adv.profiler.profile()
            caps = adv.generate_capability_matrix(prof)
            res_cfg = finalize_enhancement(
                model_key=mkey,
                model_path=avail[mkey]["local_path"],
                hardware_tier=prof.compute_tier,
                threads=caps.recommended_threads,
                ctx_size=caps.recommended_ctx_size,
                gpu_layers=caps.recommended_gpu_layers,
                provider="gguf"
            )
            self._send_json({"success": True, "message": f"Successfully activated '{mkey}' for local inference", "config": res_cfg})
            return

        # 12. Docker Actions
        elif path == "/api/docker/action":
            from ops_assistant.tools import docker_ops
            act = body.get("action")
            cid = body.get("container", "")
            if act == "restart":
                res = docker_ops.restart_container(cid)
            elif act == "logs":
                res = docker_ops.get_container_logs(cid, tail=body.get("tail", 100))
            elif act == "prune":
                res = docker_ops.prune_docker_resources(dry_run=bool(body.get("dry_run", True)))
            else:
                res = {"success": False, "error": f"Unknown docker action: {act}"}
            self._send_json(res)
            return

        # 13. Backup & Restore Actions
        elif path == "/api/backup/create":
            from ops_assistant.tools import backup_ops
            path_target = body.get("path", "/etc")
            dest = body.get("dest", "~/.ops_assistant/backups")
            res = backup_ops.create_backup(path_target, backup_dir=dest)
            self._send_json(res)
            return

        elif path == "/api/backup/restore":
            from ops_assistant.tools import backup_ops
            backup_file = body.get("backup_file", "")
            destination = body.get("destination", "")
            res = backup_ops.restore_backup(backup_file, destination)
            self._send_json(res)
            return

        # 14. System Maintenance Actions
        elif path == "/api/system/action":
            from ops_assistant.tools import system_ops
            act = body.get("action")
            if act == "vacuum_journal":
                res = system_ops.vacuum_journal(max_size=body.get("max_size", "200M"), dry_run=bool(body.get("dry_run", True)))
            elif act == "trim_ssds":
                res = system_ops.trim_ssds(dry_run=bool(body.get("dry_run", True)))
            elif act == "clean_packages":
                res = system_ops.clean_package_cache(dry_run=bool(body.get("dry_run", True)))
            else:
                res = {"success": False, "error": f"Unknown system action: {act}"}
            self._send_json(res)
            return

        # 15. CommandCenter — Intent interpretation (plan without execution)
        elif path == "/api/command/interpret":
            text = body.get("text", "").strip()
            if not text:
                self._send_error("text field is required")
                return
            interpretation = self.agent.interpret_command(text)
            session_id = _create_session({
                "text": text,
                "understanding": interpretation["understanding"],
                "plan_steps": interpretation["plan_steps"],
                "requires_confirmation": interpretation["requires_confirmation"],
                "safety_level": interpretation["safety_level"],
                "intent": interpretation["intent"],
            })
            self._send_json({
                "session_id": session_id,
                "understanding": interpretation["understanding"],
                "plan_steps": interpretation["plan_steps"],
                "requires_confirmation": interpretation["requires_confirmation"],
                "safety_level": interpretation["safety_level"],
                "intent": interpretation["intent"],
                "confidence": interpretation.get("confidence", 1.0),
            })
            return

        # 16. CommandCenter — Execute a confirmed plan, stream results via SSE
        elif path == "/api/command/execute":
            session_id = body.get("session_id", "").strip()
            confirmed = bool(body.get("confirmed", False))
            if not session_id:
                self._send_error("session_id is required")
                return
            sess = _get_session(session_id)
            if not sess:
                self._send_error("Session not found or expired", status=404)
                return
            # Server-side confirmation gate — HIGH_RISK / DESTRUCTIVE require confirmed=true
            if sess.get("requires_confirmation") and not confirmed:
                self._send_json({
                    "blocked": True,
                    "error": "This action requires explicit confirmation (HIGH_RISK or DESTRUCTIVE). "
                             "Set confirmed: true to proceed.",
                    "safety_level": sess.get("safety_level"),
                    "requires_confirmation": True,
                }, status=403)
                return
            # Launch execution in a background thread; results stream via SSE
            t = threading.Thread(
                target=self._execute_plan_async,
                args=(session_id, sess),
                daemon=True,
            )
            t.start()
            self._send_json({"success": True, "session_id": session_id, "message": "Execution started"})
            return

        elif path == "/api/config/gemini":
            from ops_assistant.config import set_gemini_api_key, get_config, save_config
            from ops_assistant.agent import GeminiProvider
            api_key = body.get("api_key", "").strip()
            model = body.get("model", "").strip()
            if api_key:
                set_gemini_api_key(api_key)
            cfg = get_config()
            if model:
                cfg["gemini_model"] = model
            if body.get("set_provider"):
                cfg["provider"] = "gemini"
            save_config(cfg)
            # Reinitialize agent provider
            self.agent.llm_provider = GeminiProvider(api_key=api_key or None, model=model)
            self._send_json({"success": True, "message": "Gemini configuration updated successfully."})
            return

        elif path == "/api/history/delete":
            sid = body.get("session_id", "").strip()
            from ops_assistant.db.history_db import get_history_db
            get_history_db().delete_session(sid)
            self._send_json({"success": True, "session_id": sid})
            return

        elif path == "/api/history/clear":
            from ops_assistant.db.history_db import get_history_db
            get_history_db().clear_all()
            self._send_json({"success": True, "message": "History cleared."})
            return

        elif path == "/api/command/explain":
            cmd = body.get("command", "").strip()
            if not cmd:
                self._send_error("Command field is required")
                return
            explanation = self.agent.explain_command(cmd)
            self._send_json(explanation)
            return

        elif path == "/api/system/cwd":
            from ops_assistant.config import set_working_dir, get_working_dir
            new_dir = body.get("path", "").strip()
            if new_dir:
                ok = set_working_dir(new_dir)
                if not ok:
                    self._send_error(f"Directory not found: {new_dir}")
                    return
            self._send_json({"success": True, "cwd": get_working_dir()})
            return

        elif path == "/api/installer/resolve":
            from ops_assistant.installer.engine import PackageInstallerEngine
            from ops_assistant.config import get_working_dir
            q = body.get("query", "").strip()
            cwd = body.get("cwd") or get_working_dir()
            distro_override = body.get("distro")
            if not q:
                self._send_error("query is required for installation resolution")
                return
            engine = PackageInstallerEngine(distro_override=distro_override)
            plan = engine.resolve_plan(q, cwd=cwd, distro_override=distro_override)
            self._send_json({"success": True, "plan": plan.to_dict()})
            return

        elif path == "/api/installer/execute":
            from ops_assistant.installer.engine import PackageInstallerEngine
            from ops_assistant.config import get_working_dir
            raw_query = body.get("query", "").strip()
            plan_dict = body.get("plan")
            confirmed = bool(body.get("confirmed", False))
            cwd = body.get("cwd") or get_working_dir()
            distro_override = body.get("distro")

            engine = PackageInstallerEngine(distro_override=distro_override)
            if raw_query:
                plan = engine.resolve_plan(raw_query, cwd=cwd, distro_override=distro_override)
            elif plan_dict:
                plan = engine.resolve_plan(plan_dict.get("query", ""), cwd=cwd, distro_override=distro_override)
            else:
                self._send_error("query or plan is required")
                return

            if plan.requires_confirmation and not confirmed:
                self._send_json({
                    "blocked": True,
                    "error": "This installation requires root / sudo permissions. Please confirm to proceed.",
                    "requires_confirmation": True,
                    "plan": plan.to_dict()
                }, status=403)
                return

            session_id = _create_session({
                "text": f"Install {plan.target_name}",
                "understanding": f"Installing {plan.target_name} ({plan.source_label})",
                "plan_steps": [s.to_dict() for s in plan.steps],
                "requires_confirmation": plan.requires_confirmation,
                "safety_level": plan.safety_level.value if hasattr(plan.safety_level, "value") else str(plan.safety_level),
                "intent": "package_install",
                "install_plan": plan.to_dict(),
            })

            t = threading.Thread(
                target=self._execute_installer_async,
                args=(session_id, plan),
                daemon=True,
            )
            t.start()
            self._send_json({"success": True, "session_id": session_id, "plan": plan.to_dict(), "message": "Installation started"})
            return

        elif path == "/api/installer/cancel":
            sid = body.get("session_id", "").strip()
            sess = _get_session(sid)
            if sess:
                sess["cancelled"] = True
                q = sess.get("events_queue")
                if q:
                    q.put({"type": "cancelled", "data": {"message": "Installation cancelled."}})
                    q.put(None)
            self._send_json({"success": True, "message": "Cancellation registered."})
            return

        else:
            self._send_error("Endpoint not found", status=404)

    def _execute_installer_async(self, session_id: str, plan: Any):
        sess = _get_session(session_id)
        if not sess:
            return
        from ops_assistant.installer.engine import PackageInstallerEngine
        from ops_assistant.installer.models import InstallProgressEvent
        from ops_assistant.db.history_db import get_history_db

        q: queue.Queue = sess["events_queue"]
        log: List[Dict[str, Any]] = sess["events_log"]

        def emit(event_type: str, data: Dict[str, Any]):
            entry = {"type": event_type, "data": data, "timestamp": time.time()}
            log.append(entry)
            q.put(entry)

        def progress_cb(ev: InstallProgressEvent):
            if sess.get("cancelled"):
                return
            emit("progress", ev.to_dict())

        engine = PackageInstallerEngine(distro_override=plan.distro_family)
        res = engine.execute_plan(plan, progress_callback=progress_cb, dry_run=False, session_id=session_id)

        emit("complete", res.to_dict())
        q.put(None)  # Sentinel

    def _serve_static_file(self, filename: str, mime: str):
        target = (STATIC_DIR / filename).resolve()
        resolved_static = STATIC_DIR.resolve()
        if not (target == resolved_static or target.is_relative_to(resolved_static)) or not target.exists() or not target.is_file():
            self._send_error("File not found", status=404)
            return

        try:
            with open(target, "rb") as f:
                content = f.read()
            content_type = f"{mime}; charset=utf-8" if ("text" in mime or "javascript" in mime or "json" in mime) else mime
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._send_error(str(e), status=500)

    # ------------------------------------------------------------------
    # CommandCenter SSE stream — drains per-session event queue
    # ------------------------------------------------------------------
    def _handle_command_stream_sse(self, session_id: str):
        sess = _get_session(session_id)
        if not sess:
            self._send_error("Session not found or expired", status=404)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        q: queue.Queue = sess["events_queue"]
        # Replay any events already logged (client connected after execution started)
        for ev in list(sess.get("events_log", [])):
            evt_type = ev["type"]
            data_str = json.dumps(ev["data"])
            try:
                self.wfile.write(f"event: {evt_type}\ndata: {data_str}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

        try:
            while True:
                try:
                    event = q.get(timeout=25)
                except queue.Empty:
                    # Keepalive comment
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue

                if event is None:
                    # Sentinel — execution complete
                    self.wfile.write(b"event: done\ndata: {}\n\n")
                    self.wfile.flush()
                    break

                evt_type = event["type"]
                data_str = json.dumps(event["data"])
                self.wfile.write(f"event: {evt_type}\ndata: {data_str}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ------------------------------------------------------------------
    # CommandCenter plan executor — runs in a background thread
    # ------------------------------------------------------------------
    def _execute_plan_async(self, session_id: str, sess: Dict[str, Any]):
        import subprocess as _sp
        import time
        from ops_assistant.config import get_working_dir
        from ops_assistant.db.history_db import get_history_db

        hdb = get_history_db()
        q: queue.Queue = sess["events_queue"]
        log: List[Dict[str, Any]] = sess["events_log"]

        def emit(event_type: str, data: Dict[str, Any]):
            entry = {"type": event_type, "data": data, "timestamp": time.time()}
            log.append(entry)
            q.put(entry)

        # 1. Emit understanding
        emit("understanding", {"text": sess.get("understanding", "")})

        # 2. Plan steps preview
        plan_steps = sess.get("plan_steps", [])
        for step in plan_steps:
            emit("plan_step", {**step, "status": "pending"})

        # 3. Execute each step and stream status transitions
        active_cwd = get_working_dir()
        for step in plan_steps:
            cmd = step.get("command", "").strip()
            emit("plan_step", {**step, "status": "running"})

            if not cmd:
                emit("plan_step", {**step, "status": "done", "exit_code": 0, "output": "Completed (no shell command)"})
                continue

            # Safety enforcement gate: ensure no destructive command ever executes via plan runner
            val = CommandSafetyValidator.validate(cmd)
            if val.level == SafetyLevel.DESTRUCTIVE:
                emit("plan_step", {
                    **step,
                    "status": "failed",
                    "exit_code": 1,
                    "output": f"Execution blocked: Command is DESTRUCTIVE ({val.matched_rule})",
                    "error_diagnosis": "Command was blocked by the safety validator due to risk of destructive data loss."
                })
                break

            t_start = time.time()
            try:
                proc = _sp.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=active_cwd
                )
                elapsed_ms = (time.time() - t_start) * 1000.0
                status = "done" if proc.returncode == 0 else "failed"
                output = (proc.stdout + proc.stderr).strip()

                diag = None
                if proc.returncode != 0:
                    diag = self.agent.explain_error(cmd, proc.returncode, stderr=proc.stderr, stdout=proc.stdout)

                outcome = ExecutionOutcomeExplainer.explain_outcome(
                    command=cmd,
                    returncode=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    query=step.get("description") or sess.get("text"),
                    elapsed_ms=elapsed_ms,
                    llm_provider=getattr(self.agent, "llm_provider", None) if self.agent else None
                )

                # Persist to database
                hdb.log_command(
                    session_id=session_id,
                    query=sess.get("text", cmd),
                    command=cmd,
                    intent=sess.get("intent", "action"),
                    safety_level=step.get("safety_level", "MODIFYING"),
                    risk_score=float(step.get("risk_score", 0.1)),
                    returncode=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    elapsed_ms=elapsed_ms,
                    explanation=step.get("description"),
                    rollback_command=step.get("rollback_command")
                )

                emit("plan_step", {
                    **step,
                    "status": status,
                    "exit_code": proc.returncode,
                    "output": output[:2000],
                    "error_diagnosis": diag,
                    "explanation_paragraph": outcome.get("explanation_paragraph", ""),
                    "natural_explanation": outcome.get("natural_explanation", ""),
                    "ai_explanation": outcome.get("ai_elaboration") or outcome.get("natural_explanation", ""),
                    "changes_made": outcome.get("changes_made", []),
                    "changes_summary": outcome.get("changes_summary", ""),
                    "failure_analysis": outcome.get("failure_analysis"),
                    "terminal_fallback": outcome.get("terminal_fallback")
                })

            except _sp.TimeoutExpired:
                from ops_assistant.tools.terminal_fallback import TerminalFallbackDetector
                fb_data = TerminalFallbackDetector.build_fallback_payload(
                    command_or_commands=cmd,
                    returncode=-1,
                    stdout="",
                    stderr="Command timed out after 30 s",
                    cwd=active_cwd
                )
                emit("plan_step", {
                    **step,
                    "status": "failed",
                    "exit_code": -1,
                    "output": "Command timed out after 30 s",
                    "terminal_fallback": fb_data.to_dict()
                })
            except Exception as exc:
                from ops_assistant.tools.terminal_fallback import TerminalFallbackDetector
                fb_data = TerminalFallbackDetector.build_fallback_payload(
                    command_or_commands=cmd,
                    returncode=-1,
                    stdout="",
                    stderr=str(exc),
                    cwd=active_cwd
                )
                emit("plan_step", {
                    **step,
                    "status": "failed",
                    "exit_code": -1,
                    "output": str(exc),
                    "terminal_fallback": fb_data.to_dict()
                })

        # 4. Build final result from log
        done_count = sum(1 for e in log if e["type"] == "plan_step" and e["data"].get("status") == "done")
        fail_count = sum(1 for e in log if e["type"] == "plan_step" and e["data"].get("status") == "failed")
        raw_output = "\n".join(
            e["data"].get("output", "") for e in log
            if e["type"] == "plan_step" and e["data"].get("status") in ("done", "failed") and e["data"].get("output")
        )

        from ops_assistant.tools.terminal_fallback import TerminalFallbackDetector
        all_plan_cmds = [s.get("command", "") for s in plan_steps if s.get("command")]
        plan_fallback = TerminalFallbackDetector.build_fallback_payload(
            command_or_commands=all_plan_cmds,
            returncode=0 if fail_count == 0 else 1,
            stdout=raw_output if fail_count == 0 else "",
            stderr=raw_output if fail_count > 0 else "",
            cwd=active_cwd,
            force_fallback=(fail_count > 0)
        )

        if not plan_steps:
            summary = "No executable steps were generated for this command."
            success = True
        elif fail_count == 0:
            summary = (
                f"All {done_count} step(s) completed successfully."
                if done_count > 1
                else "Step completed successfully."
            )
            success = True
        else:
            summary = f"{done_count} step(s) completed, {fail_count} failed."
            success = False

        emit("result", {
            "success": success,
            "summary": summary,
            "raw_output": raw_output,
            "exit_code": 0 if success else 1,
            "terminal_fallback": plan_fallback.to_dict()
        })


        # Sentinel to signal SSE client the stream is complete
        q.put(None)

    def _handle_telemetry_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            while True:
                snap = self.hub.get_health_snapshot()
                data_str = json.dumps(snap.to_dict())
                self.wfile.write(f"data: {data_str}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(1.5)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _get_services_list(self) -> List[Dict[str, Any]]:
        services = []
        if shutil.which("systemctl"):
            try:
                import subprocess
                p = subprocess.run(
                    ["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"],
                    capture_output=True, text=True, timeout=5
                )
                for line in p.stdout.strip().splitlines()[:100]:
                    parts = line.strip().split(None, 4)
                    if len(parts) >= 4:
                        unit = parts[0]
                        load = parts[1]
                        active = parts[2]
                        sub = parts[3]
                        desc = parts[4] if len(parts) > 4 else ""
                        services.append({
                            "unit": unit,
                            "load": load,
                            "active": active,
                            "sub": sub,
                            "description": desc
                        })
            except Exception:
                pass
        return services


def start_gui_server(
    host: str = "127.0.0.1",
    port: int = 8888,
    open_browser: bool = True,
    agent: Optional[OpsAssistantAgent] = None
) -> Tuple[ThreadingHTTPServer, str]:
    """
    Start the embedded GUI server in a background thread or main loop.
    Returns (server_instance, url).
    """
    if agent is None:
        agent = OpsAssistantAgent()

    hub = agent.hub if hasattr(agent, "hub") else TelemetryHub()
    executor = SafeExecutor()

    OpsAssistantHandler.agent = agent
    OpsAssistantHandler.hub = hub
    OpsAssistantHandler.executor = executor

    # Find available port if specified port is in use
    server = None
    actual_port = port
    for p in range(port, port + 50):
        try:
            server = ThreadingHTTPServer((host, p), OpsAssistantHandler)
            actual_port = p
            break
        except OSError:
            continue

    if server is None:
        raise RuntimeError(f"Could not bind GUI server to any port in range {port}-{port+50}")

    url = f"http://{host}:{actual_port}"
    print(f"[*] AI Linux Ops Assistant GUI running at: {url}")

    if open_browser:
        try:
            webbrowser.open(url, new=2)
        except Exception:
            pass

    return server, url
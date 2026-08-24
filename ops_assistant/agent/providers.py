"""Pluggable LLM Inference Providers with Tool-Calling & Structured Synthesis."""

import os
import re
import json
import time
import urllib.request
from typing import Dict, Any, List, Optional, Tuple, Union

from ops_assistant.models import SafetyLevel


def _enrich_command_metadata(cmd_data: Dict[str, Any], query: str = "") -> Dict[str, Any]:
    """Ensures a parsed command dictionary has complete and accurate safety and rollback metadata."""
    cmd = cmd_data.get("command", "").strip()
    if not cmd:
        return cmd_data

    # Deterministically calculate safety & risk if missing or unclassified
    try:
        from ops_assistant.tools.safety import CommandSafetyValidator
        validator = CommandSafetyValidator()
        lvl, risk, reason = validator.evaluate_safety(cmd)
        if "safety_level" not in cmd_data or not cmd_data["safety_level"]:
            cmd_data["safety_level"] = lvl.value
        if "risk_score" not in cmd_data or cmd_data["risk_score"] is None:
            cmd_data["risk_score"] = risk
    except Exception:
        cmd_data.setdefault("safety_level", "MODIFYING")
        cmd_data.setdefault("risk_score", 0.35)

    if not cmd_data.get("summary"):
        cmd_data["summary"] = f"Execute `{cmd}`"

    return cmd_data


def _parse_llm_json(raw: Optional[Union[str, Dict[str, Any]]], query: str = "") -> Optional[Dict[str, Any]]:
    """Robustly extracts and parses JSON objects, markdown code blocks, or shell commands from raw LLM responses."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return _enrich_command_metadata(raw, query)
    if not isinstance(raw, str):
        return None

    cleaned = raw.strip()
    if not cleaned:
        return None

    # 1. Direct JSON parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return _enrich_command_metadata(data, query)
    except Exception:
        pass

    # 2. Extract from markdown code fence ```json ... ``` or ```bash ... ``` or ```sh ... ```
    fence_m = re.search(r"```(?:json|bash|sh|zsh)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence_m:
        content = fence_m.group(1).strip()
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return _enrich_command_metadata(data, query)
        except Exception:
            pass
        # If code block is a raw shell command line
        if content and not content.startswith("{") and "\n" not in content:
            return _enrich_command_metadata({
                "command": content,
                "summary": f"Execute `{content}`",
                "safety_level": "MODIFYING",
                "risk_score": 0.30,
                "rollback_command": None
            }, query)

    # 3. Match outer { ... }
    brace_m = re.search(r"\{[\s\S]*\}", cleaned)
    if brace_m:
        try:
            data = json.loads(brace_m.group(0))
            if isinstance(data, dict):
                return _enrich_command_metadata(data, query)
        except Exception:
            pass

    # 4. Fallback: extract command candidate from raw lines
    lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
    for line in lines:
        stripped_line = line.strip("`$#").strip()
        tokens = stripped_line.split()
        if not tokens:
            continue
        first = tokens[0].lower()
        if first in ("here", "i", "you", "to", "sure", "the", "this", "note:", "explanation:"):
            continue
        if any(sym in stripped_line for sym in ("|", "&&", ";", ">", ">>")) or first in (
            "sudo", "apt", "dnf", "pacman", "apk", "systemctl", "service", "ls", "cat",
            "grep", "find", "ps", "kill", "mkdir", "rm", "cp", "mv", "touch", "tar",
            "unzip", "curl", "wget", "git", "journalctl", "dmesg", "df", "du", "free",
            "uptime", "ip", "ss", "netstat", "chmod", "chown", "pkill", "echo"
        ) or len(tokens) >= 1:
            return _enrich_command_metadata({
                "command": stripped_line,
                "summary": f"Execute `{stripped_line}`",
                "safety_level": "MODIFYING",
                "risk_score": 0.30,
                "rollback_command": None
            }, query)

    return None


class LLMProvider:
    """Base class for pluggable LLM inference backends with tool-calling capabilities."""

    def is_available(self) -> Tuple[bool, str]:
        raise NotImplementedError

    def generate_raw(self, prompt: str, max_tokens: int = 512, temperature: float = 0.2) -> Optional[str]:
        raise NotImplementedError

    def plan_observations(self, query: str, context: Dict[str, Any], tools_schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Given a user query and system context, decide which diagnostic tools to call."""
        return []

    def synthesize_diagnosis(self, query: str, context: Dict[str, Any], observations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Synthesize final root cause diagnosis and proposed remediation given observed tool evidence."""
        raise NotImplementedError

    def generate_diagnosis(self, query: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Direct diagnosis generation fallback."""
        return self.synthesize_diagnosis(query, context, observations=[])

    def generate_command(self, query: str, cwd: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Translate natural language request into a single Linux command with safety metadata."""
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    """Google Gemini API Provider with structured reasoning and tool execution."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        from ops_assistant.config import get_gemini_api_key, get_config
        self.api_key = api_key or get_gemini_api_key() or os.environ.get("GEMINI_API_KEY", "")
        cfg = get_config()
        self.model = model or cfg.get("gemini_model") or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    def is_available(self) -> Tuple[bool, str]:
        if not self.api_key or not self.api_key.strip():
            return False, "Gemini API key not configured (set GEMINI_API_KEY or configure in GUI/CLI)"
        return True, f"Ready (Gemini API: {self.model})"

    def _call_gemini_api(self, prompt: str, response_json: bool = True) -> Optional[str]:
        if not self.api_key:
            return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key.strip()}"
        gen_config: Dict[str, Any] = {
            "temperature": 0.2,
            "maxOutputTokens": 2048
        }
        if response_json:
            gen_config["responseMimeType"] = "application/json"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": gen_config
        }
        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
        except Exception:
            return None
        return None

    def plan_observations(self, query: str, context: Dict[str, Any], tools_schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ask LLM which tools to execute to investigate the issue."""
        distro_guide = (context.get("distro_prompt_context") or "").strip()
        distro_header = f"\nDistribution Rules & Context:\n{distro_guide}\n" if distro_guide else f"Distro: {context.get('distro_name')} ({context.get('family_id')})\n"
        prompt = (
            "You are an expert Linux SRE & Systems Diagnostics Agent. "
            "Given a user query about a Linux system issue, select 1 to 4 diagnostic tools to run in order to inspect the actual system state.\n\n"
            f"User Query: {query}\n"
            f"{distro_header}"
            f"Target Subsystem / Service: {context.get('subsystem')}\n\n"
            f"Available Tools Schema:\n{json.dumps(tools_schema, indent=2)}\n\n"
            "Respond strictly in JSON format as a list of tool call objects:\n"
            "[\n"
            '  {"tool": "<tool_name>", "arguments": {<args>}}\n'
            "]\n"
            "If no tools are needed, return []."
        )
        res = self._call_gemini_api(prompt, response_json=True)
        if not res:
            return []
        try:
            data = json.loads(res)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "tool_calls" in data:
                return data["tool_calls"]
            elif isinstance(data, dict) and "tool" in data:
                return [data]
        except Exception:
            pass
        return []

    def synthesize_diagnosis(self, query: str, context: Dict[str, Any], observations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Synthesize final diagnosis from observed evidence."""
        distro_guide = (context.get("distro_prompt_context") or "").strip()
        distro_header = f"\n=== Active Distribution Knowledge & Rules ===\n{distro_guide}\n" if distro_guide else f"Distro Environment: {context.get('distro_name', 'Linux')} (Init: {context.get('init_system', 'systemd')})\n"
        prompt = (
            "You are an expert Linux System Administrator and SRE. "
            "Analyze the sysadmin query along with live system telemetry and observed tool execution results.\n\n"
            f"User Query: {query}\n"
            f"{distro_header}"
            f"Observed Evidence / Tool Execution Outputs:\n{json.dumps(observations, indent=2, default=str)}\n\n"
            "Synthesize an accurate, evidence-backed diagnosis and safe remediation plan.\n"
            "Respond strictly in valid JSON format matching this schema:\n"
            "{\n"
            '  "symptom": "<concise description of what is failing>",\n'
            '  "root_cause": "<underlying technical root cause on Linux grounded in the observed evidence>",\n'
            '  "rationale": "<step-by-step diagnostic reasoning citing observed evidence>",\n'
            '  "causal_chain": ["<cause step 1>", "<cause step 2>", "<symptom>"],\n'
            '  "proposed_commands": [\n'
            '    ["<bash command>", "<READ_ONLY|MODIFYING|HIGH_RISK|DESTRUCTIVE>", <risk_score 0.05-1.0>, "<rationale for this command>"]\n'
            "  ],\n"
            '  "confidence": <confidence score between 0.0 and 1.0>\n'
            "}"
        )
        res = self._call_gemini_api(prompt, response_json=True)
        return _parse_llm_json(res)

    def generate_command(self, query: str, cwd: Optional[str] = None) -> Optional[Dict[str, Any]]:
        wd = cwd or os.getcwd()
        prompt = (
            "You are an expert Linux System Administrator AI. Translate the user's natural language request into the single most appropriate Linux command.\n"
            f"User Request: {query}\n"
            f"Current Directory: {wd}\n"
            f"User Home: {os.path.expanduser('~')}\n\n"
            "Respond in JSON format:\n"
            "{\n"
            '  "command": "<exact shell command>",\n'
            '  "summary": "<plain English explanation of what the command does>"\n'
            "}\n"
            "Or respond directly with the shell command in a ```bash code block."
        )
        res = self._call_gemini_api(prompt, response_json=False)
        return _parse_llm_json(res, query=query)


class OllamaProvider(LLMProvider):
    """Local Ollama inference provider."""

    def __init__(self, endpoint: str = "http://localhost:11434/api/generate", model: str = "llama3:8b"):
        self.endpoint = endpoint
        self.model = model

    def is_available(self) -> Tuple[bool, str]:
        try:
            req = urllib.request.Request(self.endpoint.replace("/generate", "/tags"))
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return True, f"Ready (Ollama: {self.model})"
        except Exception:
            pass
        return False, f"Ollama not reachable at {self.endpoint}"

    def generate_raw(self, prompt: str, max_tokens: int = 512, temperature: float = 0.2) -> Optional[str]:
        try:
            req_data = json.dumps({"model": self.model, "prompt": prompt, "stream": False, "format": "json"}).encode("utf-8")
            req = urllib.request.Request(self.endpoint, data=req_data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "")
        except Exception:
            return None

    def plan_observations(self, query: str, context: Dict[str, Any], tools_schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tool_names = [t["name"] for t in tools_schema]
        prompt = (
            f"You are a Linux troubleshooting assistant. Given query: '{query}', choose 1-3 tool names from: {tool_names}.\n"
            'Respond in JSON: [{"tool": "<name>", "arguments": {}}]'
        )
        raw = self.generate_raw(prompt)
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else [data]
        except Exception:
            return []

    def synthesize_diagnosis(self, query: str, context: Dict[str, Any], observations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        distro_guide = (context.get("distro_prompt_context") or "").strip()
        distro_sec = f"\n=== Active Distribution Rules ===\n{distro_guide}\n" if distro_guide else f"Distro: {context.get('distro_name', 'Linux')}\n"
        prompt = (
            "You are an expert Linux System Administrator AI. Diagnose the sysadmin query given system telemetry and tool evidence.\n"
            f"{distro_sec}"
            f"Query: {query}\n"
            f"Evidence: {json.dumps(observations, default=str)}\n"
            "Respond strictly in JSON format with keys: symptom, root_cause, rationale, proposed_commands (list of [cmd, safety, risk, rationale]), confidence."
        )
        raw = self.generate_raw(prompt)
        return _parse_llm_json(raw, query=query)

    def generate_command(self, query: str, cwd: Optional[str] = None) -> Optional[Dict[str, Any]]:
        wd = cwd or os.getcwd()
        user_home = os.path.expanduser("~")
        prompt = (
            "You are an expert Linux System Administrator AI. Translate the user natural language request into a single Linux shell command.\n"
            f"User Request: {query}\n"
            f"Current Directory: {wd}\n"
            f"User Home: {user_home}\n\n"
            "Respond with a JSON object containing 'command' and 'summary', or output the command in a ```bash code block."
        )
        raw = self.generate_raw(prompt)
        return _parse_llm_json(raw, query=query)


class LlamaCppProvider(LLMProvider):
    """In-process GGUF inference provider using llama-cpp-python."""

    def __init__(self, model_path: Optional[str] = None, n_ctx: int = 2048, n_threads: Optional[int] = None):
        self.model_path = model_path
        if self.model_path is None:
            try:
                from ops_assistant.config import get_config
                cfg = get_config()
                if cfg.get("active_model_path") and os.path.exists(cfg["active_model_path"]):
                    self.model_path = cfg["active_model_path"]
            except Exception:
                pass
            if self.model_path is None:
                try:
                    from ops_assistant.model_manager.downloader import ModelDownloader
                    downloader = ModelDownloader()
                    active = downloader.get_active_model_path()
                    if active:
                        self.model_path = str(active)
                except Exception:
                    pass

        self.n_ctx = n_ctx
        self.n_threads = n_threads or max(1, (os.cpu_count() or 4) // 2)
        self._llm = None
        self._load_error = None

    def is_available(self) -> Tuple[bool, str]:
        if self._llm is not None:
            return True, "Ready (In-memory Llama context)"
        if not self.model_path or not os.path.exists(self.model_path):
            return False, f"Model weights not found at '{self.model_path}'"
        try:
            import llama_cpp
            return True, f"Ready ({os.path.basename(self.model_path)})"
        except ImportError:
            return False, "llama-cpp-python is not installed"

    def _ensure_loaded(self):
        if self._llm is not None:
            return
        if self._load_error:
            raise RuntimeError(self._load_error)
        if not self.model_path or not os.path.exists(self.model_path):
            self._load_error = f"Model file not found: {self.model_path}"
            raise FileNotFoundError(self._load_error)
        try:
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                verbose=False
            )
        except Exception as e:
            self._load_error = str(e)
            raise RuntimeError(self._load_error)

    def generate_raw(self, prompt: str, max_tokens: int = 512, temperature: float = 0.2) -> Optional[str]:
        try:
            self._ensure_loaded()
            res = self._llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["<|im_end|>", "```", "<|endoftext|>"]
            )
            return res["choices"][0]["text"].strip()
        except Exception:
            return None

    def generate_command(self, query: str, cwd: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Synthesize exact shell command from natural language using the local GGUF model."""
        wd = cwd or os.getcwd()
        user_home = os.path.expanduser("~")
        prompt = (
            "<|im_start|>system\n"
            "You are an expert Linux System Administrator AI & Command Copilot. Translate the user request into a single exact Linux shell command.\n"
            f"Current Directory: {wd}\n"
            f"User Home: {user_home}\n"
            "<|im_end|>\n"
            "<|im_start|>user\n"
            f"{query}\n"
            "<|im_end|>\n"
            "<|im_start|>assistant\n"
            "```bash\n"
        )
        raw = self.generate_raw(prompt, max_tokens=256)
        if raw and not raw.startswith("```"):
            raw = f"```bash\n{raw}\n```"
        return _parse_llm_json(raw, query=query)

    def synthesize_diagnosis(self, query: str, context: Dict[str, Any], observations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        distro_guide = (context.get("distro_prompt_context") or "").strip()
        distro_sec = f"\nDistribution Rules:\n{distro_guide}\n" if distro_guide else f"Distro: {context.get('distro_name', 'Linux')}\n"
        prompt = (
            "<|im_start|>system\n"
            "You are an expert Linux System Administrator AI. Diagnose the sysadmin query given system observations.\n"
            f"{distro_sec}"
            "Respond ONLY in valid JSON format with keys:\n"
            "- 'symptom': string\n"
            "- 'root_cause': string\n"
            "- 'rationale': string\n"
            "- 'proposed_commands': list of [command, safety_level, risk_score, rationale]\n"
            "- 'confidence': float between 0.0 and 1.0\n"
            "<|im_end|>\n"
            "<|im_start|>user\n"
            f"Query: {query}\n"
            f"Observations: {json.dumps(observations, default=str)}\n"
            "<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        raw = self.generate_raw(prompt)
        return _parse_llm_json(raw)

    def generate_diagnosis(self, query: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.synthesize_diagnosis(query, context, observations=[])

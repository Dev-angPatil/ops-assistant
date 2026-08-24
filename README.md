# AI-Powered Linux Operations Assistant

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-346%20passed-brightgreen.svg)]()
[![Latency](https://img.shields.io/badge/avg_latency-45.2ms-success.svg)]()
[![Accuracy](https://img.shields.io/badge/accuracy-100%25-brightgreen.svg)]()
[![Distro Support](https://img.shields.io/badge/distros-Debian%20%7C%20RHEL%20%7C%20Arch%20%7C%20Alpine%20%7C%20SUSE%20%7C%20BOSS-purple.svg)]()

> **C-DAC AI Enabled Operating System Hackathon 2026**  
> Track 1 — AI at Application Level · Problem Statement 2

---

## The Problem

When a production Linux server crashes at 3 AM, the operator stares at thousands of lines of `journalctl`, `dmesg`, and `/var/log/*` under extreme pressure. A single root cause — say, Kernel OOM — cascades into dozens of symptoms: worker process killed → socket hangup → reverse proxy 502. **Generic LLM chatbots try to fix the 502. We isolate the OOM.**

Most AI assistants are cloud-dependent wrappers that hallucinate shell commands, ignore distro differences, and offer zero safety guarantees. They cannot run on the very server that is dying — because the server is already resource-starved.

## The Solution

**`ops-assistant`** is an air-gapped, explainable Linux operations copilot that diagnoses system failures in **<50 ms** with **zero cloud dependencies**. It reads directly from the kernel (`/proc`, `/sys`, PSI pressure metrics), builds causal graphs to isolate the *true* root cause, validates fixes in ephemeral sandboxes before you ever run them, and generates one-click rollbacks for every action.

```
 "Why is NGINX failing to bind to port 80?"

 ┌─ Root Cause Isolated ─────────────────────────────────────────┐
 │  PORT_CONFLICT: PID 1842 (apache2) already bound on :80       │
 │  Latency: 44.17ms · Confidence: HIGH · Risk: MODIFYING (0.35) │
 ├─ Causality DAG ───────────────────────────────────────────────┤
 │  apache2:80 ─→ NGINX bind() EADDRINUSE ─→ Service Crash      │
 ├─ Remediation ─────────────────────────────────────────────────┤
 │  $ sudo fuser -k 80/tcp                                       │
 │    └─ -k  : send SIGKILL to processes using the port          │
 │    └─ 80/tcp : target TCP port 80                             │
 ├─ Rollback ────────────────────────────────────────────────────┤
 │  $ sudo systemctl start apache2                               │
 ├─ Sandbox Verified ────────────────────────────────────────────┤
 │  ✓ Syntax valid · ✓ Dry-run passed in rootless namespace      │
 └───────────────────────────────────────────────────────────────┘
```

---

## Why This Is Different

| | Generic LLM Chatbots | `ops-assistant` |
|---|---|---|
| **Latency** | 1–5 seconds (API round-trip) | **45.2 ms average** (deterministic fast-path) |
| **Offline / Air-Gapped** | ❌ Requires internet | ✅ **100% offline capable** — zero API keys needed |
| **Root Cause Analysis** | Treats symptoms as causes | **Causal DAG** isolates true root ($\text{InDegree}=0$) |
| **Safety** | Suggests `rm -rf /` if you ask nicely | **AST safety gate** hard-blocks destructive patterns |
| **Distro Awareness** | Assumes Ubuntu | **6 distro families**: Debian, RHEL, Arch, Alpine, SUSE, BOSS |
| **Explainability** | "Run this command" | **Flag-by-flag XAI** + automatic rollback synthesis |
| **Command Validation** | None | **Ephemeral rootless namespace** sandbox dry-run |
| **Memory** | Multi-GB model required | **<16 MB RAM** in deterministic mode |
| **Hallucination Rate** | Unknown | **0.0%** — AST-verified deterministic pipeline |

---

## Core Architecture

```
 ┌────────────────────────────────────────────────────────────────┐
 │  Natural Language Query (CLI / Web GUI / Voice / REPL)         │
 └──────────────────────────┬─────────────────────────────────────┘
                            ▼
 ┌──────────────────────────────────────────────────────────────┐
 │               OpsAssistantAgent (ReAct Loop)                 │
 │  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
 │  │  Deterministic│  │  Local GGUF  │  │  Gemini API       │  │
 │  │  Fast-Path    │  │  Ollama Edge │  │  (Optional Cloud) │  │
 │  │  <50ms, 0 MB  │  │  1-6 GB      │  │  Full reasoning   │  │
 │  └──────┬───────┘  └──────┬───────┘  └────────┬──────────┘  │
 │         └─────────────────┴───────────────────┘              │
 └──────────────────────────┬───────────────────────────────────┘
                            ▼
 ┌──────────────────────────────────────────────────────────────┐
 │                    Telemetry Hub                              │
 │  /proc/stat  /proc/meminfo  /proc/pressure/*  journald       │
 │  dmesg  /var/log/*  systemd DBus  DistroDetector             │
 └──────────────────────────┬───────────────────────────────────┘
                            ▼
 ┌──────────────────────────────────────────────────────────────┐
 │        Causality DAG → XAI Explainer → Rollback Gen          │
 └──────────────────────────┬───────────────────────────────────┘
                            ▼
 ┌──────────────────────────────────────────────────────────────┐
 │  Ephemeral Sandbox Probe (unshare -r -m -p -f --mount-proc)  │
 │  AST Safety Validator → 4-Tier Risk Gate → User Approval     │
 └──────────────────────────┬───────────────────────────────────┘
                            ▼
                   [ Linux Kernel & Daemons ]
```

### Key Subsystems

| Subsystem | What It Does | Key Metric |
|---|---|---|
| **Multi-Tier AI Copilot** | Deterministic regex AST → Local GGUF/Ollama → Cloud Gemini fallback chain | <50ms L1 latency |
| **Causality DAG Engine** | Builds $G=(V,E)$ causal graphs; isolates root cause via $\text{InDegree}=0$ | 100% root cause accuracy |
| **Kernel PSI Ingestion** | Parses `/proc/pressure/{cpu,memory,io}` 10s/60s/300s stall averages | >14,000 ops/s throughput |
| **Sandbox Probe** | Dry-runs commands in rootless `unshare` User+Mount+PID namespaces | 100% syntax validation |
| **AST Safety Gate** | Classifies risk: `READ_ONLY` → `MODIFYING` → `HIGH_RISK` → `DESTRUCTIVE` | 0 destructive leaks |
| **XAI Explainer** | Flag-by-flag breakdowns for 35+ utilities + inverse rollback synthesis | 4.95/5.0 quality score |
| **Multi-Distro KB** | SQLite-backed command translation across 6 distro families + init systems | 100% adaptation accuracy |
| **Intent Chaining & Fuzzy NLP** | Decomposes compound multi-step sysadmin requests into ordered actions | Multi-intent pipeline |
| **Runtime Self-Correction** | Intercepts execution failures, inspects logs, and synthesizes auto-remedies | Dynamic recovery |
| **Desktop Introspector** | Detects Hyprland/KDE/GNOME, PipeWire, wallpaper engines, user configs | Real-time detection |
| **NL Command Compiler** | Natural language → safe Linux commands with approval gate | Multi-ecosystem installs |
| **Web GUI Cockpit** | Glassmorphic layout, Chart.js telemetry, Mission History drawer | Real-time streaming |

> 📖 **See [MODEL_CAPABILITIES.md](MODEL_CAPABILITIES.md) for the full capability matrix across Deterministic, 2.5B Edge, 7B, and Cloud model tiers.**

---

## Installation

### Prerequisites

| Requirement | Details |
|---|---|
| **OS** | Linux — Ubuntu/Debian, Fedora/RHEL/Rocky, Arch, Alpine, openSUSE, BOSS |
| **Python** | 3.9+ (3.10, 3.11, 3.12, 3.14 tested) |
| **Privileges** | Standard user; `sudo` only for restricted logs & service control |
| **RAM (Deterministic)** | <20 MB |
| **RAM (Edge Model)** | 1–2 GB (Qwen2.5-Coder 0.5B) |
| **RAM (Full Local LLM)** | 8–16 GB (Llama 3 8B / Ollama) |

### ⚠️ Private Repository Notice

> [!WARNING]
> During the **C-DAC AI Hackathon 2026** evaluation period, this repository is **private** (collaborator access granted to `ssm-hackathon`).  
> The remote `curl | bash` one-liner below **will not work** for unauthenticated users — GitHub returns 404 for raw files in private repos.  
> **Judges: please use the local installation steps.**

### 📦 Local Installation (Recommended)

```bash
# 1. Clone with your authenticated GitHub credentials
git clone https://github.com/Dev-angPatil/01_LinuxOpsAssistant.git
cd 01_LinuxOpsAssistant

# 2a. Automated installer (detects distro, profiles hardware, configures AI model)
chmod +x install.sh && ./install.sh

# 2b. Or: manual Python venv setup
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt

# 3. Verify installation
python3 -m ops_assistant.cli --inspect-health
```

<details>
<summary><b>Installer flags for advanced / unattended setups</b></summary>

```bash
./install.sh -y                    # Accept all defaults (unattended)
./install.sh --deterministic       # Zero-download deterministic mode
./install.sh --ollama llama3:8b    # Configure local Ollama backend
./install.sh --distro debian       # Override distro profile
./install.sh --no-model            # Skip model download
```

</details>

### ⚡ Remote 1-Line Install (Public Repos / Token Auth)

```bash
curl -fsSL https://raw.githubusercontent.com/Dev-angPatil/01_LinuxOpsAssistant/main/install.sh | bash
```

---

## Usage

Once installed, use `ops-assistant` (or `python3 -m ops_assistant.cli`):

```bash
# System diagnostics
ops-assistant --inspect-health          # CPU, RAM, PSI pressure, zombies, failed units
ops-assistant --distro-info             # Detected distro, init system, package manager
ops-assistant --diagnose-failed         # Scan & diagnose all failed systemd services

# Natural language troubleshooting
ops-assistant "Why is NGINX failing to bind to port 80?"
ops-assistant "Out of memory killed process java"
ops-assistant "Permission denied writing to /var/log/postgres"

# Natural language → Linux commands (with safety gate)
ops-assistant "install nginx" --distro debian
ops-assistant "download zotero"
ops-assistant "find files larger than 500MB"

# Multi-distro cross-targeting
ops-assistant "Why is apache2 failing?" --distro alpine    # → rc-service, logread
ops-assistant "Check firewall rules" --distro rhel         # → firewall-cmd

# Interactive mode & Web GUI
ops-assistant -i                        # Conversational REPL
ops-assistant --gui                     # Launch web dashboard

# Benchmarks & configuration
ops-assistant --benchmark               # 16-scenario empirical benchmark
ops-assistant --setup                   # Hardware profiler & model wizard
```

---

## Empirical Benchmarks

Measured across 16 core Linux failure taxonomy scenarios:

| Metric | Value |
|---|---|
| **Diagnostic Accuracy** | **100%** (16/16 failure vectors) |
| **Average Latency** | **45.2 ms** |
| **Causality DAG Accuracy** | **100%** (topological root cause isolation) |
| **Sandbox Probe Accuracy** | **100%** |
| **Distro Adaptation** | **100%** (6 families) |
| **Destructive Command Leaks** | **0** |
| **Peak Memory (Deterministic)** | **<16 MB** |
| **XAI Explanation Quality** | **4.95 / 5.0** |
| **Procfs Throughput** | **>14,000 ops/s** |

> 📊 **Full benchmark breakdown**: [STATS.md](STATS.md)

---

## Test Suite

**346 tests** across **44 modules** — 100% pass rate:

```bash
pytest tests/ -v
```

```
============================= 346 passed in 44.42s =============================
```

Test coverage spans: agent core, ReAct loop, causality DAGs, safety guardrails, sandbox probe, NL compiler, CLI, GUI server, voice subsystem, desktop ops, Docker ops, installer engine, multi-distro packs, autocomplete, Hinglish synonyms, hardware profiler, and more.

---

## Documentation

| Document | Description |
|---|---|
| **[Architecture Specification](docs/ARCHITECTURE_SPEC.md)** | Subsystem specs, data flows, mathematical formulations |
| **[Failure Taxonomy Playbook](docs/FAILURE_TAXONOMY_PLAYBOOK.md)** | All 16 Linux failure classes with diagnosis workflows |
| **[User & Operator Manual](docs/USER_GUIDE.md)** | CLI commands, REPL, export formats, configuration |
| **[Judges Evaluation Cheat Sheet](docs/JUDGES_CHEAT_SHEET.md)** | 3-minute live demo script for hackathon evaluation |
| **[Empirical Benchmark Report](STATS.md)** | Latency metrics, accuracy tables, test coverage |
| **[Model Capability Matrix](MODEL_CAPABILITIES.md)** | Feature tiers: Deterministic → Edge → Local → Cloud |
| **[Official Submission Dossier](SUBMISSION.md)** | 13-field Annexure III submission document |
| **[System Architecture](ARCHITECTURE.md)** | Full Mermaid diagrams and component deep-dive |

## Contributors

Developed and maintained by the engineering team and open-source contributors.

---

## License

Licensed under the [Apache License, Version 2.0](LICENSE).


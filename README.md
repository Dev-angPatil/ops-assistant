# AI-Powered Linux Operations Assistant (`ops-assistant`)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-200%20passed-brightgreen.svg)]()
[![Latency](https://img.shields.io/badge/latency-%3C50ms-success.svg)]()
[![Accuracy](https://img.shields.io/badge/accuracy-100%25-brightgreen.svg)]()
[![Distro Support](https://img.shields.io/badge/distros-Debian%20%7C%20RHEL%20%7C%20Arch%20%7C%20Alpine%20%7C%20SUSE%20%7C%20BOSS-purple.svg)]()

**C-DAC AI Enabled Operating System Hackathon 2026 — Track 1 (AI at Application Level) — Problem Statement 2**

---

## 📌 Overview

The **AI-Powered Linux Operations Assistant** (`ops-assistant`) is an autonomous, explainable, and air-gapped system administration copilot for Linux servers and edge nodes. It ingests natural language sysadmin queries, correlates multi-vector system telemetry (`procfs`, `sysfs`, `journald`, `dmesg`, `/var/log/*`, `/proc/pressure/*` PSI metrics, `systemd` / `OpenRC`), isolates root causes across 16+ failure taxonomy classes in **<50ms**, and delivers step-by-step Explainable AI (XAI) rationale, flag-by-flag command breakdowns, 4-tier risk scoring, ephemeral namespace sandbox validation, and automatic state-reverting rollback generation.

---

## ✨ Key Architectural Innovations

1. **Multi-Tier Intelligent AI Copilot (`ops_assistant.agent`)**:
   - **Layer 1 (Deterministic Fast-Path)**: Sub-50ms regex AST engine with 0 MB memory footprint.
   - **Layer 2 (Google Gemini API)**: High-speed cloud copilot (`gemini-2.0-flash`, `gemini-1.5-pro`) with structured JSON outputs.
   - **Layer 3 (Local GGUF / Ollama)**: Fully offline edge inference via `llama-cpp-python` with hardware-aware auto-tuning.

2. **Avant-Garde Web GUI Cockpit (`ops_assistant.gui`)**:
   - 2-column cockpit layout with collapsible tactical reasoning stream (`Ctrl+J`) and real-time Chart.js telemetry.
   - Top-right slide-over Mission History Drawer (`Ctrl+H`) backed by persistent SQLite database.
   - On-demand XAI modal deconstructing bash command flags and Linux semantics.

3. **Dynamic Causality DAG Engine (`ops_assistant.explainer.causality_dag`)**:
   - Constructs directed causal graphs $G = (V, E)$ to isolate true root causes with topological in-degree minimization ($\text{InDegree}=0$), suppressing symptom cascade noise (e.g. `KERNEL_OOM` $\rightarrow$ `PROCESS_KILLED` $\rightarrow$ `SOCKET_CLOSED` $\rightarrow$ `UPSTREAM_502`).

4. **Persistent SQLite History & Audit Database (`ops_assistant.db.history_db`)**:
   - Persists all command runs, return codes, execution latencies, stdout/stderr, and rollback commands in `~/.config/ops_assistant/history.db`.

5. **Multi-Ecosystem Project Operations (`ops_assistant.tools.project_ops`)**:
   - Auto-detects Python, Node.js, Rust, Go, Ruby, and PHP project manifests and configures isolated virtual environments automatically.

6. **Ephemeral Rootless Namespace Sandbox Probe (`ops_assistant.tools.sandbox_probe`)**:
   - Empirically dry-runs candidate remediation commands inside isolated User + Mount + PID namespaces (`unshare -r -m -p -f --mount-proc`) with fallback to POSIX syntax validation prior to presenting them to the operator.

7. **AST Safety Guardrails & 4-Tier Risk Matrix (`ops_assistant.tools.safety`)**:
   - Classifies commands into `READ_ONLY` (0.05), `MODIFYING` (0.35), `HIGH_RISK` (0.70), and `DESTRUCTIVE` (1.00).
   - Hard-blocks destructive commands (`rm -rf /`, fork bombs, raw block writes) with zero execution leaks.

8. **Transparent Explainable AI (XAI) & Rollbacks (`ops_assistant.explainer.xai`)**:
   - Provides plain-English flag-by-flag breakdowns across 35+ core Linux utilities and synthesizes inverse rollback commands (`systemctl start <-> stop`, `ufw allow <-> delete allow`).

---

## 🚀 Quickstart

### Prerequisites
- Linux OS (Ubuntu/Debian, Fedora/RHEL/Rocky, Arch Linux, Alpine Linux, openSUSE, BOSS Linux)
- Python 3.9+
- Standard user or `sudo` access for elevated log inspection

### ⚡ Automated 1-Line Installation (Recommended)

Run the autonomous installer directly in your terminal to automatically detect your Linux distribution, profile hardware (CPU, RAM, GPU/VRAM), install dependencies in an isolated virtual environment, choose your open-source AI model, and link the global `ops-assistant` command:

```bash
curl -fsSL https://raw.githubusercontent.com/Dev-angPatil/01_LinuxOpsAssistant/main/install.sh | bash
```

### 🛠️ Manual Installation

```bash
# 1. Clone repository
git clone https://github.com/Dev-angPatil/01_LinuxOpsAssistant.git
cd 01_LinuxOpsAssistant

# 2. Run automated installer locally
chmod +x install.sh && ./install.sh

# Or install manually via pip
pip install -r requirements.txt
```

### CLI Command Reference

Once installed, you can use the global `ops-assistant` command (or `python3 -m ops_assistant.cli`):

```bash
# 1. One-Shot Natural Language Diagnostic Query
ops-assistant "Why is NGINX failing to bind to port 80?"

# 2. Interactive Conversational Sysadmin REPL
ops-assistant -i

# 3. Inspect Real-Time Linux Health, Distro Profile & Kernel PSI Pressure
ops-assistant --inspect-health

# 4. Scan and Diagnose Failed System Services
ops-assistant --diagnose-failed

# 5. Run Hardware Setup & Model Configuration Wizard
ops-assistant --setup

# 6. Launch Interactive Web GUI Dashboard
ops-assistant --gui

# 7. Natural Language → Linux Command Synthesis with Safety Approval Gate
ops-assistant "download zotero"
ops-assistant "install nginx" --distro debian
ops-assistant "create folder /tmp/myproject"

# 8. Run Automated Empirical Benchmark across 16 Failure Scenarios
ops-assistant --benchmark
```

---

## 🧪 Comprehensive Test Suite

Run the full automated test suite containing 200 unit and integration tests across 29 test modules:

```bash
pytest tests/ -v
```

```text
============================= 200 passed in 33.24s =============================
OK (100% Pass Rate)
```

---

## 📁 Repository Structure

```
01_LinuxOpsAssistant/
├── LICENSE                                # Apache 2.0 Open Source License
├── README.md                              # Main project overview, quickstart & architecture summary
├── SUBMISSION.md                          # Official 13-Field Annexure III Submission Document
├── ARCHITECTURE.md                        # High-level architecture specification and Mermaid diagrams
├── STATS.md                               # Empirical benchmark metrics, latency tables & test results
├── PLAN.md                                # Milestone tracking & development roadmap
├── requirements.txt                       # Optional Python dependencies (rich)
│
├── docs/                                  # Complete Technical Documentation Suite
│   ├── ARCHITECTURE_SPEC.md               # In-depth subsystem specification & data flow design
│   ├── FAILURE_TAXONOMY_PLAYBOOK.md       # Detailed 16-class failure taxonomy reference guide
│   ├── USER_GUIDE.md                      # Comprehensive operator manual & CLI flag reference
│   ├── JUDGES_CHEAT_SHEET.md              # Hackathon scorecard alignment & 3-minute demo script
│   └── presentation_deck.md               # Stage 2 presentation slides in GitHub-flavored Markdown
│
├── ops_assistant/                         # Core Python Package Source Code
│   ├── __init__.py
│   ├── agent/                             # Modular Agentic & ReAct Reasoning Subsystem
│   │   ├── __init__.py
│   │   ├── core.py                        # ReAct agent loop, 16 taxonomy classes & action dispatcher
│   │   ├── providers.py                   # Multi-tier LLM providers (Gemini, Ollama, Llama.cpp)
│   │   ├── session.py                     # Multi-turn conversation context & pronoun resolver
│   │   └── tools_registry.py              # Tool execution registry for ReAct reasoning loop
│   ├── cli.py                             # Rich/ANSI CLI, interactive REPL, demo & benchmark runner
│   ├── models.py                          # Strongly-typed Dataclass schemas (Telemetries, Reports, XAI)
│   ├── config.py                          # Local persistent configuration manager
│   │
│   ├── collectors/                        # Multi-Vector Telemetry Ingestion Layer
│   │   ├── hub.py                         # Consolidated Telemetry Hub & health snapshot aggregator
│   │   ├── proc_collector.py              # /proc/stat CPU ticks, /proc/meminfo RAM/Swap, inodes & zombies
│   │   ├── psi_collector.py               # /proc/pressure/{cpu,memory,io} Kernel PSI stall metrics
│   │   ├── journal_collector.py           # journalctl JSON, dmesg -T kernel ring buffer & /var/log/*
│   │   ├── systemd_collector.py           # DBus systemd unit state inspector & failed unit scanner
│   │   └── distro_detector.py             # /etc/os-release parser & distro stack identifier
│   │
│   ├── explainer/                         # Neuro-Symbolic Explainable AI (XAI) Layer
│   │   ├── causality_dag.py               # Directed Acyclic Graph engine with InDegree=0 root isolation
│   │   └── xai.py                         # 35+ Linux utility flag deconstruction & rollback synthesizer
│   │
│   ├── nlp/                               # Natural Language Processing & Intent Routing Layer
│   │   ├── intent_router.py               # 90+ intent classification rules & LLM fallback classifier
│   │   └── nl_compiler.py                 # Natural phrasing shell compiler & explanation builder
│   │
│   ├── gui/                               # Avant-Garde Web GUI Dashboard Cockpit
│   │   ├── server.py                      # Multi-threaded stdlib HTTP server & SSE telemetry stream
│   │   └── static/                        # Frontend dark-mode UI, Chart.js & audio synthesizer
│   │
│   ├── hardware/                          # Hardware Profiling & Local Model Advisor
│   │   ├── profiler.py                    # Micro-architecture inspector (CPU, RAM, GPU, storage)
│   │   └── advisor.py                     # Hardware tier classifier & model catalog recommender
│   │
│   ├── tools/                             # Safety Sandbox & Subprocess Execution Layer
│   │   ├── safety.py                      # 4-tier AST safety validator & destructive pattern blocker
│   │   ├── sandbox_probe.py               # Ephemeral rootless namespace probe & syntax validator
│   │   ├── executor.py                    # Subprocess profiler, dry-run simulator & rollback invoker
│   │   └── project_ops.py                 # Multi-language project dependency & venv manager
│   │
│   ├── db/                                # Knowledge Base & Persistent Audit Layer
│   │   ├── distro_db.py                   # Embedded SQLite relational distro knowledge base
│   │   └── history_db.py                  # Persistent SQLite command history & session database
│   │
│   └── model_manager/                     # Local Offline Model Management
│       └── downloader.py                  # Offline GGUF edge model downloader & verifier
│
└── tests/                                 # 29 Test Modules, 200 Tests (100% Pass Rate)
    ├── __init__.py
    ├── test_agent.py                      # 16 taxonomy scenarios, XAI generation & report serialization
    ├── test_causality_dag.py              # Multi-event causal cascades & InDegree=0 root isolation
    ├── test_cli.py                        # CLI flags, benchmark, demo, exports & health dashboards
    ├── test_collectors.py                 # Procfs CPU ticks, memory, inodes, swap & journald logs
    ├── test_distro_db.py                  # Distro detector, SQLite KB & multi-distro command adaptation
    ├── test_psi_collector.py              # Kernel /proc/pressure parsing & mock stall metrics
    ├── test_safety.py                     # 4-tier risk classification, destructive blockers & rollbacks
    └── test_sandbox_probe.py              # Ephemeral namespace dry-run probe & syntax verification
```

---

## 📜 Documentation Index

- **[System Architecture Specification](docs/ARCHITECTURE_SPEC.md)**: Full component specs, mathematical formulations, and data flows.
- **[Failure Taxonomy Playbook](docs/FAILURE_TAXONOMY_PLAYBOOK.md)**: Exhaustive reference for all 16 Linux failure taxonomy classes.
- **[User & Operator Manual](docs/USER_GUIDE.md)**: Detailed user manual, CLI commands, REPL options, and export formats.
- **[Judges Evaluation Cheat Sheet](docs/JUDGES_CHEAT_SHEET.md)**: 3-minute live demo script and hackathon scorecard alignment.
- **[Stage 2 Presentation Deck](docs/presentation_deck.md)**: Slide deck in clean presentation markdown.
- **[Empirical Benchmark Report](STATS.md)**: Empirical test numbers, latencies, and pass rates.
- **[Official Submission Dossier](SUBMISSION.md)**: 13-field Annexure III submission document.

---

## 📜 License

Licensed under the [Apache License, Version 2.0](LICENSE).

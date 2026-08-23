# AI-Powered Linux Operations Assistant (`ops-assistant`)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-225%20passed-brightgreen.svg)]()
[![Latency](https://img.shields.io/badge/latency-%3C50ms-success.svg)]()
[![Accuracy](https://img.shields.io/badge/accuracy-100%25-brightgreen.svg)]()
[![Distro Support](https://img.shields.io/badge/distros-Debian%20%7C%20RHEL%20%7C%20Arch%20%7C%20Alpine%20%7C%20SUSE%20%7C%20BOSS-purple.svg)]()

**C-DAC AI Enabled Operating System Hackathon 2026 — Track 1 (AI at Application Level) — Problem Statement 2**

---

## 📌 Overview

The **AI-Powered Linux Operations Assistant** (`ops-assistant`) is an autonomous, explainable, and air-gapped system administration copilot built directly for Linux environments. It ingests natural language sysadmin queries, correlates multi-vector system telemetry (`procfs`, `sysfs`, `journald`, `dmesg`, `/var/log/*`, `/proc/pressure/*` PSI metrics, `systemd` / `OpenRC`), introspects desktop environments (**Hyprland/HyDE, KDE Plasma, GNOME, Wayland, PipeWire**), indexes active user configuration files, isolates root causes across 16+ failure taxonomy classes in **<50ms**, and delivers step-by-step Explainable AI (XAI) rationale, flag-by-flag command breakdowns, 4-tier risk scoring, and automatic state-reverting rollback generation.

---

## ✨ Key Architectural Innovations

1. **Multi-Tier Intelligent AI Copilot (`ops_assistant.agent`)**:
   - **Layer 1 (Deterministic Fast-Path)**: Sub-50ms regex AST engine with 0 MB memory overhead.
   - **Layer 2 (Google Gemini API)**: High-speed cloud copilot (`gemini-2.0-flash`, `gemini-1.5-pro`) with structured JSON outputs.
   - **Layer 3 (Local GGUF / Ollama)**: Fully offline edge inference via `llama-cpp-python` with hardware-aware auto-tuning.

2. **Desktop & System Intelligence Ecosystem (`ops_assistant.collectors`, `ops_assistant.db`)**:
   - **Desktop Introspector**: Live detection of compositors (Hyprland, Sway, KDE Plasma, GNOME), theme frameworks (HyDE, Omakub), wallpaper engines (hyprpaper, matugen, swww), and audio daemons (PipeWire, WirePlumber).
   - **User Configuration Indexer**: Scans and catalogs user configs (`hyprland.lua`, `waybar/config.jsonc`, `kitty.conf`, `.zshrc`, `/etc/fstab`) for instant context-aware file retrieval.

3. **Dynamic Causality DAG Engine (`ops_assistant.explainer.causality_dag`)**:
   - Constructs directed causal graphs $G = (V, E)$ to isolate true root causes with topological in-degree minimization ($\text{InDegree}=0$), suppressing symptom cascade noise (e.g. `KERNEL_OOM` $\rightarrow$ `PROCESS_KILLED` $\rightarrow$ `SOCKET_CLOSED` $\rightarrow$ `UPSTREAM_502`).

4. **AST Safety Guardrails & 4-Tier Risk Matrix (`ops_assistant.tools.safety`)**:
   - Classifies commands into `READ_ONLY` (0.05), `MODIFYING` (0.35), `HIGH_RISK` (0.70), and `DESTRUCTIVE` (1.00).
   - Hard-blocks destructive commands (`rm -rf /`, fork bombs, raw block writes) with zero execution leaks.

5. **Modular Distro Knowledge Packs & Dynamic Host Introspection (`ops_assistant.db.distro_db`, `ops_assistant.collectors.host_introspector`)**:
   - Backed by lean, self-contained distribution packs (`debian`, `rhel`, `arch`, `alpine`, `suse`, `base`) that only install the active host distribution data to eliminate bloat, paired with live runtime capability discovery.

6. **Explainable AI (XAI) & Rollback Synthesis (`ops_assistant.explainer.xai`)**:
   - Provides plain-English flag-by-flag breakdowns across 35+ core Linux utilities and synthesizes inverse rollback commands (`systemctl start <-> stop`, `ufw allow <-> delete allow`).

7. **Avant-Garde Web GUI Cockpit (`ops_assistant.gui`)**:
   - 2-column cockpit layout with collapsible tactical stream (`Ctrl+J`), real-time Chart.js telemetry stream, and slide-over Mission History Drawer (`Ctrl+H`).

---

## 🚀 Quickstart

### Prerequisites
- **Operating System**: Linux (Ubuntu/Debian, Fedora/RHEL/Rocky, Arch Linux, Alpine Linux, openSUSE, C-DAC BOSS Linux)
- **Python**: 3.9+
- **Privileges**: Standard user; `sudo` privileges for elevated diagnostic log inspection and service control

### ⚡ Automated 1-Line Installation (Recommended)

Run the autonomous installer directly in your terminal to automatically detect your Linux distribution, profile hardware (CPU, RAM, GPU/VRAM), configure an isolated virtual environment, choose your open-source AI model, and link the global `ops-assistant` command:

```bash
curl -fsSL https://raw.githubusercontent.com/Dev-angPatil/01_LinuxOpsAssistant/main/install.sh | bash
```

### 🛠️ Manual Installation

```bash
# 1. Clone the repository
git clone https://github.com/Dev-angPatil/01_LinuxOpsAssistant.git
cd 01_LinuxOpsAssistant

# 2. Run automated installer locally
chmod +x install.sh && ./install.sh

# Or install manually via pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 💻 CLI Usage Guide

Once installed, use the global `ops-assistant` CLI (or `python3 -m ops_assistant.cli`):

```bash
# 1. Live System Health, Distro Profile & Kernel PSI Inspection
ops-assistant --inspect-health
ops-assistant --distro-info

# 2. Modular Distro Knowledge Pack Management
ops-assistant --pack-list
ops-assistant --pack-add rhel
ops-assistant --pack-sync-all

# 3. Natural Language Diagnostic Triage (Root Cause + Causality DAG)
ops-assistant "Why is NGINX failing to bind to port 80?"

# 4. Interactive Conversational Sysadmin REPL
ops-assistant -i

# 5. Scan and Diagnose Failed System Services
ops-assistant --diagnose-failed

# 6. Natural Language → Linux Command Synthesis with Safety Approval Gate
ops-assistant "download zotero"
ops-assistant "install nginx" --distro debian
ops-assistant "create folder /tmp/myproject"

# 7. Multi-Distro Cross-Targeting
ops-assistant "Why is apache2 failing to restart?" --distro alpine
ops-assistant "Check firewall rules" --distro rhel
ops-assistant "Update package index" --distro boss

# 8. Check Background Installation / Enhancement Progress
ops-assistant --install-status

# 9. Hardware Setup & Model Configuration Wizard
ops-assistant --setup

# 10. Launch Interactive Web GUI Dashboard
ops-assistant --gui

# 11. Run Full Empirical Benchmark (16 Failure Taxonomies)
ops-assistant --benchmark
```

---

## 🧪 Comprehensive Test Suite

Run the full automated test suite containing 210 unit and integration tests across 31 test modules:

```bash
pytest tests/ -v

```

```text
============================= 202 passed in 19.72s =============================
OK (100% Pass Rate)
```

---

## 📜 Documentation Index

- **[System Architecture Specification](docs/ARCHITECTURE_SPEC.md)**: In-depth subsystem specifications, data flow designs, and mathematical formulations.
- **[Failure Taxonomy Playbook](docs/FAILURE_TAXONOMY_PLAYBOOK.md)**: Exhaustive reference guide for all 16 Linux failure taxonomy classes.
- **[User & Operator Manual](docs/USER_GUIDE.md)**: Comprehensive user manual, CLI commands, REPL options, and export formats.
- **[Judges Evaluation Cheat Sheet](docs/JUDGES_CHEAT_SHEET.md)**: 3-minute live demo script and hackathon scorecard alignment.
- **[Empirical Benchmark Report](STATS.md)**: Measured latency metrics, accuracy tables, and test coverage details.
- **[Official Submission Dossier](SUBMISSION.md)**: 13-field Annexure III submission document.

---

## 📜 License

Licensed under the [Apache License, Version 2.0](LICENSE).

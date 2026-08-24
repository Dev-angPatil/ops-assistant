# AI-Powered Linux Operations Assistant (`ops-assistant`)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-346%20passed-brightgreen.svg)]()
[![Latency](https://img.shields.io/badge/avg_latency-45.2ms-success.svg)]()
[![Accuracy](https://img.shields.io/badge/accuracy-100%25-brightgreen.svg)]()
[![Distro Support](https://img.shields.io/badge/distros-Debian%20%7C%20RHEL%20%7C%20Arch%20%7C%20Alpine%20%7C%20SUSE%20%7C%20BOSS-purple.svg)]()

> **C-DAC AI Enabled Operating System Hackathon 2026**  
> Track 1 — AI at Application Level · Problem Statement 2 (PS-2)  
> **Team ID**: SSM-2026-T1-02

---

## The Problem

When a production Linux server crashes, logs explode across `journalctl`, `dmesg`, and `/var/log/*`. A single root cause triggers a cascade of symptoms:

```
Kernel OOM Kill ──► Worker Process Killed ──► Socket Hangup ──► Reverse Proxy 502
                                                                       ▲
                                            Generic AI assistants try to fix THIS
```

Standard LLM chatbots fail sysadmins during critical outages:
- **High Latency & Cloud Lock**: 2–5 second API round-trips; impossible to run on an air-gapped or resource-starved server.
- **Dangerous Hallucinations**: Suggest destructive commands (`rm -rf /`, unsafe `chmod 777`) with zero guardrails.
- **Ubuntu Tunnel Vision**: Ignore real distro differences across RHEL, Arch, Alpine (OpenRC), openSUSE, and BOSS Linux.
- **Zero Host Telemetry**: Cannot read live `/proc`, `/sys`, or Kernel Pressure Stall Information (PSI).
- **Privacy Violations**: Transmit sensitive server logs to third-party clouds, violating data sovereignty and the DPDP Act 2023.

---

## The Solution: `ops-assistant`

**`ops-assistant`** is an air-gapped, explainable Linux operations copilot that diagnoses system failures in **<50 ms** (45.2ms measured average) using **<16 MB RAM** with zero external cloud dependencies.

```
 $ ops-assistant "Why is NGINX failing to bind to port 80?"

 ┌─ Root Cause Isolated ─────────────────────────────────────────┐
 │  PORT_CONFLICT: PID 1842 (apache2) already bound on :80       │
 │  Latency: 44.17ms · Confidence: HIGH · Risk: MODIFYING (0.35) │
 ├─ Causality DAG ───────────────────────────────────────────────┤
 │  apache2:80 ─→ NGINX bind() EADDRINUSE ─→ Service Crash      │
 ├─ Remediation (XAI Grounded) ──────────────────────────────────┤
 │  $ sudo fuser -k 80/tcp                                       │
 │    └─ -k     : send SIGKILL to processes holding the port     │
 │    └─ 80/tcp : target TCP port 80                             │
 ├─ Guaranteed Rollback ─────────────────────────────────────────┤
 │  $ sudo systemctl start apache2                               │
 ├─ Sandbox Verification ────────────────────────────────────────┤
 │  ✓ Syntax validated · ✓ Dry-run passed in rootless namespace  │
 └───────────────────────────────────────────────────────────────┘
```

---

## What Makes This Different

| Metric / Capability | Generic Cloud LLMs | `ops-assistant` |
|---|---|---|
| **Diagnosis Latency** | 2,000–5,000 ms | **45.2 ms** (deterministic fast-path) |
| **Offline / Air-Gapped** | ❌ Cloud-dependent | ✅ **100% Offline** (zero API keys required) |
| **Root Cause Isolation** | Fixes symptoms | **Causality DAG** isolates root cause (InDegree=0) |
| **Safety Gate** | Hallucinates dangerous commands | **AST safety gate** hard-blocks destructive patterns |
| **Distro Support** | Assumes Ubuntu | **6 Distros**: Debian, RHEL, Arch, Alpine, SUSE, BOSS |
| **Command Explainability** | "Run this command" | **Flag-by-flag XAI** + automatic rollback generation |
| **Execution Validation** | None | **Ephemeral rootless namespace** (`unshare`) sandbox |
| **Memory Footprint** | Multi-GB model | **<16 MB RAM** in deterministic mode |
| **Test Suite Pass Rate** | N/A | **346 / 346 tests passed (100%)** |

---

## System Architecture

```
 ┌──────────────────────────────────────────────────────────────┐
 │  Natural Language Query (CLI / Web GUI / Voice / REPL)       │
 └──────────────────────────────┬───────────────────────────────┘
                                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │               OpsAssistantAgent Core Loop                    │
 │  ┌──────────────────┐ ┌───────────────┐ ┌─────────────────┐ │
 │  │ Deterministic    │ │ Local GGUF    │ │ Google Gemini   │ │
 │  │ Fast-Path Engine │ │ Ollama Edge   │ │ (Optional Cloud)│ │
 │  │ <50ms · <16MB RAM│ │ 1–6 GB        │ │ Full Reasoning  │ │
 │  └────────┬─────────┘ └───────┬───────┘ └────────┬────────┘ │
 │           └───────────────────┴──────────────────┘          │
 └──────────────────────────────┬───────────────────────────────┘
                                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │                     Telemetry Hub                            │
 │  • /proc/stat (CPU deltas)    • /proc/meminfo (RAM/Swap)     │
 │  • /proc/pressure/* (PSI)     • journald & dmesg streams     │
 │  • systemd DBus status        • /var/log/* flat logs         │
 └──────────────────────────────┬───────────────────────────────┘
                                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │        Causality DAG ──► XAI Explainer ──► Rollback Gen      │
 │  Isolates InDegree=0 node · Flag breakdowns · Inverses       │
 └──────────────────────────────┬───────────────────────────────┘
                                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │  Ephemeral Rootless Namespace Sandbox (`unshare`)            │
 │  AST Safety Gate ──► 4-Tier Risk Matrix ──► User Approval    │
 └──────────────────────────────┬───────────────────────────────┘
                                ▼
                   [ Linux Kernel & Daemons ]
```

---

## Core Capabilities

1. **Deterministic Root-Cause Analysis (<50ms)**: Fast-path AST regex router covers 16 core Linux failure taxonomy classes with 100% precision with zero cloud tokens.
2. **Dynamic Causality DAGs**: Builds directed acyclic graphs of event sequences to isolate true root causes and discard downstream cascade noise.
3. **Kernel PSI Telemetry Ingestion**: Parses `/proc/pressure/{cpu,memory,io}` 10s/60s/300s stall metrics, catching resource saturation *before* kernel panics occur.
4. **Rootless Namespace Sandbox (`unshare`)**: Dry-runs candidate commands in isolated User+Mount+PID namespaces with scratch filesystems before presenting them to the user.
5. **Multi-Distro Knowledge Base**: Embedded SQLite database dynamically translates commands, package locks, and init systems across Debian, RHEL, Arch, Alpine, openSUSE, and BOSS Linux.
6. **Explainable AI (XAI) & Rollbacks**: Deconstructs command flags into plain English across 35+ utilities and generates guaranteed inverse rollback commands.
7. **4-Tier AST Safety Gate**: Classifies risk (`READ_ONLY`, `MODIFYING`, `HIGH_RISK`, `DESTRUCTIVE`). Unconditionally blocks destructive commands (`rm -rf /`, fork bombs, raw block writes).
8. **Compound Intent Chaining & Self-Correction**: Decomposes multi-step sysadmin requests into sequenced actions, intercepts non-zero exit codes, and synthesizes auto-remedies.

---

## 16-Class Linux Failure Taxonomy

`ops-assistant` natively classifies and remediates:
- `PORT_CONFLICT`: Socket collisions (`EADDRINUSE`)
- `PERMISSION_DENIED`: POSIX file permission or user mismatches (`EACCES`)
- `OOM_KILL`: Kernel Out-of-Memory killer invocations
- `DISK_EXHAUSTION`: Zero remaining physical disk blocks (`ENOSPC`)
- `INODE_EXHAUSTION`: Inode table exhaustion
- `CONFIG_SYNTAX_ERROR`: Configuration file parser errors
- `SSL_CERT_ERROR`: Expired or untrusted TLS certificates
- `DNS_RESOLUTION_FAILURE`: DNS query timeouts or resolver failures
- `DPKG_LOCK_BLOCKED`: Package manager frontend lock held by background processes
- `SYSTEMD_CRASH_LOOP`: Unit restart burst rate limits exceeded
- `DB_CONN_EXHAUSTION`: Database connection pool saturation
- `FIREWALL_PORT_BLOCKED`: Netfilter/UFW packet drops
- `ZOMBIE_PROCESS_ACCUMULATION`: Defunct child process accumulation
- `IOWAIT_BOTTLENECK`: Block layer I/O write starvation
- `SELINUX_APPARMOR_DENIAL`: Mandatory Access Control security profile blocks
- `NTP_CLOCK_DRIFT`: System clock synchronization failures

---

## Quickstart

### Prerequisites
- **OS**: Linux (Ubuntu/Debian, Fedora/RHEL, Arch, Alpine, openSUSE, BOSS Linux)
- **Python**: 3.9+ (3.10, 3.11, 3.12, 3.14 tested)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Dev-angPatil/ops-assistant.git
cd ops-assistant

# 2. Automated installer (detects distro, profiles hardware, sets up venv)
chmod +x install.sh && ./install.sh

# 3. Or standard manual setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

---

## Usage Examples

```bash
# System Health & Telemetry
ops-assistant --inspect-health          # CPU, RAM, PSI pressure, zombies, failed units
ops-assistant --distro-info             # Detected distro, init system, package manager
ops-assistant --diagnose-failed         # Scan & diagnose all failed systemd units

# Natural Language Troubleshooting
ops-assistant "Why is NGINX failing to bind to port 80?"
ops-assistant "Out of memory killed process java"
ops-assistant "Permission denied writing to /var/log/postgres"

# Natural Language → Safe Linux Commands
ops-assistant "install nginx" --distro debian
ops-assistant "download zotero"
ops-assistant "find files larger than 500MB"

# Cross-Distro Targeting
ops-assistant "Why is apache2 failing?" --distro alpine    # → OpenRC & logread
ops-assistant "Check firewall rules" --distro rhel         # → firewall-cmd

# Interactive REPL & Web GUI Cockpit
ops-assistant -i                        # Conversational REPL
ops-assistant --gui                     # Launch web cockpit dashboard

# Benchmarking
ops-assistant --benchmark               # Run full 16-scenario empirical benchmark
```

---

## Empirical Benchmarks

Measured on Linux across all 16 failure taxonomy scenarios:

| Metric | Target | Current Measured Value |
|---|---|---|
| **Diagnostic Accuracy** | >90% | **100.0%** (16/16 vectors passed) |
| **Average Latency** | <150 ms | **45.2 ms** (telemetry + DAG + XAI) |
| **Causality DAG Accuracy** | >95% | **100.0%** (InDegree=0 isolation) |
| **Sandbox Probe Accuracy** | >95% | **100.0%** (rootless namespace dry-run) |
| **Distro Adaptation** | 100% | **100.0%** (6 distro families) |
| **Destructive Command Leaks** | 0 | **0** (AST safety gate verified) |
| **Peak Memory Footprint** | <50 MB | **<16 MB RAM** (deterministic mode) |
| **XAI Explanation Quality** | >4.5 / 5.0 | **4.95 / 5.0** (grounded flag breakdown) |
| **Procfs Throughput** | >5,000 ops/s | **>14,000 ops/s** |

---

## Test Suite

The codebase includes **346 tests across 44 test modules** with a 100% pass rate:

```bash
pytest tests/ -v
```

```
============================= 346 passed in 44.42s =============================
```

---

## Documentation Index

| Document | Description |
|---|---|
| **[Architecture Specification](ARCHITECTURE.md)** | Full subsystem architecture and Mermaid diagrams |
| **[Benchmark Statistics](STATS.md)** | Detailed latency and empirical benchmark breakdown |
| **[Model Capability Matrix](MODEL_CAPABILITIES.md)** | Capability tiers: Deterministic → Edge → Local → Cloud |
| **[Official Submission Dossier](SUBMISSION.md)** | 13-field Annexure III submission document |
| **[User Guide](docs/USER_GUIDE.md)** | Comprehensive operator CLI & REPL manual |
| **[Failure Taxonomy Playbook](docs/FAILURE_TAXONOMY_PLAYBOOK.md)** | Diagnostic workflows for all 16 failure classes |
| **[Judges Cheat Sheet](docs/JUDGES_CHEAT_SHEET.md)** | 3-minute live evaluation demo script |

---

## License

Licensed under the [Apache License, Version 2.0](LICENSE).


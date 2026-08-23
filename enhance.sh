#!/usr/bin/env bash
# ==============================================================================
# LinuxOpsAssistant — Background Heavy Component Enhancer (Phase 2)
#
# Runs detached in the background following the fast core installation.
# Responsibilities:
#   1. Installs optional llama-cpp-python runtime
#   2. Downloads selected AI model weights from Hugging Face with live progress
#   3. Seeds the distribution knowledge base into SQLite
#   4. Finalizes hardware-tuned inference settings in config.json
# ==============================================================================

set -eo pipefail
export LC_ALL=C

VENV_PY="${1:-python3}"
INSTALL_DIR="${2:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
TARGET_DISTRO="${3:-generic}"
CHOSEN_MODEL="${4:-deterministic}"
VENV_PIP="${5:-$(dirname "$VENV_PY")/pip}"

export PYTHONPATH="$INSTALL_DIR:${PYTHONPATH:-}"

CONFIG_DIR="$("$VENV_PY" -c "from ops_assistant.config import get_config_dir; print(get_config_dir())" 2>/dev/null || echo "$HOME/.ops_assistant")"
mkdir -p "$CONFIG_DIR"
LOG_FILE="$CONFIG_DIR/enhance.log"
LOCK_FILE="$CONFIG_DIR/enhance.lock"

# Redirect stdout and stderr to the enhancement log
exec >> "$LOG_FILE" 2>&1

echo "=============================================================================="
echo "Starting Background Enhancement: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Target Distro: $TARGET_DISTRO | Model: $CHOSEN_MODEL | PID: $$"
echo "=============================================================================="

# File-based locking to prevent concurrent enhancement runs
exec 200>"$LOCK_FILE"
if command -v flock >/dev/null 2>&1; then
    if ! flock -n 200; then
        echo "[!] Another enhancement process is already running. Exiting."
        exit 0
    fi
fi

# Trap failures and record error state
trap_failure() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "[✗] Enhancement failed with exit code $exit_code at $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
        "$VENV_PY" -c "
from ops_assistant.install_tracker import get_tracker
get_tracker().mark_failed('Background enhancement encountered an error (exit code $exit_code). Check $LOG_FILE')
" 2>/dev/null || true
    fi
}
trap trap_failure EXIT

# Mark enhancement start in tracker
"$VENV_PY" -c "
from ops_assistant.install_tracker import get_tracker
get_tracker().mark_start(model_key='$CHOSEN_MODEL', pid=$$, total_steps=3)
"

# ------------------------------------------------------------------------------
# Step 1/3: Local Inference Engine (llama-cpp-python)
# ------------------------------------------------------------------------------
echo ""
echo "[Step 1/3] Checking / installing llama-cpp-python runtime..."

"$VENV_PY" -c "
from ops_assistant.install_tracker import get_tracker
get_tracker().mark_step(1, 3, 'Verifying local inference runtime (llama-cpp-python)...', status='installing', progress_pct=10.0)
"

if [ "$CHOSEN_MODEL" != "deterministic" ] && [ "$CHOSEN_MODEL" != "ollama" ]; then
    if ! "$VENV_PY" -c "import llama_cpp" >/dev/null 2>&1; then
        echo "[*] Installing llama-cpp-python binary wheel..."
        if [ -f "$VENV_PIP" ]; then
            "$VENV_PIP" install --quiet llama-cpp-python || echo "[!] llama-cpp-python wheel install non-zero; falling back gracefully."
        fi
    else
        echo "[✓] llama-cpp-python is already available."
    fi
else
    echo "[✓] Deterministic or Ollama provider selected; skipping llama-cpp compilation."
fi

"$VENV_PY" -c "
from ops_assistant.install_tracker import get_tracker
get_tracker().mark_step(1, 3, 'Inference runtime verified.', status='running', progress_pct=30.0)
"

# ------------------------------------------------------------------------------
# Step 2/3: Model Weights Download & Verification
# ------------------------------------------------------------------------------
echo ""
echo "[Step 2/3] Checking / downloading AI model ($CHOSEN_MODEL)..."

if [ "$CHOSEN_MODEL" = "deterministic" ]; then
    echo "[✓] Deterministic engine: 0 MB download required."
    "$VENV_PY" -c "
from ops_assistant.install_tracker import get_tracker
get_tracker().mark_step(2, 3, 'Deterministic engine active (0 MB download)', status='running', progress_pct=70.0)
"
elif [ "$CHOSEN_MODEL" = "ollama" ]; then
    echo "[✓] Ollama provider configured; weights managed by local daemon."
    "$VENV_PY" -c "
from ops_assistant.install_tracker import get_tracker
get_tracker().mark_step(2, 3, 'Ollama backend connected', status='running', progress_pct=70.0)
"
else
    "$VENV_PY" -c "
import sys
import time
from ops_assistant.model_manager.downloader import ModelDownloader
from ops_assistant.install_tracker import get_tracker

tracker = get_tracker()
mkey = '$CHOSEN_MODEL'
dl = ModelDownloader()
avail = dl.list_available_models()

if mkey in avail and avail[mkey]['is_downloaded']:
    print(f'[✓] Model {mkey} is already downloaded.')
    tracker.mark_step(2, 3, f'Model {mkey} ready', status='running', model_key=mkey, progress_pct=70.0)
else:
    print(f'[*] Downloading {mkey} weights...')
    last_update = [0.0]
    
    def on_progress(cur, total, speed):
        pct = (cur / total * 100.0) if total > 0 else 0.0
        # Map 0-100% download into step 30%-70%
        mapped_pct = 30.0 + (pct * 0.40)
        now = time.time()
        if now - last_update[0] >= 1.0 or pct >= 100.0:
            last_update[0] = now
            tracker.mark_step(
                2, 3,
                f'Downloading AI model {mkey} ({pct:.1f}%)',
                status='downloading',
                model_key=mkey,
                progress_pct=mapped_pct,
                extra={'downloaded_bytes': cur, 'total_bytes': total, 'speed_mbps': round(speed, 2)}
            )
            print(f'    Download progress: {pct:.1f}% ({cur // (1024*1024)}MB / {total // (1024*1024)}MB @ {speed:.2f} MB/s)')
            sys.stdout.flush()

    mpath = dl.download_model(mkey, progress_callback=on_progress)
    print(f'[✓] Download completed to {mpath}')
    tracker.mark_step(2, 3, f'Model {mkey} downloaded successfully.', status='running', model_key=mkey, progress_pct=70.0)
"
fi

# ------------------------------------------------------------------------------
# Step 3/3: Seed Distribution Knowledge Base
# ------------------------------------------------------------------------------
echo ""
echo "[Step 3/3] Seeding distribution knowledge database for all supported distributions..."

"$VENV_PY" -c "
import os
from ops_assistant.db.distro_db import DistroKnowledgeBase
from ops_assistant.install_tracker import get_tracker

tracker = get_tracker()
tracker.mark_step(3, 3, 'Seeding distribution knowledge base...', status='seeding', progress_pct=85.0)

db = DistroKnowledgeBase()
db.seed_distro_packs('all')
installed = db.list_installed_packs()
print(f'[✓] Knowledge base seeded for profiles: {installed}')
"

# ------------------------------------------------------------------------------
# Finalize Configuration & Mark Complete
# ------------------------------------------------------------------------------
echo ""
echo "[Finalizing] Updating configuration parameters..."

"$VENV_PY" -c "
import os
from ops_assistant.model_manager.downloader import ModelDownloader
from ops_assistant.hardware.advisor import HardwareAdvisor, MODEL_CATALOG
from ops_assistant.install_tracker import get_tracker
from ops_assistant.config import get_config, set_distro_override

tracker = get_tracker()
mkey = '$CHOSEN_MODEL'

if mkey == 'deterministic':
    tracker.mark_complete(provider='deterministic')
    print('[✓] Finalized deterministic-only setup.')
elif mkey == 'ollama':
    tracker.mark_complete(provider='ollama')
    print('[✓] Finalized Ollama setup.')
else:
    adv = HardwareAdvisor()
    prof = adv.profiler.profile()
    caps = adv.generate_capability_matrix(prof)
    dl = ModelDownloader()
    avail = dl.list_available_models()
    mpath = avail[mkey]['local_path'] if (mkey in avail and avail[mkey]['is_downloaded']) else None

    tracker.mark_complete(
        model_key=mkey,
        model_path=mpath,
        hardware_tier=prof.compute_tier,
        threads=caps.recommended_threads,
        ctx_size=caps.recommended_ctx_size,
        gpu_layers=caps.recommended_gpu_layers,
        provider='gguf'
    )
    print(f'[✓] Finalized GGUF setup for model {mkey} (path={mpath}).')
"

echo "=============================================================================="
echo "Background Enhancement Completed Successfully at $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=============================================================================="

// ==========================================================================
// LinuxOps Assistant — Luxury Avant-Garde Editorial Client Application Logic
// ==========================================================================

// Global state
let cpuChart = null;
let memoryChart = null;
let sseSource = null;
let allServices = [];
let pendingPermissionResolver = null;
let sfxEnabled = true;
let audioCtx = null;

// ==========================================================================
// LUXURY WEB AUDIO SYNTHESIZER
// ==========================================================================
function getAudioContext() {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) audioCtx = new AudioContextClass();
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

function playScifiSound(type) {
  if (!sfxEnabled) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    if (type === 'click' || type === 'tab') {
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, now);
      osc.frequency.exponentialRampToValueAtTime(1320, now + 0.04);
      gain.gain.setValueAtTime(0.04, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
      osc.start(now);
      osc.stop(now + 0.04);
    } else if (type === 'scan' || type === 'execute') {
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.08);
      gain.gain.setValueAtTime(0.05, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.10);
      osc.start(now);
      osc.stop(now + 0.10);
    } else if (type === 'success') {
      osc.type = 'sine';
      osc.frequency.setValueAtTime(523.25, now);
      osc.frequency.setValueAtTime(659.25, now + 0.05);
      osc.frequency.setValueAtTime(783.99, now + 0.10);
      gain.gain.setValueAtTime(0.04, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
      osc.start(now);
      osc.stop(now + 0.18);
    } else if (type === 'alert' || type === 'error') {
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(320, now);
      osc.frequency.exponentialRampToValueAtTime(160, now + 0.12);
      gain.gain.setValueAtTime(0.05, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);
      osc.start(now);
      osc.stop(now + 0.12);
    } else if (type === 'voice_on') {
      osc.type = 'sine';
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.08);
      osc.frequency.exponentialRampToValueAtTime(1320, now + 0.16);
      gain.gain.setValueAtTime(0.04, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.16);
      osc.start(now);
      osc.stop(now + 0.16);
    } else if (type === 'voice_off') {
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, now);
      osc.frequency.exponentialRampToValueAtTime(440, now + 0.12);
      gain.gain.setValueAtTime(0.04, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);
      osc.start(now);
      osc.stop(now + 0.12);
    }
  } catch (e) {
    // Fail silently
  }
}

function toggleSFX() {
  sfxEnabled = !sfxEnabled;
  const btn = document.getElementById('btn-toggle-sfx');
  if (btn) {
    btn.innerHTML = sfxEnabled 
      ? '<i data-lucide="volume-2" class="w-4 h-4 text-white"></i>'
      : '<i data-lucide="volume-x" class="w-4 h-4 text-slate-500"></i>';
    if (window.lucide) lucide.createIcons();
  }
  if (sfxEnabled) playScifiSound('click');
}

function updateTacticalClock() {
  const clockEl = document.getElementById('hud-tactical-clock');
  if (clockEl) {
    const d = new Date();
    const utc = d.toISOString().substring(11, 19) + ' UTC';
    const local = d.toTimeString().substring(0, 8);
    clockEl.textContent = `${local} [${utc}]`;
  }
}

function focusCommandDeck() {
  switchTab('home');
  const input = document.getElementById('agent-prompt-input');
  if (input) {
    input.scrollIntoView({ behavior: 'smooth', block: 'center' });
    input.focus();
  }
  playScifiSound('click');
}

// ==========================================================================
// VOICE ACTIVATION & SPEECH SYNTHESIS ENGINE
// ==========================================================================
let speechRecognition = null;
let isVoiceListening = false;
let ttsVoiceEnabled = false;
let speechFinalTranscript = '';
let mediaStreamAudio = null;

function isSpeechRecognitionSupported() {
  return ('SpeechRecognition' in window) || ('webkitSpeechRecognition' in window);
}

function updateVoiceUIState(listening) {
  const micBtn = document.getElementById('btn-voice-mic');
  const voiceLabel = document.getElementById('btn-voice-label');
  const hudContainer = document.getElementById('voice-hud-container');
  const statusEl = document.getElementById('voice-hud-status');
  const interimEl = document.getElementById('voice-hud-interim');

  if (micBtn) {
    if (listening) {
      micBtn.classList.add('listening');
      micBtn.innerHTML = '<i data-lucide="mic" class="w-4.5 h-4.5 text-cyan-300 animate-pulse"></i><span id="btn-voice-label" class="text-cyan-300 font-bold">Listening... 🔴</span>';
    } else {
      micBtn.classList.remove('listening');
      micBtn.innerHTML = '<i data-lucide="mic" class="w-4.5 h-4.5 text-cyan-300"></i><span id="btn-voice-label">Voice Command 🎙</span>';
    }
    if (window.lucide) lucide.createIcons();
  }

  if (hudContainer) {
    if (listening) {
      hudContainer.classList.remove('hidden');
      if (statusEl) statusEl.textContent = 'Listening...';
      if (interimEl) interimEl.textContent = 'Speak your sysadmin command...';
    } else {
      hudContainer.classList.add('hidden');
    }
  }
}

async function toggleVoiceActivation() {
  if (isVoiceListening) {
    stopVoiceActivation(true);
    return;
  }
  await startVoiceActivation();
}

async function startVoiceActivation() {
  // Step 1: Explicitly request microphone access
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    try {
      mediaStreamAudio = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      console.warn('Microphone permission error:', err);
      showToast('Microphone access required. Please allow microphone permissions in your browser.', 'error', 4000);
      return;
    }
  }

  // Step 2: Initialize Web Speech Recognition
  if (isSpeechRecognitionSupported()) {
    try {
      const SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
      speechRecognition = new SpeechRecognitionClass();
      speechRecognition.continuous = false;
      speechRecognition.interimResults = true;
      speechRecognition.lang = 'en-US';

      speechRecognition.onstart = () => {
        isVoiceListening = true;
        updateVoiceUIState(true);
        playScifiSound('voice_on');
        showToast('Voice activation active. Speak your command...', 'info', 2500);
      };

      speechRecognition.onresult = (event) => {
        let interim = '';
        let final = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            final += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }

        const interimEl = document.getElementById('voice-hud-interim');
        const inputEl = document.getElementById('agent-prompt-input');

        if (interimEl) {
          interimEl.textContent = interim || final || 'Listening...';
        }

        if (final) {
          speechFinalTranscript = final.trim();
          if (inputEl) {
            inputEl.value = speechFinalTranscript;
            toggleClearPromptBtn(speechFinalTranscript);
          }
        } else if (interim && inputEl) {
          inputEl.value = interim;
          toggleClearPromptBtn(interim);
        }
      };

      speechRecognition.onerror = (event) => {
        console.warn('Speech recognition error:', event.error);
        isVoiceListening = false;
        updateVoiceUIState(false);
        if (event.error === 'not-allowed') {
          showToast('Microphone access was denied. Please allow microphone permissions.', 'error', 4000);
        } else if (event.error !== 'no-speech') {
          showToast(`Voice recognition: ${event.error}`, 'warning', 3000);
        }
      };

      speechRecognition.onend = () => {
        const wasListening = isVoiceListening;
        isVoiceListening = false;
        updateVoiceUIState(false);

        if (mediaStreamAudio) {
          mediaStreamAudio.getTracks().forEach(t => t.stop());
          mediaStreamAudio = null;
        }

        if (wasListening && speechFinalTranscript) {
          playScifiSound('success');
          const inputEl = document.getElementById('agent-prompt-input');
          const promptToRun = speechFinalTranscript;
          speechFinalTranscript = '';
          if (inputEl) {
            inputEl.value = promptToRun;
            toggleClearPromptBtn(promptToRun);
          }
          
          // Auto-submit voice instruction after a short pause
          setTimeout(() => {
            submitAgentPrompt(promptToRun);
          }, 350);
        } else {
          playScifiSound('voice_off');
        }
      };

      speechFinalTranscript = '';
      focusCommandDeck();
      speechRecognition.start();
    } catch (e) {
      console.error('Failed to start speech recognition', e);
      showToast('Could not start voice recognition: ' + e.message, 'error', 4000);
      updateVoiceUIState(false);
    }
  } else {
    showToast('Speech Recognition not supported in this browser. Please use Chrome, Edge, or Chromium.', 'warning', 4500);
  }
}

function stopVoiceActivation(submit = true) {
  if (speechRecognition && isVoiceListening) {
    try {
      if (submit) {
        const inputEl = document.getElementById('agent-prompt-input');
        if (inputEl && inputEl.value.trim()) {
          speechFinalTranscript = inputEl.value.trim();
        }
      } else {
        speechFinalTranscript = '';
      }
      speechRecognition.stop();
    } catch (e) {}
  }
  if (mediaStreamAudio) {
    mediaStreamAudio.getTracks().forEach(t => t.stop());
    mediaStreamAudio = null;
  }
  isVoiceListening = false;
  updateVoiceUIState(false);
}

function toggleVoiceSpeech() {
  ttsVoiceEnabled = !ttsVoiceEnabled;
  const btn = document.getElementById('btn-toggle-tts');
  if (btn) {
    btn.innerHTML = ttsVoiceEnabled 
      ? '<i data-lucide="volume-2" class="w-4 h-4 text-cyan-300"></i>' 
      : '<i data-lucide="volume-x" class="w-4 h-4 text-slate-500"></i>';
    if (window.lucide) lucide.createIcons();
  }
  if (ttsVoiceEnabled) {
    playScifiSound('success');
    showToast('AI Voice Speech synthesis enabled', 'success', 2500);
    speakText('Voice synthesis online. Linux Operations Assistant ready.');
  } else {
    playScifiSound('click');
    showToast('AI Voice Speech synthesis disabled', 'info', 2000);
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  }
}

function speakText(text) {
  if (!ttsVoiceEnabled || !('speechSynthesis' in window)) return;
  try {
    window.speechSynthesis.cancel();
    const cleanText = text
      .replace(/[*_#`~[\]()$]/g, '')
      .replace(/https?:\/\/\S+/g, 'link')
      .replace(/\s+/g, ' ')
      .trim();

    if (!cleanText) return;
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    
    // Pick natural English voice if available
    const voices = window.speechSynthesis.getVoices();
    const englishVoice = voices.find(v => (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Samantha') || v.lang.startsWith('en')));
    if (englishVoice) utterance.voice = englishVoice;

    window.speechSynthesis.speak(utterance);
  } catch (e) {
    console.warn('TTS error:', e);
  }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  initCharts();
  startTelemetrySSE();
  loadInitialData();
  renderQueryHistory();
  loadHistoryFromBackend();
  checkInstallStatus();
  setInterval(checkInstallStatus, 3000);

  updateTacticalClock();
  setInterval(updateTacticalClock, 1000);

  // Restore live output collapsed state
  try {
    if (localStorage.getItem('linuxops_output_collapsed') === 'true') {
      collapseLiveOutput();
    }
  } catch (e) {}

  // Initialize Real-Time Intelligent Autocomplete
  initAutocomplete();

  // Setup prompt form submit
  const form = document.getElementById('agent-prompt-form');
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const input = document.getElementById('agent-prompt-input');
      if (input && input.value.trim()) {
        submitAgentPrompt(input.value.trim());
      }
    });
  }

  // Refresh button
  const btnRefresh = document.getElementById('btn-refresh-health');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      playScifiSound('scan');
      fetchHealthSnapshot();
    });
  }

  // Global Keyboard Shortcuts
  document.addEventListener('keydown', (e) => {
    // Ctrl+H or Alt+H for Mission History Drawer
    if ((e.ctrlKey && e.key.toLowerCase() === 'h') || (e.altKey && e.key.toLowerCase() === 'h')) {
      e.preventDefault();
      toggleHistoryDrawer();
      return;
    }
    // Ctrl+J or Alt+J to Collapse/Expand Live Output
    if ((e.ctrlKey && e.key.toLowerCase() === 'j') || (e.altKey && e.key.toLowerCase() === 'j')) {
      e.preventDefault();
      toggleLiveOutputCollapse();
      return;
    }
    // Alt+V or Ctrl+Space for Voice Activation
    if ((e.altKey && e.key.toLowerCase() === 'v') || (e.ctrlKey && e.code === 'Space')) {
      e.preventDefault();
      toggleVoiceActivation();
      return;
    }
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
      e.preventDefault();
      focusCommandDeck();
    }
    if (e.key === 'Escape') {
      stopVoiceActivation(false);
      closeHistoryDrawer();
      closeModal('modal-permission');
      closeModal('modal-logs');
    }
  });
});

// ==========================================================================
// TOAST NOTIFICATION SYSTEM
// ==========================================================================
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast-item';

  let iconName = 'info';
  let iconColor = 'text-white';
  if (type === 'success') {
    iconName = 'check-circle';
    iconColor = 'text-emerald-400';
    playScifiSound('success');
  } else if (type === 'error') {
    iconName = 'alert-circle';
    iconColor = 'text-rose-400';
    playScifiSound('alert');
  } else if (type === 'warning') {
    iconName = 'alert-triangle';
    iconColor = 'text-amber-400';
    playScifiSound('alert');
  } else {
    playScifiSound('click');
  }

  toast.innerHTML = `
    <div class="mt-0.5 ${iconColor} shrink-0">
      <i data-lucide="${iconName}" class="w-4 h-4"></i>
    </div>
    <div class="flex-1 text-xs text-white leading-relaxed break-words font-sans font-medium">${escapeHtml(message)}</div>
    <button onclick="this.parentElement.remove()" class="text-slate-400 hover:text-white font-mono text-sm leading-none">&times;</button>
  `;

  container.appendChild(toast);
  if (window.lucide) lucide.createIcons();

  setTimeout(() => {
    toast.classList.add('toast-leave');
    setTimeout(() => {
      if (toast.parentElement) toast.remove();
    }, 200);
  }, duration);
}

// ==========================================================================
// GUI-TO-TERMINAL FALLBACK ENGINE (CLIENT)
// ==========================================================================
let currentFallbackData = null;
let currentFallbackRetryCallback = null;

function showTerminalFallbackModal(fallbackData, retryCallback) {
  currentFallbackData = fallbackData;
  currentFallbackRetryCallback = retryCallback;
  playScifiSound('alert');

  const titleEl = document.getElementById('modal-fallback-reason-title');
  const expEl = document.getElementById('modal-fallback-explanation');
  const cmdEl = document.getElementById('modal-fallback-command-text');
  const copySingleBtn = document.getElementById('modal-fallback-copy-btn');
  const copyAllBtn = document.getElementById('modal-fallback-copy-all-btn');
  const runTermBtn = document.getElementById('modal-fallback-run-terminal-btn');
  const runTermLabel = document.getElementById('modal-fallback-run-terminal-label');
  const warningBox = document.getElementById('modal-fallback-warning-box');
  const prereqsList = document.getElementById('modal-fallback-prereqs-list');
  const expectedOutEl = document.getElementById('modal-fallback-expected-output');
  const instrContent = document.getElementById('modal-fallback-instructions-content');
  const badgeEl = document.getElementById('modal-fallback-badge');

  if (titleEl) titleEl.textContent = fallbackData.reason_title || 'Terminal Fallback Mode';
  if (expEl) expEl.textContent = fallbackData.explanation || 'This command requires execution in your Linux terminal.';
  
  const cmdString = fallbackData.multi_command_script || fallbackData.single_command || (fallbackData.commands && fallbackData.commands.join('\n')) || '';
  if (cmdEl) cmdEl.textContent = cmdString;

  if (badgeEl) {
    if (fallbackData.requires_sudo) {
      badgeEl.textContent = 'Sudo Required';
      badgeEl.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase bg-amber-500/20 text-amber-300 border border-amber-500/30';
    } else if (fallbackData.is_destructive) {
      badgeEl.textContent = 'Destructive';
      badgeEl.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase bg-rose-500/20 text-rose-300 border border-rose-500/30';
    } else {
      badgeEl.textContent = fallbackData.reason_code || 'Manual Execution';
      badgeEl.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase bg-cyan-400/20 text-cyan-300 border border-cyan-400/30';
    }
  }

  // Warning Box
  if (warningBox) {
    if (fallbackData.is_destructive || fallbackData.is_high_risk || (fallbackData.risk_score && fallbackData.risk_score >= 0.65)) {
      warningBox.classList.remove('hidden');
    } else {
      warningBox.classList.add('hidden');
    }
  }

  // Copy buttons
  const isMulti = fallbackData.commands && fallbackData.commands.length > 1;
  if (copyAllBtn) {
    if (isMulti) {
      copyAllBtn.classList.remove('hidden');
    } else {
      copyAllBtn.classList.add('hidden');
    }
  }

  // Run in terminal
  if (runTermBtn && runTermLabel) {
    if (fallbackData.available_terminal) {
      runTermBtn.classList.remove('hidden');
      runTermLabel.textContent = `Run in ${fallbackData.available_terminal} ↗`;
    } else {
      runTermLabel.textContent = 'Run in Terminal ↗';
    }
  }

  // Prerequisites
  if (prereqsList) {
    const prereqs = fallbackData.prerequisites || ['Open your standard Linux terminal'];
    prereqsList.innerHTML = prereqs.map(p => `<div>&bull; ${escapeHtml(p)}</div>`).join('');
  }

  // Expected Output
  if (expectedOutEl) {
    expectedOutEl.textContent = fallbackData.expected_output || 'Command output will print in terminal followed by prompt return.';
  }

  // Instructions
  if (instrContent) {
    const instrs = fallbackData.instructions || [];
    instrContent.innerHTML = instrs.map(i => `
      <div class="flex items-start space-x-2.5 py-1">
        <span class="step-indicator-pill">${i.step || '&bull;'}</span>
        <div class="flex-1">
          <div class="font-bold text-white text-xs">${escapeHtml(i.title || '')}</div>
          <div class="text-slate-300 text-xs mt-0.5 leading-relaxed">${escapeHtml(i.detail || '')}</div>
        </div>
      </div>
    `).join('');
  }

  openModal('modal-terminal-fallback');
  if (window.lucide) lucide.createIcons();
}

async function openTerminalFallbackForCommand(cmd, reason = 'Manual Execution Requested', retryCallback = null) {
  try {
    const res = await fetch('/api/terminal/fallback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd, force: true })
    });
    const data = await res.json();
    if (data.fallback) {
      if (reason && (!data.fallback.reason_title || data.fallback.reason_title === 'Terminal Execution Available')) {
        data.fallback.reason_title = reason;
      }
      showTerminalFallbackModal(data.fallback, retryCallback);
    }
  } catch (e) {
    showToast('Failed to load terminal fallback: ' + e.message, 'error');
  }
}

function copyFallbackSingleCommand() {
  if (!currentFallbackData) return;
  const cmd = currentFallbackData.single_command || (currentFallbackData.commands && currentFallbackData.commands[0]) || '';
  if (!cmd) return;
  copyTextWithFeedback(cmd, 'modal-fallback-copy-btn', 'modal-fallback-copy-btn-text', 'Copied Command! ✓');
}

function copyFallbackAllCommands() {
  if (!currentFallbackData) return;
  const script = currentFallbackData.multi_command_script || (currentFallbackData.commands && currentFallbackData.commands.join('\n')) || '';
  if (!script) return;
  copyTextWithFeedback(script, 'modal-fallback-copy-all-btn', 'modal-fallback-copy-all-text', 'Copied All Commands! ✓');
}

function copyTextWithFeedback(text, btnId, labelId, successText = 'Copied! ✓') {
  navigator.clipboard.writeText(text).then(() => {
    playScifiSound('success');
    showToast('Command copied to clipboard — ready to paste in terminal', 'success', 2500);
    const btn = document.getElementById(btnId);
    const label = document.getElementById(labelId);
    if (btn) {
      btn.classList.add('btn-copied');
      if (label) {
        const origText = label.textContent;
        label.textContent = successText;
        setTimeout(() => {
          btn.classList.remove('btn-copied');
          label.textContent = origText;
        }, 2200);
      }
    }
  }).catch(() => {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    showToast('Command copied to clipboard', 'success', 2000);
  });
}

function toggleFallbackInstructions() {
  const content = document.getElementById('modal-fallback-instructions-content');
  const arrow = document.getElementById('modal-fallback-instructions-arrow');
  if (content) {
    const isHidden = content.classList.contains('hidden');
    if (isHidden) {
      content.classList.remove('hidden');
      if (arrow) arrow.style.transform = 'rotate(180deg)';
    } else {
      content.classList.add('hidden');
      if (arrow) arrow.style.transform = 'rotate(0deg)';
    }
  }
}

async function launchFallbackInTerminal(cmdOverride = null) {
  const cmd = cmdOverride || (currentFallbackData ? (currentFallbackData.single_command || currentFallbackData.multi_command_script || (currentFallbackData.commands && currentFallbackData.commands.join(' && '))) : '');
  if (!cmd) return;

  showToast('Spawning command in native Linux desktop terminal...', 'info');
  try {
    const res = await fetch('/api/terminal/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd, hold_open: true })
    });
    const data = await res.json();
    if (data.success) {
      playScifiSound('success');
      showToast(`Launched in ${data.terminal || 'Linux terminal'} (PID ${data.pid || ''})`, 'success', 4000);
    } else {
      showToast(data.error || 'Failed to spawn terminal. Please copy and run manually.', 'warning', 4000);
    }
  } catch (e) {
    showToast('Terminal spawn request failed: ' + e.message, 'error');
  }
}

function retryFallbackExecution() {
  closeModal('modal-terminal-fallback');
  if (typeof currentFallbackRetryCallback === 'function') {
    playScifiSound('execute');
    currentFallbackRetryCallback();
  }
}

function renderTerminalFallbackCardHTML(fb, uid, retryFnCallStr = '') {
  if (!fb) return '';
  const singleCmd = fb.single_command || (fb.commands && fb.commands[0]) || '';
  const multiScript = fb.multi_command_script || (fb.commands && fb.commands.join('\n')) || singleCmd;
  const isMulti = fb.commands && fb.commands.length > 1;
  const prereqs = fb.prerequisites || ['Open your Linux terminal'];
  const instrs = fb.instructions || [];

  return `
    <div class="terminal-fallback-card p-5 sm:p-6 space-y-4 my-2 text-white">
      <!-- Fallback Header -->
      <div class="flex items-center justify-between border-b border-cyan-500/20 pb-3">
        <div class="flex items-center space-x-2.5">
          <div class="w-8 h-8 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-400/40 flex items-center justify-center">
            <i data-lucide="terminal" class="w-4.5 h-4.5"></i>
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <span class="font-bold text-white text-xs sm:text-sm">${escapeHtml(fb.reason_title || 'Terminal Fallback Mode')}</span>
              <span class="px-2 py-0.5 rounded-full text-[9px] font-mono font-bold uppercase ${fb.requires_sudo ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/30'}">
                ${fb.requires_sudo ? 'Sudo Required' : (fb.reason_code || 'Manual Execution')}
              </span>
            </div>
          </div>
        </div>
        <span class="text-[10px] font-mono text-cyan-400 font-semibold uppercase tracking-wider">Fallback Activated</span>
      </div>

      <!-- Human Guidance Message (Never generic Execution Failed) -->
      <div class="p-3.5 rounded-xl bg-cyan-950/30 border border-cyan-500/25 text-xs font-sans text-slate-200 leading-relaxed space-y-1">
        <div class="text-[10px] font-bold text-cyan-300 uppercase tracking-wider flex items-center space-x-1">
          <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
          <span>Copilot Guidance:</span>
        </div>
        <div>${escapeHtml(fb.explanation || 'This command requires a real Linux terminal and cannot be executed directly from the Browser GUI. You can copy the command below and run it in your terminal.')}</div>
      </div>

      ${(fb.is_destructive || fb.is_high_risk || (fb.risk_score && fb.risk_score >= 0.65)) ? `
        <div class="p-3 rounded-xl bg-rose-950/40 border border-rose-500/40 text-xs font-sans text-rose-200 flex items-start space-x-2">
          <i data-lucide="alert-triangle" class="w-4 h-4 text-rose-400 shrink-0 mt-0.5"></i>
          <div><span class="font-bold text-rose-300">Safety Notice:</span> Destructive/Privileged command. Review target paths carefully before executing in terminal.</div>
        </div>
      ` : ''}

      <!-- Command Block with Copy Buttons -->
      <div class="space-y-2">
        <div class="flex items-center justify-between text-[11px] text-slate-400 font-sans">
          <span class="uppercase tracking-wider font-semibold">Terminal Command(s):</span>
          <div class="flex items-center space-x-2">
            <button id="inline-fb-copy-btn-${uid}" onclick="copyTextWithFeedback('${escapeHtml(singleCmd)}', 'inline-fb-copy-btn-${uid}', 'inline-fb-copy-label-${uid}', 'Copied! ✓')" class="px-2.5 py-1 rounded-md bg-white/10 hover:bg-white/20 border border-white/20 text-white font-mono text-[11px] transition flex items-center space-x-1">
              <i data-lucide="copy" class="w-3 h-3"></i>
              <span id="inline-fb-copy-label-${uid}">Copy Command</span>
            </button>
            ${isMulti ? `
              <button id="inline-fb-copy-all-btn-${uid}" onclick="copyTextWithFeedback('${escapeHtml(multiScript)}', 'inline-fb-copy-all-btn-${uid}', 'inline-fb-copy-all-label-${uid}', 'Copied All! ✓')" class="px-2.5 py-1 rounded-md bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/40 text-cyan-200 font-mono text-[11px] transition flex items-center space-x-1">
                <i data-lucide="copy-check" class="w-3 h-3"></i>
                <span id="inline-fb-copy-all-label-${uid}">Copy All Commands</span>
              </button>
            ` : ''}
          </div>
        </div>

        <div class="terminal-code-block p-4 font-mono text-xs text-white break-all select-all flex items-start space-x-2.5">
          <span class="text-cyan-400 select-none font-bold">$</span>
          <pre class="flex-1 font-semibold text-white whitespace-pre-wrap leading-relaxed">${escapeHtml(multiScript)}</pre>
        </div>
      </div>

      <!-- Action Toolbar -->
      <div class="flex flex-wrap items-center justify-between gap-2.5 pt-2 border-t border-white/10">
        <div class="flex items-center space-x-2">
          <button onclick="launchFallbackInTerminal('${escapeHtml(singleCmd)}')" class="btn-editorial-secondary !py-1.5 !px-3 text-xs border-cyan-400/40 text-cyan-200 hover:bg-cyan-500/20">
            <i data-lucide="external-link" class="w-3.5 h-3.5 text-cyan-300"></i>
            <span>Run in Terminal ↗</span>
          </button>
          <button onclick="const el = document.getElementById('inline-fb-instr-${uid}'); if(el){ el.classList.toggle('hidden'); }" class="btn-editorial-secondary !py-1.5 !px-3 text-xs">
            <i data-lucide="book-open" class="w-3.5 h-3.5"></i>
            <span>Show Instructions</span>
          </button>
        </div>

        ${retryFnCallStr ? `
          <button onclick="${retryFnCallStr}" class="btn-editorial-primary !py-1.5 !px-3.5 text-xs">
            <i data-lucide="refresh-cw" class="w-3 h-3"></i>
            <span>Retry Execution</span>
          </button>
        ` : ''}
      </div>

      <!-- Context Info: Prerequisites & Expected Output -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-[11px] font-sans pt-1">
        <div class="p-3 rounded-xl bg-black/40 border border-white/10 space-y-1">
          <span class="text-slate-400 font-bold uppercase text-[10px] block">📌 Prerequisites:</span>
          <div class="space-y-0.5 text-slate-300">
            ${prereqs.map(p => `<div>&bull; ${escapeHtml(p)}</div>`).join('')}
          </div>
        </div>
        <div class="p-3 rounded-xl bg-black/40 border border-white/10 space-y-1">
          <span class="text-emerald-400 font-bold uppercase text-[10px] block">🔮 Expected Output:</span>
          <p class="text-slate-300 leading-relaxed">${escapeHtml(fb.expected_output || 'Output prints in terminal followed by exit code 0.')}</p>
        </div>
      </div>

      <!-- Collapsible Instructions -->
      <div id="inline-fb-instr-${uid}" class="hidden p-3.5 rounded-xl bg-black/60 border border-cyan-500/20 space-y-2 text-xs font-sans text-slate-200">
        <div class="font-bold text-cyan-300 text-xs flex items-center space-x-1.5">
          <i data-lucide="list-ordered" class="w-3.5 h-3.5"></i>
          <span>Step-by-Step Manual Execution Instructions:</span>
        </div>
        <div class="space-y-2 pt-1">
          ${instrs.map(i => `
            <div class="flex items-start space-x-2">
              <span class="step-indicator-pill">${i.step || '&bull;'}</span>
              <div class="flex-1">
                <div class="font-bold text-white text-xs">${escapeHtml(i.title || '')}</div>
                <div class="text-slate-300 text-[11px] leading-relaxed">${escapeHtml(i.detail || '')}</div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

// ==========================================================================
// COMMAND EXECUTION PERMISSION MODAL & GATE
// ==========================================================================
function requestCommandPermission(options) {
  const {
    command,
    description = 'Executes specified operation on the Linux host.',
    safetyLevel = 'MODIFYING',
    riskScore = 0.35,
    rollback = null,
    onApprove = null,
    onDryRun = null
  } = options;

  playScifiSound('alert');

  return new Promise((resolve) => {
    const modal = document.getElementById('modal-permission');
    const cmdEl = document.getElementById('modal-perm-command');
    const descEl = document.getElementById('modal-perm-description');
    const safetyEl = document.getElementById('modal-perm-safety');
    const riskEl = document.getElementById('modal-perm-risk');
    const rollbackBox = document.getElementById('modal-perm-rollback-box');
    const rollbackEl = document.getElementById('modal-perm-rollback');
    const approveBtn = document.getElementById('modal-perm-approve-btn');
    const dryRunBtn = document.getElementById('modal-perm-dryrun-btn');
    const fallbackBtn = document.getElementById('modal-perm-fallback-btn');

    if (!modal) return resolve(false);

    cmdEl.textContent = command;
    descEl.textContent = description;
    safetyEl.textContent = safetyLevel;
    safetyEl.className = 'font-bold ' + getSafetyTextColor(safetyLevel);
    riskEl.textContent = (riskScore || 0.05).toFixed(2) + ' / 1.00';

    if (rollback) {
      rollbackBox.classList.remove('hidden');
      rollbackEl.textContent = rollback;
    } else {
      rollbackBox.classList.add('hidden');
    }

    const cleanup = () => {
      approveBtn.onclick = null;
      dryRunBtn.onclick = null;
      if (fallbackBtn) fallbackBtn.onclick = null;
      closeModal('modal-permission');
    };

    approveBtn.onclick = async () => {
      cleanup();
      playScifiSound('execute');
      if (onApprove) await onApprove();
      resolve(true);
    };

    dryRunBtn.onclick = async () => {
      cleanup();
      playScifiSound('scan');
      if (onDryRun) await onDryRun();
      else await executeDryRunSandbox(command);
      resolve(false);
    };

    if (fallbackBtn) {
      fallbackBtn.onclick = () => {
        cleanup();
        openTerminalFallbackForCommand(command, 'Authorized Terminal Execution', onApprove);
        resolve(false);
      };
    }

    openModal('modal-permission');
    if (window.lucide) lucide.createIcons();
  });
}

function copyModalCommand() {
  const cmd = document.getElementById('modal-perm-command')?.textContent;
  if (cmd) {
    navigator.clipboard.writeText(cmd);
    showToast('Command copied to clipboard', 'info', 2000);
  }
}


async function executeDryRunSandbox(cmd) {
  showToast('Testing command in ephemeral CoW sandbox...', 'info');
  try {
    const res = await fetch('/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd, dry_run: true })
    });
    const data = await res.json();
    if (data.blocked) {
      showToast('SANDBOX BLOCKED: ' + data.error, 'error', 5000);
    } else {
      showToast(`Sandbox Verified (Exit Code ${data.returncode}) in ${data.latency_ms || 0}ms`, 'success', 4000);
    }
  } catch (e) {
    showToast('Sandbox error: ' + e.message, 'error');
  }
}

// ==========================================================================
// TAB SWITCHING & INITIALIZATION
// ==========================================================================
const TAB_TITLES = {
  'home': 'Home / AI Ops Deck',
  'health': 'System Health & PSI Telemetry',
  'services': 'Services & Process Management',
  'storage': 'Storage Matrix & Cleanup',
  'network': 'Network & Ports Control',
  'taxonomy': '16-Class Failure Taxonomy',
  'packages': 'Package Nexus',
  'desktop': 'Runner & Portals'
};

function switchTab(tabId) {
  playScifiSound('tab');
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.nav-capsule-tab').forEach(el => el.classList.remove('active'));

  const activeContent = document.getElementById('tab-content-' + tabId);
  const activeBtn = document.getElementById('tab-btn-' + tabId);

  if (activeContent) activeContent.classList.remove('hidden');
  if (activeBtn) activeBtn.classList.add('active');

  if (tabId === 'services') loadServices();
  if (tabId === 'network') loadNetwork();
  if (tabId === 'taxonomy') loadTaxonomyScenarios();
  if (tabId === 'packages') loadInstallerTab();

  if (window.lucide) {
    setTimeout(() => lucide.createIcons(), 50);
  }
}

async function loadInitialData() {
  await fetchHealthSnapshot();
  await loadTaxonomyScenarios();
}

// ==========================================================================
// TELEMETRY & CHARTS
// ==========================================================================
function startTelemetrySSE() {
  if (window.EventSource) {
    try {
      sseSource = new EventSource('/api/stream/telemetry');
      sseSource.onmessage = (event) => {
        try {
          const snap = JSON.parse(event.data);
          updateTelemetryUI(snap);
        } catch (e) {
          console.error('Error parsing SSE telemetry', e);
        }
      };
      sseSource.onerror = () => {
        if (sseSource) sseSource.close();
        setInterval(fetchHealthSnapshot, 3000);
      };
    } catch (e) {
      setInterval(fetchHealthSnapshot, 3000);
    }
  } else {
    setInterval(fetchHealthSnapshot, 3000);
  }
}

async function fetchHealthSnapshot() {
  try {
    const res = await fetch('/api/health');
    if (res.ok) {
      const snap = await res.json();
      updateTelemetryUI(snap);
    }
  } catch (e) {
    console.error('Failed to fetch health snapshot', e);
  }
}

function updateTelemetryUI(snap) {
  if (!snap) return;

  // Header & Hero Stats
  const cpu = snap.cpu || {};
  const mem = snap.memory || {};
  const load = snap.load || {};

  const totalCpuPct = (cpu.user_pct || 0) + (cpu.system_pct || 0);

  // Hero Card Stats
  const heroCpu = document.getElementById('hero-cpu-stat');
  if (heroCpu) heroCpu.textContent = totalCpuPct.toFixed(1) + '%';
  const heroPsi = document.getElementById('hero-psi-stat');
  if (heroPsi) heroPsi.textContent = snap.pressure_status || 'NORMAL';

  // Health Elements
  const cpuPctEl = document.getElementById('health-cpu-pct');
  if (cpuPctEl) cpuPctEl.textContent = totalCpuPct.toFixed(1) + '%';
  const cpuCoresEl = document.getElementById('health-cpu-cores');
  if (cpuCoresEl) cpuCoresEl.textContent = (cpu.core_count || 1) + ' Cores';
  const cpuBreakdownEl = document.getElementById('health-cpu-breakdown');
  if (cpuBreakdownEl) cpuBreakdownEl.textContent = `User: ${(cpu.user_pct||0).toFixed(1)}% | Sys: ${(cpu.system_pct||0).toFixed(1)}% | IO: ${(cpu.iowait_pct||0).toFixed(1)}%`;

  const ramPctEl = document.getElementById('health-ram-pct');
  if (ramPctEl) ramPctEl.textContent = (mem.used_percent || 0).toFixed(1) + '%';
  const swapInfoEl = document.getElementById('health-swap-info');
  if (swapInfoEl) swapInfoEl.textContent = 'Swap: ' + (mem.swap_used_percent||0).toFixed(1) + '% used';

  const load1mEl = document.getElementById('health-load-1m');
  if (load1mEl) load1mEl.textContent = (load.load_1m || 0).toFixed(2);
  const load5mEl = document.getElementById('health-load-5m');
  if (load5mEl) load5mEl.textContent = `5m: ${(load.load_5m||0).toFixed(2)} | 15m: ${(load.load_15m||0).toFixed(2)}`;

  const psiBadge = document.getElementById('health-psi-badge');
  if (psiBadge) psiBadge.textContent = snap.pressure_status || 'NORMAL';
  const uptimeEl = document.getElementById('health-uptime-str');
  if (uptimeEl) uptimeEl.textContent = 'Uptime: ' + ((snap.uptime_seconds||0)/3600).toFixed(1) + ' hrs';

  // Update Charts
  const nowStr = new Date().toLocaleTimeString();
  if (cpuChart) {
    if (cpuChart.data.labels.length > 15) {
      cpuChart.data.labels.shift();
      cpuChart.data.datasets[0].data.shift();
      cpuChart.data.datasets[1].data.shift();
    }
    cpuChart.data.labels.push(nowStr);
    cpuChart.data.datasets[0].data.push(totalCpuPct);
    cpuChart.data.datasets[1].data.push(cpu.iowait_pct || 0);
    cpuChart.update('none');
  }

  if (memoryChart) {
    if (memoryChart.data.labels.length > 15) {
      memoryChart.data.labels.shift();
      memoryChart.data.datasets[0].data.shift();
      memoryChart.data.datasets[1].data.shift();
    }
    memoryChart.data.labels.push(nowStr);
    memoryChart.data.datasets[0].data.push(mem.used_percent || 0);
    memoryChart.data.datasets[1].data.push(mem.swap_used_percent || 0);
    memoryChart.update('none');
  }

  renderPSITable(snap.psi_metrics);
  renderDisksTable(snap.disks);
}

function initCharts() {
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.06)' }, ticks: { color: '#94A3B8', font: { family: 'JetBrains Mono', size: 11 } } },
      x: { grid: { color: 'rgba(255,255,255,0.06)' }, ticks: { color: '#94A3B8', font: { family: 'JetBrains Mono', size: 11 }, maxRotation: 0 } }
    },
    plugins: { legend: { labels: { color: '#F1F5F9', font: { family: 'Space Grotesk', size: 13, weight: 600 }, boxWidth: 14 } } }
  };

  const ctxCpu = document.getElementById('chart-cpu');
  if (ctxCpu) {
    cpuChart = new Chart(ctxCpu, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          { label: 'CPU Total %', data: [], borderColor: '#00D2FF', backgroundColor: 'rgba(0, 210, 255, 0.12)', fill: true, tension: 0.3, borderWidth: 2.5, pointBackgroundColor: '#00D2FF', pointRadius: 2 },
          { label: 'I/O Wait %', data: [], borderColor: '#F59E0B', backgroundColor: 'rgba(245, 158, 11, 0.08)', borderDash: [4, 4], fill: true, tension: 0.3, borderWidth: 2, pointBackgroundColor: '#F59E0B', pointRadius: 2 }
        ]
      },
      options: chartOptions
    });
  }

  const ctxMem = document.getElementById('chart-memory');
  if (ctxMem) {
    memoryChart = new Chart(ctxMem, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          { label: 'RAM Used %', data: [], borderColor: '#A855F7', backgroundColor: 'rgba(168, 85, 247, 0.12)', fill: true, tension: 0.3, borderWidth: 2.5, pointBackgroundColor: '#A855F7', pointRadius: 2 },
          { label: 'Swap Used %', data: [], borderColor: '#FB7185', backgroundColor: 'rgba(251, 113, 133, 0.08)', borderDash: [4, 4], fill: true, tension: 0.3, borderWidth: 2, pointBackgroundColor: '#FB7185', pointRadius: 2 }
        ]
      },
      options: chartOptions
    });
  }
}

function renderPSITable(psi) {
  const container = document.getElementById('psi-table-container');
  if (!container) return;
  if (!psi) {
    container.innerHTML = '<p class="text-slate-500 font-mono">Kernel PSI metrics not available (/proc/pressure unmounted).</p>';
    return;
  }

  let html = '<div class="grid grid-cols-3 gap-3">';
  for (const [subsys, metrics] of Object.entries(psi)) {
    const avg10 = metrics.some_avg10 || 0;
    const colorClass = avg10 > 20 ? 'text-rose-400 border-rose-500/40 bg-rose-500/10' : (avg10 > 5 ? 'text-amber-400 border-amber-500/40 bg-amber-500/10' : 'text-cyan-300 border-cyan-500/30 bg-cyan-500/5');
    const badgeColor = avg10 > 20 ? 'text-rose-400' : (avg10 > 5 ? 'text-amber-400' : 'text-emerald-400');
    html += `<div class="p-4 rounded-2xl border space-y-1.5 ${colorClass}">
      <div class="flex items-center justify-between">
        <span class="font-sans font-bold uppercase text-slate-300 text-xs tracking-wider">${subsys}</span>
        <span class="text-[10px] font-mono font-bold uppercase ${badgeColor}">${avg10 > 20 ? 'HIGH STALL' : (avg10 > 5 ? 'ELEVATED' : 'NORMAL')}</span>
      </div>
      <div class="font-editorial italic text-3xl ${badgeColor}">${avg10.toFixed(2)}%</div>
      <p class="text-xs text-slate-400 font-mono">60s: ${(metrics.some_avg60||0).toFixed(2)}% | 300s: ${(metrics.some_avg300||0).toFixed(2)}%</p>
    </div>`;
  }
  html += '</div>';
  container.innerHTML = html;
}

function renderDisksTable(disks) {
  const container = document.getElementById('disks-table-container');
  if (!container) return;
  if (!disks || disks.length === 0) {
    container.innerHTML = '<p class="text-slate-500 font-mono">No filesystem mounts discovered.</p>';
    return;
  }

  let html = '<div class="space-y-3">';
  disks.slice(0, 4).forEach(d => {
    const barColor = d.used_percent > 85 ? 'bg-rose-500 shadow-[0_0_12px_rgba(244,63,94,0.6)]' : (d.used_percent > 70 ? 'bg-amber-400 shadow-[0_0_12px_rgba(245,158,11,0.6)]' : 'bg-cyan-400 shadow-[0_0_12px_rgba(0,210,255,0.6)]');
    html += `<div class="p-4 rounded-2xl bg-black/40 border border-white/10 space-y-2.5 font-sans text-xs sm:text-sm">
      <div class="flex justify-between items-center">
        <span class="text-white font-semibold font-tech text-sm">${d.mountpoint}</span>
        <span class="text-cyan-300 font-mono font-bold">${d.used_gb.toFixed(1)} / ${d.total_gb.toFixed(1)} GB (${d.used_percent.toFixed(1)}%)</span>
      </div>
      <div class="w-full bg-white/10 h-2 rounded-full overflow-hidden">
        <div class="${barColor} h-full transition-all duration-500" style="width: ${Math.min(100, d.used_percent)}%"></div>
      </div>
    </div>`;
  });
  html += '</div>';
  container.innerHTML = html;
}

// ==========================================================================
// MISSION & INQUIRY HISTORY ENGINE (SLIDE-OVER DRAWER)
// ==========================================================================
const HISTORY_STORAGE_KEY = 'linuxops_mission_history_v1';

const DEFAULT_HISTORY = [
  { prompt: 'Why is port 80 blocked in firewall?', intent: 'DIAGNOSTIC', time: '18:20:10', safety: 'READ_ONLY' },
  { prompt: 'Show system health and pressure', intent: 'TELEMETRY', time: '18:15:42', safety: 'READ_ONLY' },
  { prompt: 'Why is NGINX failing to bind?', intent: 'DIAGNOSTIC', time: '18:10:05', safety: 'READ_ONLY' },
  { prompt: 'Organize my Downloads folder', intent: 'MUTATION', time: '17:55:20', safety: 'MUTATION_SAFE' },
  { prompt: 'Find large files over 100MB', intent: 'AUDIT', time: '17:42:18', safety: 'READ_ONLY' },
  { prompt: 'Audit SSH security configuration', intent: 'SECURITY', time: '17:30:00', safety: 'READ_ONLY' }
];

function toggleHistoryDrawer() {
  const drawer = document.getElementById('history-drawer');
  const overlay = document.getElementById('history-drawer-overlay');
  if (!drawer || !overlay) return;
  const isClosed = drawer.classList.contains('translate-x-full');
  if (isClosed) {
    openHistoryDrawer();
  } else {
    closeHistoryDrawer();
  }
}

function openHistoryDrawer() {
  playScifiSound('click');
  const drawer = document.getElementById('history-drawer');
  const overlay = document.getElementById('history-drawer-overlay');
  if (drawer && overlay) {
    drawer.classList.remove('translate-x-full');
    overlay.classList.remove('opacity-0', 'pointer-events-none');
    overlay.classList.add('opacity-100', 'pointer-events-auto');
    renderQueryHistory();
    // Auto-focus search input inside drawer after slide-in
    setTimeout(() => {
      const filterInput = document.getElementById('history-filter-input');
      if (filterInput) filterInput.focus();
    }, 120);
  }
}

function closeHistoryDrawer() {
  const drawer = document.getElementById('history-drawer');
  const overlay = document.getElementById('history-drawer-overlay');
  if (drawer && overlay) {
    drawer.classList.add('translate-x-full');
    overlay.classList.remove('opacity-100', 'pointer-events-auto');
    overlay.classList.add('opacity-0', 'pointer-events-none');
  }
}

function getStoredHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch (e) {}
  return DEFAULT_HISTORY;
}

async function loadHistoryFromBackend() {
  try {
    const res = await fetch('/api/history/sessions');
    const data = await res.json();
    if (data && Array.isArray(data.sessions) && data.sessions.length > 0) {
      const mapped = data.sessions.map(s => ({
        id: s.id || s.session_id,
        prompt: s.title || s.query || s.first_query || 'Mission Operation',
        intent: s.intent || 'ACTION',
        time: s.created_at ? new Date(s.created_at).toLocaleTimeString() : '',
        safety: s.safety_level || 'MODIFYING',
        command_count: s.command_count || 1
      }));
      localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(mapped));
      renderQueryHistory();
    }
  } catch (e) {}
}

function saveQueryToHistory(promptText, intent = 'QUERY', safety = 'READ_ONLY') {
  if (!promptText || !promptText.trim()) return;
  const history = getStoredHistory().filter(h => h.prompt.toLowerCase() !== promptText.trim().toLowerCase());
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0];
  
  history.unshift({
    prompt: promptText.trim(),
    intent: intent || 'QUERY',
    time: timeStr,
    safety: safety || 'READ_ONLY'
  });

  const trimmed = history.slice(0, 50);
  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(trimmed));
  } catch (e) {}

  renderQueryHistory();
}

function renderQueryHistory(filterText = '') {
  const container = document.getElementById('history-items-container');
  const countBadge = document.getElementById('history-badge-count');

  const history = getStoredHistory();

  // Update top-right navbar count badge
  if (countBadge) {
    if (history.length > 0) {
      countBadge.textContent = history.length;
      countBadge.classList.remove('hidden');
    } else {
      countBadge.classList.add('hidden');
    }
  }

  if (!container) return;

  const filtered = filterText 
    ? history.filter(h => h.prompt.toLowerCase().includes(filterText.toLowerCase()) || (h.intent && h.intent.toLowerCase().includes(filterText.toLowerCase())))
    : history;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="p-6 rounded-2xl bg-white/[0.02] border border-white/10 text-center text-xs text-slate-400 font-mono space-y-2">
        <i data-lucide="inbox" class="w-6 h-6 mx-auto text-slate-500"></i>
        <p>${filterText ? 'No matching past inquiries found' : 'No mission history yet'}</p>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  let html = '';
  filtered.forEach((item) => {
    const escaped = escapeHtml(item.prompt);
    const intentClass = getIntentBadgeClass(item.intent);
    html += `
      <div class="history-item flex items-center justify-between group space-x-3" onclick="loadHistoryPrompt('${escaped.replace(/'/g, "\\'")}')">
        <div class="flex-1 min-w-0 space-y-1.5">
          <div class="flex items-center space-x-2">
            <span class="${intentClass} text-[9px] font-mono px-2 py-0.5 rounded-full uppercase font-bold tracking-wider">${escapeHtml(item.intent || 'QUERY')}</span>
            <span class="text-[10px] text-slate-400 font-mono">${escapeHtml(item.time || '')}</span>
          </div>
          <p class="text-xs sm:text-sm text-slate-200 font-mono truncate group-hover:text-white transition-colors">${escaped}</p>
        </div>
        <div class="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition shrink-0">
          <button 
            type="button" 
            onclick="event.stopPropagation(); quickPrompt('${escaped.replace(/'/g, "\\'")}');" 
            title="Execute Mission Query" 
            class="p-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white transition shadow-[0_2px_10px_rgba(0,0,0,0.5)]">
            <i data-lucide="play" class="w-4 h-4 text-cyan-300"></i>
          </button>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

function filterHistoryList(query) {
  renderQueryHistory(query);
}

async function clearQueryHistory() {
  playScifiSound('click');
  try {
    localStorage.removeItem(HISTORY_STORAGE_KEY);
    await fetch('/api/history/clear', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  } catch (e) {}
  renderQueryHistory();
  showToast('Mission history cleared from database', 'info', 2000);
}

function loadHistoryPrompt(promptText) {
  playScifiSound('click');
  const input = document.getElementById('agent-prompt-input');
  if (input) {
    input.value = promptText;
    toggleClearPromptBtn(promptText);
    input.focus();
  }
  // Automatically close history drawer on smaller screens or when loading into prompt
  if (window.innerWidth < 768) {
    closeHistoryDrawer();
  }
  showToast('Query loaded into command deck', 'info', 1500);
}

function toggleClearPromptBtn(val) {
  const btn = document.getElementById('btn-clear-prompt');
  if (btn) {
    if (val && val.trim().length > 0) {
      btn.classList.remove('hidden');
    } else {
      btn.classList.add('hidden');
    }
  }
}

function clearPromptInput() {
  playScifiSound('click');
  const input = document.getElementById('agent-prompt-input');
  if (input) {
    input.value = '';
    input.focus();
    toggleClearPromptBtn('');
  }
}

function getIntentBadgeClass(intent) {
  const norm = (intent || '').toUpperCase();
  if (norm.includes('DIAGNOSTIC') || norm.includes('DIAGNOSE')) return 'bg-amber-400/20 text-amber-300 border border-amber-400/30';
  if (norm.includes('MUTATION') || norm.includes('ACTION')) return 'bg-cyan-400/20 text-cyan-300 border border-cyan-400/30';
  if (norm.includes('SECURITY') || norm.includes('AUDIT')) return 'bg-rose-400/20 text-rose-300 border border-rose-400/30';
  if (norm.includes('TELEMETRY') || norm.includes('HEALTH')) return 'bg-emerald-400/20 text-emerald-300 border border-emerald-400/30';
  return 'bg-white/10 text-slate-300 border border-white/20';
}

// ==========================================================================
// SHRINKABLE & EXPANDABLE LIVE WORKING OUTPUT CONTROLLER
// ==========================================================================
function toggleLiveOutputCollapse() {
  playScifiSound('click');
  const expandedCard = document.getElementById('output-expanded-card');
  if (!expandedCard) return;

  const isCurrentlyCollapsed = expandedCard.classList.contains('hidden');
  if (isCurrentlyCollapsed) {
    expandLiveOutput(true);
    showToast('Tactical stream expanded', 'info', 1500);
  } else {
    collapseLiveOutput();
    showToast('Tactical stream minimized', 'info', 1500);
  }
}

function collapseLiveOutput() {
  const aside = document.getElementById('home-output-aside');
  const mainArena = document.getElementById('home-main-arena');
  const expandedCard = document.getElementById('output-expanded-card');
  const collapsedCard = document.getElementById('output-collapsed-card');

  if (!aside || !mainArena || !expandedCard || !collapsedCard) return;

  expandedCard.classList.add('hidden');
  collapsedCard.classList.remove('hidden');

  aside.classList.remove('lg:col-span-5', 'xl:col-span-5');
  aside.classList.add('lg:col-span-1', 'xl:col-span-1');

  mainArena.classList.remove('lg:col-span-7', 'xl:col-span-7');
  mainArena.classList.add('lg:col-span-11', 'xl:col-span-11');

  try {
    localStorage.setItem('linuxops_output_collapsed', 'true');
  } catch (e) {}

  if (window.lucide) lucide.createIcons();
}

function expandLiveOutput(playSound = false) {
  if (playSound) playScifiSound('click');
  const aside = document.getElementById('home-output-aside');
  const mainArena = document.getElementById('home-main-arena');
  const expandedCard = document.getElementById('output-expanded-card');
  const collapsedCard = document.getElementById('output-collapsed-card');

  if (!aside || !mainArena || !expandedCard || !collapsedCard) return;

  collapsedCard.classList.add('hidden');
  expandedCard.classList.remove('hidden');

  aside.classList.remove('lg:col-span-1', 'xl:col-span-1');
  aside.classList.add('lg:col-span-5', 'xl:col-span-5');

  mainArena.classList.remove('lg:col-span-11', 'xl:col-span-11');
  mainArena.classList.add('lg:col-span-7', 'xl:col-span-7');

  try {
    localStorage.setItem('linuxops_output_collapsed', 'false');
  } catch (e) {}

  if (window.lucide) lucide.createIcons();
}

// ==========================================================================
// AI OPS AGENT: CHAT & TACTICAL STREAM
// ==========================================================================
function quickPrompt(text) {
  playScifiSound('click');
  closeHistoryDrawer();
  expandLiveOutput(false);
  const input = document.getElementById('agent-prompt-input');
  if (input) {
    input.value = text;
    toggleClearPromptBtn(text);
    submitAgentPrompt(text);
  }
}

async function submitAgentPrompt(promptText) {
  playScifiSound('execute');
  expandLiveOutput(false);
  const feed = document.getElementById('agent-feed-container');
  const input = document.getElementById('agent-prompt-input');
  const btn = document.getElementById('btn-submit-prompt');
  const statusEl = document.getElementById('working-stream-status');

  if (!feed) return;

  // Keep query explicitly visible on the search bar
  if (input) {
    input.value = promptText;
    toggleClearPromptBtn(promptText);
  }

  if (statusEl) {
    statusEl.innerHTML = '<span class="text-cyan-300 animate-pulse">⚡ Reasoning &amp; AST Checking...</span>';
  }

  const userCard = document.createElement('div');
  userCard.className = 'p-4 sm:p-5 rounded-2xl bg-white/[0.03] border border-white/15 font-mono text-xs text-white space-y-2';
  userCard.innerHTML = `
    <div class="flex items-center justify-between text-[10px] text-slate-400 font-sans uppercase tracking-wider">
      <span class="flex items-center space-x-1.5">
        <i data-lucide="user" class="w-3.5 h-3.5 text-slate-300"></i>
        <span>Sysadmin Inquirer</span>
      </span>
      <span>${new Date().toLocaleTimeString()}</span>
    </div>
    <div class="text-xs sm:text-[13px] text-white font-semibold pl-3 border-l-2 border-cyan-400 leading-relaxed">${escapeHtml(promptText)}</div>
  `;
  feed.appendChild(userCard);

  const agentCard = document.createElement('div');
  agentCard.className = 'p-5 rounded-2xl bg-white/[0.04] border border-white/10 space-y-3';
  agentCard.innerHTML = `
    <div class="flex items-center space-x-2.5 text-xs font-sans text-slate-300">
      <span class="inline-block w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
      <span>Reasoning &amp; AST validation in progress...</span>
    </div>
  `;
  feed.appendChild(agentCard);

  feed.scrollTop = feed.scrollHeight;
  if (btn) btn.disabled = true;
  if (window.lucide) lucide.createIcons();

  try {
    const res = await fetch('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: promptText, execute: false })
    });
    const data = await res.json();
    renderAgentResponseCard(agentCard, data);

    // Save to history
    saveQueryToHistory(promptText, data.intent || 'QUERY', data.safety_level || 'READ_ONLY');

    if (statusEl) {
      statusEl.innerHTML = `<span class="text-emerald-400">🟢 Verified (${new Date().toLocaleTimeString()})</span>`;
    }
  } catch (e) {
    agentCard.innerHTML = `
      <div class="text-xs text-rose-400 font-mono font-bold flex items-center space-x-2">
        <i data-lucide="alert-circle" class="w-4 h-4"></i>
        <span>Agent Error: ${escapeHtml(e.message)}</span>
      </div>
    `;
    if (statusEl) {
      statusEl.innerHTML = `<span class="text-rose-400">⚠️ Error</span>`;
    }
  } finally {
    if (btn) btn.disabled = false;
    if (window.lucide) lucide.createIcons();
    feed.scrollTop = feed.scrollHeight;
  }
}

function renderAgentResponseCard(card, data) {
  playScifiSound('success');

  if (data.is_ambiguous) {
    let candidatePills = '';
    if (data.candidates && data.candidates.length > 0) {
      candidatePills = `
        <div class="flex flex-wrap gap-2 pt-2">
          ${data.candidates.map(c => `
            <button type="button" onclick="submitAgentPrompt('${data.action_template ? data.action_template.replace('{choice}', c) : c}')" class="px-3.5 py-1.5 rounded-full bg-cyan-500/20 text-cyan-200 hover:bg-cyan-500/30 border border-cyan-400/40 text-xs font-mono transition flex items-center space-x-1.5">
              <span>👉 ${escapeHtml(c)}</span>
            </button>
          `).join('')}
        </div>
      `;
    }
    card.className = 'avant-card-elevated p-5 sm:p-6 space-y-3 border-amber-500/40 bg-amber-500/5';
    card.innerHTML = `
      <div class="space-y-3">
        <div class="flex items-center space-x-2 text-amber-400 font-bold text-sm">
          <i data-lucide="help-circle" class="w-4.5 h-4.5"></i>
          <span>Ambiguity Clarification Required</span>
        </div>
        <div class="text-slate-100 text-sm font-sans leading-relaxed">${escapeHtml(data.ambiguity_prompt || data.summary)}</div>
        ${candidatePills}
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  const safetyClass = getSafetyBadgeClass(data.safety_level || 'READ_ONLY');

  card.className = 'avant-card-elevated p-5 sm:p-6 space-y-4';

  let stepsHtml = '';
  if (data.steps && data.steps.length > 0) {
    stepsHtml = `
      <div class="space-y-1 text-[11px] text-slate-300 font-mono border-l-2 border-white/30 pl-3 py-0.5 leading-relaxed">
        ${data.steps.map(s => `<div>&bull; ${escapeHtml(s)}</div>`).join('')}
      </div>
    `;
  }

  let commandSectionHtml = '';
  const plannedCmds = data.planned_commands || (data.command ? [{
    command: data.command,
    description: data.command_description || data.summary,
    safety_level: data.safety_level,
    risk_score: data.risk_score,
    rollback_command: data.rollback_command
  }] : []);

  if (plannedCmds.length > 0) {
    commandSectionHtml = `
      <div class="space-y-3 pt-1">
        <div class="text-[10px] font-sans font-semibold uppercase tracking-wider text-slate-400">Planned Command Execution &amp; Guardrails:</div>
        ${plannedCmds.map((c) => `
          <div class="p-4 rounded-2xl bg-black/60 border border-white/10 space-y-2.5">
            <div class="flex items-center justify-between">
              <span class="${getSafetyBadgeClass(c.safety_level)} text-[10px] font-mono px-2.5 py-0.5 rounded-full uppercase font-bold">${c.safety_level || 'READ_ONLY'}</span>
              <span class="text-[10px] font-mono text-slate-400">Risk: ${(c.risk_score || 0.05).toFixed(2)}</span>
            </div>

            <div class="p-3 rounded-xl bg-black/80 border border-white/10 font-mono text-xs text-white flex items-start justify-between space-x-2">
              <div class="break-all select-all flex-1 font-semibold text-white">
                <span class="text-slate-500 select-none">$ </span>
                ${escapeHtml(c.command)}
              </div>
              <button onclick="navigator.clipboard.writeText('${escapeHtml(c.command)}'); showToast('Command copied', 'info', 2000);" class="text-slate-400 hover:text-white px-1" title="Copy Command">
                <i data-lucide="copy" class="w-3.5 h-3.5"></i>
              </button>
            </div>

            <div class="text-xs text-slate-200 font-sans leading-relaxed">
              <span class="text-slate-500 text-[10px] font-semibold uppercase block mb-0.5">Rationale:</span>
              ${escapeHtml(c.description || 'Executes operation on the system.')}
            </div>

            ${c.rollback_command ? `
              <div class="text-[11px] font-mono text-slate-400">
                <span class="text-amber-400 font-bold">Rollback:</span> ${escapeHtml(c.rollback_command)}
              </div>
            ` : ''}

            <div class="flex flex-wrap items-center gap-2 pt-2 border-t border-white/10">
              <button onclick="executeCommandDirect('${escapeHtml(c.command)}', '${escapeHtml(c.rollback_command || '')}', this.closest('.avant-card-elevated'))" class="btn-editorial-primary !py-1.5 !px-3 text-xs">
                <i data-lucide="play" class="w-3 h-3"></i>
                <span>Execute</span>
              </button>
              <button onclick="openTerminalFallbackForCommand('${escapeHtml(c.command)}', 'Manual Terminal Execution', () => executeCommandDirect('${escapeHtml(c.command)}', '${escapeHtml(c.rollback_command || '')}', this.closest('.avant-card-elevated')))" class="btn-editorial-secondary !py-1.5 !px-3 text-xs text-cyan-300 border-cyan-400/30 hover:bg-cyan-500/20" title="Open Terminal Fallback Mode">
                <i data-lucide="terminal" class="w-3 h-3 text-cyan-300"></i>
                <span>Terminal Fallback</span>
              </button>
              <button onclick="executeDryRunSandbox('${escapeHtml(c.command)}')" class="btn-editorial-secondary !py-1.5 !px-3 text-xs">
                <i data-lucide="flask-conical" class="w-3 h-3"></i>
                <span>Dry-Run</span>
              </button>
              <button onclick="explainCommandModal('${escapeHtml(c.command)}')" class="btn-editorial-secondary !py-1.5 !px-3 text-xs" title="Explain Flags and Linux Semantics">
                <i data-lucide="help-circle" class="w-3 h-3 text-cyan-300"></i>
                <span>Explain</span>
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  let outputDetailsHtml = '';
  if (data.output && !plannedCmds.length) {
    outputDetailsHtml = `
      <pre class="p-4 rounded-2xl bg-black/60 border border-white/10 text-[11px] font-mono text-slate-300 overflow-x-auto max-h-48 whitespace-pre-wrap leading-relaxed">${escapeHtml(JSON.stringify(data.output, null, 2))}</pre>
    `;
  }

  let rollbackBtnHtml = '';
  if (data.rollback_command && data.executed) {
    rollbackBtnHtml = `
      <button onclick="executeRollback('${escapeHtml(data.rollback_command)}')" class="btn-editorial-secondary !py-1 !px-2.5 text-xs">
        <i data-lucide="undo-2" class="w-3 h-3"></i>
        <span>Rollback</span>
      </button>
    `;
  }

  let paragraphHtml = '';
  const explanationText = data.ai_explanation || data.natural_explanation || data.explanation_paragraph;
  if (explanationText && explanationText !== data.summary && (!data.terminal_fallback || !data.terminal_fallback.needs_fallback)) {
    paragraphHtml = `
      <div class="p-3.5 rounded-xl bg-cyan-950/20 border border-cyan-500/20 text-xs text-slate-200 leading-relaxed font-sans space-y-1">
        <div class="flex items-center space-x-1.5 font-bold text-cyan-300 text-[10px] uppercase">
          <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
          <span>AI Ops Explanation:</span>
        </div>
        <div>${escapeHtml(explanationText)}</div>
      </div>
    `;
  }

  let fallbackCardHtml = '';
  if (data.terminal_fallback && data.terminal_fallback.needs_fallback) {
    const uid = 'agent-fb-' + Math.random().toString(36).substring(2, 9);
    const firstCmd = plannedCmds.length > 0 ? plannedCmds[0].command : (data.command || '');
    fallbackCardHtml = renderTerminalFallbackCardHTML(data.terminal_fallback, uid, firstCmd ? `executeCommandDirect('${escapeHtml(firstCmd)}', '', this.closest('.avant-card-elevated'))` : '');
  }

  let changesHtml = '';
  if (data.changes_made && data.changes_made.length > 0) {
    changesHtml = `
      <div class="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/30 space-y-1.5 font-sans">
        <div class="text-[10px] font-bold text-emerald-400 uppercase tracking-wider flex items-center space-x-1">
          <i data-lucide="check-check" class="w-3.5 h-3.5"></i>
          <span>System Changes Applied:</span>
        </div>
        <div class="space-y-1 text-xs text-emerald-200">
          ${data.changes_made.map(c => `<div class="flex items-start space-x-1.5"><span class="text-emerald-400 font-bold">&check;</span><span>${escapeHtml(c)}</span></div>`).join('')}
        </div>
      </div>
    `;
  }

  let failureHtml = '';
  if (data.is_success === false && data.failure_analysis && (!data.terminal_fallback || !data.terminal_fallback.needs_fallback)) {
    failureHtml = `
      <div class="p-3.5 rounded-xl bg-rose-950/40 border border-rose-500/40 space-y-2 font-sans text-xs">
        <div class="flex items-center space-x-1.5 text-rose-300 font-bold text-xs">
          <i data-lucide="alert-triangle" class="w-4 h-4 text-rose-400"></i>
          <span>Root Cause Diagnosis: ${escapeHtml(data.failure_analysis.error_class || 'EXECUTION_ERROR')}</span>
        </div>
        <div class="text-slate-200 leading-relaxed">${escapeHtml(data.failure_analysis.diagnosis || '')}</div>
        <div class="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-200 leading-relaxed">
          <span class="font-bold text-emerald-400 block text-[10px] uppercase mb-0.5">💡 AI Recommended Fix:</span>
          ${escapeHtml(data.failure_analysis.recommendation || '')}
        </div>
      </div>
    `;
  }

  card.innerHTML = `
    <div class="flex items-center justify-between text-xs border-b border-white/10 pb-2.5 font-sans">
      <div class="flex items-center space-x-2">
        <span class="font-semibold text-white flex items-center space-x-1.5">
          <i data-lucide="bot" class="w-4 h-4 text-cyan-300"></i>
          <span>${escapeHtml(data.intent || 'ACTION')}</span>
        </span>
        <span class="${safetyClass} text-[9px] font-mono px-2.5 py-0.5 rounded-full uppercase font-bold">${escapeHtml(data.safety_level || 'READ_ONLY')}</span>
      </div>
      <span class="text-slate-500 text-[10px]">${new Date().toLocaleTimeString()}</span>
    </div>

    <div class="text-xs sm:text-sm text-white font-sans font-medium leading-relaxed">${escapeHtml(data.summary || 'Analysis complete.')}</div>
    
    ${fallbackCardHtml}
    ${paragraphHtml}
    ${changesHtml}
    ${failureHtml}
    ${stepsHtml}
    ${commandSectionHtml}
    ${outputDetailsHtml}

    <div class="flex items-center justify-between pt-1 font-mono text-[10px] text-slate-500">
      <span>Risk Score: ${(data.risk_score || 0.05).toFixed(2)}</span>
      ${rollbackBtnHtml}
    </div>
  `;

  if (window.lucide) lucide.createIcons();

  // Optional Voice TTS Output
  if (typeof ttsVoiceEnabled !== 'undefined' && ttsVoiceEnabled && data.summary) {
    speakText(data.summary);
  }
}

function clearAgentFeed() {
  playScifiSound('click');
  const feed = document.getElementById('agent-feed-container');
  if (feed) {
    feed.innerHTML = '<p class="text-xs font-mono text-slate-500 p-2">Tactical reasoning feed purged.</p>';
  }
}

// ==========================================================================
// COMMAND EXECUTION ENGINE & ROLLBACK
// ==========================================================================
async function executeCommandDirect(cmd, rollbackCmd, cardEl) {
  showToast('Executing command: ' + cmd, 'info');

  try {
    const res = await fetch('/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd, dry_run: false })
    });
    const data = await res.json();

    const fallback = data.terminal_fallback;

    if (data.blocked) {
      showToast('Execution protected by Safety Matrix. Switched to Terminal Fallback Mode.', 'warning', 4500);
    } else if (data.success) {
      showToast(`Command executed successfully (Exit Code ${data.returncode}) in ${data.latency_ms || 0}ms`, 'success');
    } else {
      showToast(`Command requires terminal execution (Exit Code ${data.returncode})`, 'warning', 3500);
    }

    if (cardEl) {
      const resultBox = document.createElement('div');
      resultBox.className = 'p-4 sm:p-5 rounded-2xl bg-black/70 border border-white/10 space-y-3 font-mono text-xs leading-relaxed';
      
      const explanationText = data.ai_explanation || data.natural_explanation || data.explanation_paragraph || '';
      const changes = data.changes_made || [];
      const failure = data.failure_analysis;

      let explanationSection = '';
      if (explanationText && (!fallback || !fallback.needs_fallback)) {
        explanationSection = `
          <div class="p-3 rounded-xl bg-cyan-950/30 border border-cyan-500/30 text-xs font-sans text-slate-200 leading-relaxed space-y-1">
            <div class="flex items-center space-x-1.5 font-bold text-cyan-300 text-[11px]">
              <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
              <span>AI Execution Explanation:</span>
            </div>
            <div>${escapeHtml(explanationText)}</div>
          </div>
        `;
      }

      let changesSection = '';
      if (changes.length > 0) {
        changesSection = `
          <div class="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/30 space-y-1.5">
            <div class="text-[10px] font-bold text-emerald-400 uppercase tracking-wider flex items-center space-x-1">
              <i data-lucide="check-check" class="w-3.5 h-3.5"></i>
              <span>System Changes Applied:</span>
            </div>
            <div class="space-y-1 text-xs text-emerald-200 font-sans">
              ${changes.map(c => `<div class="flex items-start space-x-1.5"><span class="text-emerald-400 font-bold">&check;</span><span>${escapeHtml(c)}</span></div>`).join('')}
            </div>
          </div>
        `;
      }

      let failureOrFallbackSection = '';
      if (fallback && (fallback.needs_fallback || data.blocked || !data.success)) {
        const uid = 'exec-fb-' + Math.random().toString(36).substring(2, 9);
        failureOrFallbackSection = renderTerminalFallbackCardHTML(fallback, uid, `executeCommandDirect('${escapeHtml(cmd)}', '${escapeHtml(rollbackCmd || '')}', this.closest('.avant-card-elevated'))`);
      } else if (!data.success && failure) {
        failureOrFallbackSection = `
          <div class="p-3.5 rounded-xl bg-rose-950/40 border border-rose-500/40 space-y-2 font-sans text-xs">
            <div class="flex items-center space-x-1.5 text-rose-300 font-bold text-xs">
              <i data-lucide="alert-triangle" class="w-4 h-4 text-rose-400"></i>
              <span>Root Cause Diagnosis: ${escapeHtml(failure.error_class || 'EXECUTION_ERROR')}</span>
            </div>
            <div class="text-slate-200 leading-relaxed">${escapeHtml(failure.diagnosis || 'Execution failed.')}</div>
            <div class="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-200 leading-relaxed">
              <span class="font-bold text-emerald-400 block text-[10px] uppercase mb-0.5">💡 AI Recommended Fix:</span>
              ${escapeHtml(failure.recommendation || 'Verify command syntax and permissions.')}
            </div>
          </div>
        `;
      }

      resultBox.innerHTML = `
        <div class="flex items-center justify-between text-[10px] text-slate-500">
          <span class="font-bold ${data.success ? 'text-emerald-400' : 'text-amber-400'} flex items-center space-x-1">
            <i data-lucide="${data.success ? 'check-circle' : 'terminal'}" class="w-3.5 h-3.5"></i>
            <span>${data.success ? 'Execution Succeeded' : (data.blocked ? 'Safety Gate Protected' : 'Terminal Fallback Active')} (Exit: ${data.returncode})</span>
          </span>
          <span>Latency: ${data.latency_ms || 0}ms</span>
        </div>
        ${failureOrFallbackSection}
        ${explanationSection}
        ${changesSection}
        ${(!fallback || !fallback.needs_fallback) ? `
          <pre class="text-[11px] ${data.success ? 'text-slate-200' : 'text-rose-200'} overflow-x-auto max-h-36 whitespace-pre-wrap">${escapeHtml(data.stdout || data.stderr || '(No terminal output returned)')}</pre>
        ` : ''}
        ${(rollbackCmd || data.rollback_command) ? `
          <div class="pt-2 flex justify-end">
            <button onclick="executeRollback('${escapeHtml(rollbackCmd || data.rollback_command)}')" class="btn-editorial-secondary !py-1 !px-2.5 text-[10px]">
              <i data-lucide="undo-2" class="w-3 h-3"></i>
              <span>Rollback</span>
            </button>
          </div>
        ` : ''}
      `;
      cardEl.appendChild(resultBox);
      if (window.lucide) lucide.createIcons();
    }
  } catch (e) {
    showToast('Execution failed: ' + e.message, 'error');
  }
}


async function executeRollback(rollbackCmd) {
  if (!rollbackCmd) return;

  requestCommandPermission({
    command: rollbackCmd,
    description: 'Reverts previous operation by executing state rollback command.',
    safetyLevel: 'MODIFYING',
    riskScore: 0.30,
    onApprove: async () => {
      showToast('Executing rollback: ' + rollbackCmd, 'info');
      try {
        const res = await fetch('/api/rollback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rollback_command: rollbackCmd })
        });
        const data = await res.json();
        if (data.success) {
          showToast('Rollback completed successfully', 'success');
        } else {
          showToast('Rollback error: ' + (data.error || 'Failed'), 'error');
        }
      } catch (e) {
        showToast('Rollback error: ' + e.message, 'error');
      }
    }
  });
}

// ==========================================================================
// SERVICES & PROCESSES
// ==========================================================================
async function loadServices() {
  try {
    const res = await fetch('/api/services');
    if (res.ok) {
      allServices = await res.json();
      renderServicesTable(allServices);
    }
  } catch (e) {
    console.error('Failed to load services', e);
  }
}

function filterServices() {
  const query = (document.getElementById('service-search-input')?.value || '').toLowerCase();
  const filtered = allServices.filter(s => (s.unit || '').toLowerCase().includes(query) || (s.description || '').toLowerCase().includes(query));
  renderServicesTable(filtered);
}

function renderServicesTable(services) {
  const tbody = document.getElementById('services-table-body');
  if (!tbody) return;

  if (!services || services.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" class="text-center text-slate-500 py-6 font-mono">No matching services found.</td></tr>';
    return;
  }

  tbody.innerHTML = services.map(s => {
    const isRunning = s.active_state === 'active' || s.sub_state === 'running';
    const isFailed = s.active_state === 'failed';
    const statusColor = isFailed ? 'text-rose-400' : (isRunning ? 'text-emerald-400' : 'text-slate-500');
    const dotColor = isFailed ? 'bg-rose-400' : (isRunning ? 'bg-emerald-400' : 'bg-slate-600');

    return `
      <tr>
        <td class="font-semibold text-white">
          <div class="flex items-center space-x-2">
            <span class="w-1.5 h-1.5 rounded-full ${dotColor}"></span>
            <span>${escapeHtml(s.unit)}</span>
          </div>
        </td>
        <td class="${statusColor} font-bold">${escapeHtml(s.active_state)} (${escapeHtml(s.sub_state)})</td>
        <td class="text-right space-x-1.5">
          <button onclick="promptServiceAction('${escapeHtml(s.unit)}', '${isRunning ? 'restart' : 'start'}')" class="btn-editorial-secondary !py-1 !px-2.5 text-[11px]">
            ${isRunning ? 'Restart' : 'Start'}
          </button>
          ${isRunning ? `
            <button onclick="promptServiceAction('${escapeHtml(s.unit)}', 'stop')" class="btn-editorial-primary !py-1 !px-2.5 text-[11px]">
              Stop
            </button>
          ` : ''}
          <button onclick="viewServiceLogs('${escapeHtml(s.unit)}')" class="btn-editorial-ghost !py-1 !px-2 text-[11px]">
            Logs
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

function promptServiceAction(svc, action) {
  const cmd = `systemctl ${action} ${svc}`;
  const rollbackCmd = action === 'start' ? `systemctl stop ${svc}` : (action === 'stop' ? `systemctl start ${svc}` : null);

  requestCommandPermission({
    command: cmd,
    description: `${action.toUpperCase()} system service unit ${svc}.`,
    safetyLevel: 'MODIFYING',
    riskScore: 0.35,
    rollback: rollbackCmd,
    onApprove: async () => {
      showToast(`Executing: ${cmd}`, 'info');
      try {
        const res = await fetch('/api/services/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ unit: svc, action: action })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Service ${svc} ${action}ed successfully`, 'success');
          loadServices();
        } else {
          showToast(`Failed to ${action} ${svc}: ` + (data.error || 'Error'), 'error');
        }
      } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
      }
    }
  });
}

async function viewServiceLogs(svc) {
  playScifiSound('scan');
  const modal = document.getElementById('modal-logs');
  const title = document.getElementById('modal-logs-title');
  const content = document.getElementById('modal-logs-content');

  if (title) title.textContent = `Journal Logs: ${svc}`;
  if (content) content.textContent = 'Streaming journal logs from journalctl...';
  openModal('modal-logs');

  try {
    const res = await fetch(`/api/services/logs?unit=${encodeURIComponent(svc)}&lines=100`);
    if (res.ok) {
      const logs = await res.json();
      content.textContent = (logs.lines || []).join('\n') || '(No journal logs recorded for unit)';
    } else {
      content.textContent = 'Failed to fetch journal logs.';
    }
  } catch (e) {
    content.textContent = 'Error: ' + e.message;
  }
}

async function loadProcesses() {
  playScifiSound('scan');
  try {
    const res = await fetch('/api/processes');
    if (res.ok) {
      const procs = await res.json();
      const tbody = document.getElementById('processes-table-body');
      if (!tbody) return;

      tbody.innerHTML = (procs || []).slice(0, 30).map(p => `
        <tr>
          <td class="font-mono text-white">${p.pid}</td>
          <td class="text-slate-400">${escapeHtml(p.user || 'root')}</td>
          <td class="font-bold text-white">${(p.cpu_pct||0).toFixed(1)}%</td>
          <td class="text-slate-300 font-bold">${(p.mem_pct||0).toFixed(1)}%</td>
          <td class="truncate max-w-[140px] text-white" title="${escapeHtml(p.command)}">${escapeHtml(p.command)}</td>
          <td class="text-right">
            <button onclick="promptKillProcess(${p.pid}, '${escapeHtml(p.command)}')" class="btn-editorial-primary !py-0.5 !px-2 text-[10px]">
              Kill
            </button>
          </td>
        </tr>
      `).join('');
    }
  } catch (e) {
    console.error('Failed to load processes', e);
  }
}

function promptKillProcess(pid, cmdName) {
  const cmd = `kill -15 ${pid}`;

  requestCommandPermission({
    command: cmd,
    description: `Terminates active process PID ${pid} (${cmdName}).`,
    safetyLevel: 'HIGH_RISK',
    riskScore: 0.65,
    onApprove: async () => {
      showToast(`Killing process ${pid}...`, 'info');
      try {
        const res = await fetch('/api/processes/kill', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pid: pid, signal: 15 })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Process ${pid} terminated`, 'success');
          loadProcesses();
        } else {
          showToast(`Failed to kill process: ` + (data.error || 'Error'), 'error');
        }
      } catch (e) {
        showToast('Error: ' + e.message, 'error');
      }
    }
  });
}

// ==========================================================================
// STORAGE & CLEANUP
// ==========================================================================
async function previewOrganize() {
  playScifiSound('scan');
  const path = document.getElementById('organize-path-input')?.value || '~/Downloads';
  const container = document.getElementById('organize-result-container');
  if (!container) return;

  container.classList.remove('hidden');
  container.innerHTML = '<span class="text-slate-400 font-mono">Analyzing target directory topology...</span>';

  try {
    const res = await fetch('/api/storage/organize/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path })
    });
    const data = await res.json();
    if (data.success) {
      container.innerHTML = `
        <div class="space-y-1.5 text-xs font-sans">
          <div class="text-white font-bold">Preview: Discovered ${data.total_files || 0} candidate files to organize:</div>
          <div class="space-y-1 text-slate-300 font-mono">
            ${(data.moves || []).slice(0, 10).map(m => `<div>&bull; ${escapeHtml(m.source)} &rarr; <span class="text-white">${escapeHtml(m.destination)}</span></div>`).join('')}
            ${(data.moves || []).length > 10 ? `<div class="text-slate-500">...and ${data.moves.length - 10} more items</div>` : ''}
          </div>
        </div>
      `;
    } else {
      container.innerHTML = `<span class="text-rose-400">Error: ${escapeHtml(data.error)}</span>`;
    }
  } catch (e) {
    container.innerHTML = `<span class="text-rose-400">Error: ${escapeHtml(e.message)}</span>`;
  }
}

function promptOrganizeNow() {
  const path = document.getElementById('organize-path-input')?.value || '~/Downloads';

  requestCommandPermission({
    command: `ops-assistant organize --path "${path}"`,
    description: `Categorizes loose files in ${path} into dedicated subdirectories.`,
    safetyLevel: 'MODIFYING',
    riskScore: 0.35,
    onApprove: async () => {
      showToast('Organizing directory...', 'info');
      try {
        const res = await fetch('/api/storage/organize/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: path })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Organized ${data.moved_count || 0} files successfully`, 'success');
          previewOrganize();
        } else {
          showToast('Error: ' + data.error, 'error');
        }
      } catch (e) {
        showToast('Error: ' + e.message, 'error');
      }
    }
  });
}

function promptCleanStorage() {
  requestCommandPermission({
    command: 'journalctl --vacuum-time=7d && rm -rf /tmp/* && sync',
    description: 'Purges old rotated journal logs, temporary scratch files, and frees system disk sectors.',
    safetyLevel: 'MODIFYING',
    riskScore: 0.40,
    onApprove: () => cleanStorage(false)
  });
}

async function cleanStorage(dryRun) {
  playScifiSound('scan');
  const container = document.getElementById('clean-result-container');
  if (container) {
    container.classList.remove('hidden');
    container.innerHTML = '<span class="text-slate-400">Scanning purge candidates...</span>';
  }

  try {
    const res = await fetch('/api/storage/clean', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dry_run: dryRun })
    });
    const data = await res.json();
    if (container) {
      container.innerHTML = `
        <div class="space-y-1.5 text-xs font-sans">
          <div class="text-white font-bold">${dryRun ? 'Purge Preview' : 'Purge Executed'}:</div>
          <div>Reclaimable Space: <span class="text-white font-bold">${data.reclaimable_mb || 0} MB</span></div>
          <div class="text-slate-400">${escapeHtml(data.details || 'Cache analysis complete.')}</div>
        </div>
      `;
    }
  } catch (e) {
    if (container) container.innerHTML = `<span class="text-rose-400">Error: ${escapeHtml(e.message)}</span>`;
  }
}

async function loadLargeFiles() {
  playScifiSound('scan');
  const container = document.getElementById('large-files-container');
  if (!container) return;

  container.innerHTML = '<p class="text-slate-400 font-mono">Scanning filesystem tree for files &gt;100MB...</p>';

  try {
    const res = await fetch('/api/storage/large-files?min_mb=100');
    if (res.ok) {
      const files = await res.json();
      if (!files || files.length === 0) {
        container.innerHTML = '<p class="text-slate-400 font-mono">No files larger than 100MB found.</p>';
        return;
      }
      container.innerHTML = files.map(f => `
        <div class="p-3 rounded-xl bg-black/40 border border-white/10 flex items-center justify-between text-xs font-mono">
          <span class="truncate max-w-[220px] text-white" title="${escapeHtml(f.path)}">${escapeHtml(f.path)}</span>
          <span class="text-white font-bold">${(f.size_mb||0).toFixed(1)} MB</span>
        </div>
      `).join('');
    }
  } catch (e) {
    container.innerHTML = `<p class="text-rose-400 font-mono">Error: ${escapeHtml(e.message)}</p>`;
  }
}

// ==========================================================================
// NETWORK & FIREWALL
// ==========================================================================
async function loadNetwork() {
  playScifiSound('scan');
  try {
    const res = await fetch('/api/network/ports');
    if (res.ok) {
      const ports = await res.json();
      const tbody = document.getElementById('network-ports-body');
      if (tbody) {
        tbody.innerHTML = (ports || []).map(p => `
          <tr>
            <td class="font-bold text-white font-mono">${p.port}</td>
            <td class="text-slate-400 uppercase font-mono">${p.proto}</td>
            <td class="text-slate-300 font-mono">${p.address}</td>
            <td class="text-slate-400 font-mono truncate max-w-[120px]">${escapeHtml(p.process || '-')}</td>
          </tr>
        `).join('');
      }
    }

    const fwRes = await fetch('/api/network/firewall/status');
    if (fwRes.ok) {
      const fw = await fwRes.json();
      const card = document.getElementById('firewall-status-card');
      if (card) {
        card.innerHTML = `
          <div class="space-y-1">
            <div class="flex items-center space-x-2">
              <span class="w-2 h-2 rounded-full ${fw.active ? 'bg-emerald-400' : 'bg-rose-400'}"></span>
              <span class="font-bold text-white">${escapeHtml(fw.firewall_backend || 'UFW/NFT')}: ${fw.active ? 'ACTIVE & FILTERING' : 'INACTIVE'}</span>
            </div>
            <p class="text-[11px] text-slate-400">${escapeHtml(fw.summary || 'Firewall packet filtering active.')}</p>
          </div>
        `;
      }
    }
  } catch (e) {
    console.error('Failed to load network state', e);
  }
}

function promptFirewallRule(action) {
  const port = document.getElementById('fw-port-input')?.value;
  const proto = document.getElementById('fw-proto-select')?.value || 'tcp';

  if (!port) {
    showToast('Please specify a target port number', 'warning');
    return;
  }

  const cmd = `ufw ${action} ${port}/${proto}`;
  const rollbackCmd = action === 'allow' ? `ufw delete allow ${port}/${proto}` : `ufw delete deny ${port}/${proto}`;

  requestCommandPermission({
    command: cmd,
    description: `Modifies firewall rule matrix to ${action.toUpperCase()} ingress port ${port}/${proto}.`,
    safetyLevel: 'MODIFYING',
    riskScore: 0.45,
    rollback: rollbackCmd,
    onApprove: async () => {
      showToast(`Applying firewall rule: ${cmd}`, 'info');
      try {
        const res = await fetch('/api/network/firewall/rule', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: action, port: parseInt(port, 10), proto: proto })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Firewall rule applied successfully`, 'success');
          loadNetwork();
        } else {
          showToast('Failed to apply firewall rule: ' + data.error, 'error');
        }
      } catch (e) {
        showToast('Error: ' + e.message, 'error');
      }
    }
  });
}

// ==========================================================================
// 16-CLASS FAILURE TAXONOMY & CAUSALITY DAG
// ==========================================================================
async function loadTaxonomyScenarios() {
  try {
    const res = await fetch('/api/taxonomy');
    if (res.ok) {
      const scenarios = await res.json();
      const grid = document.getElementById('taxonomy-scenarios-grid');
      if (!grid) return;

      grid.innerHTML = (scenarios || []).map(sc => `
        <button onclick="runTaxonomyScenario('${escapeHtml(sc.id)}')" class="p-4 rounded-2xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/10 text-left transition space-y-1.5 group">
          <div class="text-xs font-semibold text-white group-hover:text-slate-200 flex items-center space-x-1.5">
            <i data-lucide="zap" class="w-3.5 h-3.5 text-white"></i>
            <span class="truncate">${escapeHtml(sc.name)}</span>
          </div>
          <div class="text-[10px] text-slate-500 font-mono truncate">${escapeHtml(sc.category || 'System')}</div>
        </button>
      `).join('');
      if (window.lucide) lucide.createIcons();
    }
  } catch (e) {
    console.error('Failed to load taxonomy scenarios', e);
  }
}

async function runTaxonomyScenario(scenarioId) {
  playScifiSound('scan');
  const reportContainer = document.getElementById('taxonomy-report-container');
  if (!reportContainer) return;

  reportContainer.classList.remove('hidden');
  document.getElementById('diag-report-title').textContent = `Diagnosing Scenario: ${scenarioId.toUpperCase()}...`;
  document.getElementById('diag-symptom').textContent = 'Correlating multi-vector telemetry across journald, dmesg, and PSI metrics...';
  document.getElementById('diag-root-cause').textContent = 'Constructing directed causality DAG...';
  document.getElementById('diag-rationale').textContent = 'Calculating topological in-degree minimization...';

  try {
    const res = await fetch('/api/taxonomy/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId })
    });
    const report = await res.json();
    playScifiSound('success');

    document.getElementById('diag-report-title').textContent = `XAI Diagnosis: ${report.taxonomy_class || scenarioId.toUpperCase()}`;
    document.getElementById('diag-symptom').textContent = report.symptom || 'Anomaly detected.';
    document.getElementById('diag-root-cause').textContent = report.root_cause || 'Root cause isolated.';
    document.getElementById('diag-rationale').textContent = report.rationale || 'Topological analysis completed.';

    const mermaidContainer = document.getElementById('mermaid-dag-container');
    if (mermaidContainer && report.mermaid_dag) {
      mermaidContainer.innerHTML = `<div class="mermaid">${escapeHtml(report.mermaid_dag)}</div>`;
      if (window.mermaid) {
        mermaid.init(undefined, mermaidContainer.querySelectorAll('.mermaid'));
      }
    } else if (mermaidContainer) {
      mermaidContainer.innerHTML = '<span class="text-xs font-mono text-slate-500">Topological Graph: InDegree=0 Root Isolated</span>';
    }

    const cmdsContainer = document.getElementById('diag-commands-container');
    if (cmdsContainer) {
      const cmds = report.remediation_commands || [];
      if (cmds.length === 0) {
        cmdsContainer.innerHTML = '<p class="text-xs text-white font-mono">No mutating commands required. State is clean.</p>';
      } else {
        cmdsContainer.innerHTML = cmds.map(c => `
          <div class="p-4 rounded-2xl bg-black/50 border border-white/10 space-y-2.5">
            <div class="flex items-center justify-between">
              <span class="${getSafetyBadgeClass(c.safety_level)} text-[10px] font-mono px-3 py-0.5 rounded-full uppercase">${c.safety_level || 'READ_ONLY'}</span>
              <span class="text-[10px] font-mono text-slate-400">Risk: ${(c.risk_score||0.05).toFixed(2)}</span>
            </div>
            <div class="p-3 rounded-xl bg-black/80 font-mono text-xs text-white border border-white/10 flex items-center justify-between">
              <span class="font-semibold text-white">$ ${escapeHtml(c.command)}</span>
              <button onclick="promptExecuteRemediation('${escapeHtml(c.command)}', '${escapeHtml(c.rationale || '')}', '${escapeHtml(c.safety_level || 'READ_ONLY')}', ${c.risk_score || 0.05}, '${escapeHtml(c.rollback || '')}')" class="btn-editorial-primary !py-1 !px-3 text-xs">
                Execute
              </button>
            </div>
            <p class="text-xs text-slate-300 font-sans leading-relaxed">${escapeHtml(c.rationale || 'Remediates root cause.')}</p>
          </div>
        `).join('');
      }
    }
  } catch (e) {
    showToast('Simulation error: ' + e.message, 'error');
  }
}

function promptExecuteRemediation(command, description, safetyLevel, riskScore, rollbackCommand) {
  requestCommandPermission({
    command: command,
    description: description,
    safetyLevel: safetyLevel,
    riskScore: riskScore,
    rollback: rollbackCommand,
    onApprove: () => executeCommandDirect(command, rollbackCommand, null)
  });
}

// ==========================================================================
// AI-POWERED SOFTWARE & DEPENDENCY INSTALLER
// ==========================================================================
let currentInstallerPlan = null;
let currentInstallerSessionId = null;
let installerEventSource = null;

async function loadInstallerTab() {
  await Promise.all([
    fetchInstallerCapabilities(),
    scanProjectDependencies()
  ]);
  if (window.lucide) setTimeout(() => lucide.createIcons(), 50);
}

async function fetchInstallerCapabilities() {
  try {
    const res = await fetch('/api/installer/sources');
    if (res.ok) {
      const caps = await res.json();
      const distroBadge = document.getElementById('pkg-distro-badge');
      const aurBadge = document.getElementById('pkg-aur-badge');
      const flatpakBadge = document.getElementById('pkg-flatpak-badge');

      if (distroBadge) {
        distroBadge.textContent = `${(caps.distro_name || 'LINUX').toUpperCase()} (${(caps.package_manager || 'PKG').toUpperCase()})`;
      }
      if (aurBadge) {
        if (caps.has_yay || caps.has_paru) {
          aurBadge.textContent = caps.has_yay ? 'AUR: YAY' : 'AUR: PARU';
          aurBadge.classList.remove('hidden');
        } else {
          aurBadge.classList.add('hidden');
        }
      }
      if (flatpakBadge) {
        if (caps.has_flatpak) {
          flatpakBadge.classList.remove('hidden');
        } else {
          flatpakBadge.classList.add('hidden');
        }
      }
    }
  } catch (e) {
    console.error('Failed to load installer capabilities', e);
  }
}

function setInstallerPrompt(text) {
  const input = document.getElementById('installer-nl-input');
  if (input) {
    input.value = text;
    resolveAndInstall(text);
  }
}

async function resolveAndInstall(customPrompt) {
  playScifiSound('scan');
  const input = document.getElementById('installer-nl-input');
  const query = customPrompt || input?.value?.trim();

  if (!query) {
    showToast('Please enter what you want to install', 'warning');
    return;
  }

  const liveCard = document.getElementById('installer-live-card');
  const btnResolve = document.getElementById('btn-installer-resolve');
  const targetTitle = document.getElementById('inst-target-title');
  const targetDesc = document.getElementById('inst-target-desc');
  const statusBadge = document.getElementById('inst-status-badge');
  const commandText = document.getElementById('inst-command-text');
  const successBanner = document.getElementById('inst-success-banner');
  const failureBanner = document.getElementById('inst-failure-banner');
  const progressBar = document.getElementById('inst-progress-bar');
  const phaseLabel = document.getElementById('inst-phase-label');
  const percentLabel = document.getElementById('inst-percent-label');
  const logsContainer = document.getElementById('installer-terminal-logs');

  if (btnResolve) {
    btnResolve.disabled = true;
    btnResolve.innerHTML = '<span class="animate-spin">⏳</span><span>Planning...</span>';
  }

  // Reset live view
  if (liveCard) liveCard.classList.remove('hidden');
  if (successBanner) successBanner.classList.add('hidden');
  if (failureBanner) failureBanner.classList.add('hidden');
  if (progressBar) progressBar.style.width = '10%';
  if (percentLabel) percentLabel.textContent = '10%';
  if (phaseLabel) phaseLabel.textContent = 'Phase: Resolving AI installation plan...';
  if (statusBadge) {
    statusBadge.textContent = 'RESOLVING';
    statusBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30';
  }
  if (logsContainer) {
    logsContainer.innerHTML = `<div class="text-cyan-400 font-mono">// Planning installation for: "${escapeHtml(query)}"...</div>`;
  }

  try {
    const res = await fetch('/api/installer/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query })
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Could not resolve installation plan');
    }

    currentInstallerPlan = data.plan;

    if (targetTitle) targetTitle.textContent = currentInstallerPlan.target_name;
    if (targetDesc) targetDesc.textContent = currentInstallerPlan.explanation || `Source: ${currentInstallerPlan.source_label}`;
    if (commandText) commandText.textContent = `$ ${currentInstallerPlan.primary_command}`;

    appendInstallerLog(`[✓] Resolved Source: ${currentInstallerPlan.source_label}`);
    appendInstallerLog(`[✓] Target Type: ${currentInstallerPlan.target_type}`);
    appendInstallerLog(`[✓] Primary Command: ${currentInstallerPlan.primary_command}`);

    if (currentInstallerPlan.requires_confirmation) {
      if (statusBadge) {
        statusBadge.textContent = 'AWAITING CONFIRMATION';
        statusBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-yellow-500/20 text-yellow-300 border border-yellow-500/30';
      }
      if (phaseLabel) phaseLabel.textContent = 'Phase: Root / Sudo confirmation required';
      showToast('Elevation confirmation required. Click "Confirm & Install" to execute.', 'info');
    } else {
      // Auto-start execution if low-risk
      await confirmAndExecuteInstall();
    }

  } catch (e) {
    if (statusBadge) {
      statusBadge.textContent = 'PLAN FAILED';
      statusBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-red-500/20 text-red-300 border border-red-500/30';
    }
    if (failureBanner) {
      failureBanner.classList.remove('hidden');
      document.getElementById('inst-failure-msg').textContent = e.message;
    }
    appendInstallerLog(`[✗] Planning error: ${e.message}`);
    showToast(e.message, 'error');
  } finally {
    if (btnResolve) {
      btnResolve.disabled = false;
      btnResolve.innerHTML = '<i data-lucide="arrow-right-circle" class="w-4.5 h-4.5"></i><span>Plan &amp; Install ↗</span>';
      if (window.lucide) setTimeout(() => lucide.createIcons(), 50);
    }
  }
}

async function confirmAndExecuteInstall() {
  if (!currentInstallerPlan) return;

  const statusBadge = document.getElementById('inst-status-badge');
  const phaseLabel = document.getElementById('inst-phase-label');
  const progressBar = document.getElementById('inst-progress-bar');
  const percentLabel = document.getElementById('inst-percent-label');
  const btnConfirm = document.getElementById('btn-inst-confirm');

  if (btnConfirm) btnConfirm.classList.add('hidden');

  if (statusBadge) {
    statusBadge.textContent = 'INSTALLING';
    statusBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30 animate-pulse';
  }
  if (phaseLabel) phaseLabel.textContent = 'Phase: Initiating package installation...';
  if (progressBar) progressBar.style.width = '25%';
  if (percentLabel) percentLabel.textContent = '25%';

  try {
    const res = await fetch('/api/installer/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: currentInstallerPlan.query,
        plan: currentInstallerPlan,
        confirmed: true
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Execution start failed');
    }

    currentInstallerSessionId = data.session_id;
    connectInstallerStream(currentInstallerSessionId);

  } catch (e) {
    if (statusBadge) {
      statusBadge.textContent = 'EXECUTION FAILED';
      statusBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-red-500/20 text-red-300 border border-red-500/30';
    }
    appendInstallerLog(`[✗] Execution launch failed: ${e.message}`);
    showToast(e.message, 'error');
  }
}

function connectInstallerStream(sessionId) {
  if (installerEventSource) {
    installerEventSource.close();
    installerEventSource = null;
  }

  const progressBar = document.getElementById('inst-progress-bar');
  const phaseLabel = document.getElementById('inst-phase-label');
  const percentLabel = document.getElementById('inst-percent-label');
  const statusBadge = document.getElementById('inst-status-badge');
  const successBanner = document.getElementById('inst-success-banner');
  const failureBanner = document.getElementById('inst-failure-banner');
  const launchGuidance = document.getElementById('inst-launch-guidance');
  const btnConfirm = document.getElementById('btn-inst-confirm');

  try {
    installerEventSource = new EventSource(`/api/installer/stream/${sessionId}`);

    installerEventSource.addEventListener('progress', (e) => {
      try {
        const ev = JSON.parse(e.data);
        if (ev.progress_percent !== undefined && progressBar) {
          progressBar.style.width = `${ev.progress_percent}%`;
          if (percentLabel) percentLabel.textContent = `${ev.progress_percent}%`;
        }
        if (ev.message && phaseLabel) {
          phaseLabel.textContent = `Phase: ${ev.message}`;
        }
        if (ev.log_line) {
          appendInstallerLog(ev.log_line);
        }
      } catch (err) {
        console.error('Error in progress event', err);
      }
    });

    installerEventSource.addEventListener('complete', (e) => {
      try {
        const result = JSON.parse(e.data);
        if (installerEventSource) installerEventSource.close();

        if (result.success) {
          playScifiSound('success');
          if (statusBadge) {
            statusBadge.textContent = 'COMPLETED';
            statusBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
          }
          if (progressBar) progressBar.style.width = '100%';
          if (percentLabel) percentLabel.textContent = '100%';
          if (phaseLabel) phaseLabel.textContent = 'Phase: Installation verified successfully!';
          if (successBanner) {
            successBanner.classList.remove('hidden');
            if (launchGuidance && result.launch_instructions) {
              launchGuidance.textContent = result.launch_instructions;
            }
          }
          appendInstallerLog(`[✓] Installation complete and verified for ${result.target_name}.`);
          showToast(`Successfully installed ${result.target_name}!`, 'success');
        } else {
          playScifiSound('error');
          if (statusBadge) {
            statusBadge.textContent = 'FAILED';
            statusBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-red-500/20 text-red-300 border border-red-500/30';
          }
          if (failureBanner) {
            failureBanner.classList.remove('hidden');
            document.getElementById('inst-failure-msg').textContent = result.error_message || 'Installation encountered an error.';
            const remBox = document.getElementById('inst-failure-rem');
            if (remBox && result.remediation_suggestion) {
              remBox.textContent = `💡 Suggested Fix: ${result.remediation_suggestion}`;
            }
          }
          if (btnConfirm) btnConfirm.classList.remove('hidden');
          appendInstallerLog(`[✗] Error: ${result.error_message}`);
          showToast(`Installation failed: ${result.error_message}`, 'error');
        }
      } catch (err) {
        console.error('Error parsing completion payload', err);
      }
    });

    installerEventSource.addEventListener('cancelled', (e) => {
      if (installerEventSource) installerEventSource.close();
      if (statusBadge) {
        statusBadge.textContent = 'CANCELLED';
        statusBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-slate-500/20 text-slate-300 border border-slate-500/30';
      }
      appendInstallerLog(`[!] Installation cancelled.`);
      showToast('Installation cancelled.', 'warning');
    });

    installerEventSource.onerror = () => {
      // Reconnection or close
    };

  } catch (e) {
    console.error('SSE connection error', e);
  }
}

async function cancelActiveInstall() {
  if (!currentInstallerSessionId) return;
  try {
    await fetch('/api/installer/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: currentInstallerSessionId })
    });
    showToast('Sent cancellation request', 'info');
  } catch (e) {
    console.error('Cancel request failed', e);
  }
}

async function retryActiveInstall() {
  if (currentInstallerPlan) {
    await confirmAndExecuteInstall();
  }
}

async function scanProjectDependencies() {
  const container = document.getElementById('project-detector-box');
  if (!container) return;

  container.innerHTML = `
    <div class="flex items-center justify-between text-slate-400">
      <span>Scanning project manifests...</span>
      <div class="w-4 h-4 rounded-full border-2 border-emerald-400 border-t-transparent animate-spin"></div>
    </div>
  `;

  try {
    const res = await fetch('/api/installer/project-detect');
    const data = await res.json();

    if (res.ok && data.detected && data.plan) {
      const plan = data.plan;
      container.innerHTML = `
        <div class="space-y-2.5">
          <div class="flex items-center justify-between text-white font-bold">
            <span class="text-emerald-300 flex items-center space-x-1.5">
              <span>●</span>
              <span>${escapeHtml(plan.target_name)}</span>
            </span>
            <span class="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">${plan.source_label}</span>
          </div>
          <p class="text-slate-300 leading-relaxed">${escapeHtml(plan.explanation)}</p>
          <div class="p-2.5 rounded-lg bg-black/70 border border-white/10 text-yellow-300 text-[11px] font-mono break-all">
            $ ${escapeHtml(plan.primary_command)}
          </div>
          <div class="pt-2 flex justify-end">
            <button onclick="installProjectDependencies()" class="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs font-mono transition flex items-center space-x-1.5 shadow-[0_0_20px_rgba(16,185,129,0.3)]">
              <span>Install All Project Dependencies</span>
              <span>↗</span>
            </button>
          </div>
        </div>
      `;
    } else {
      container.innerHTML = `
        <div class="text-slate-400 space-y-1">
          <p>No project manifest found in current directory.</p>
          <p class="text-[11px] text-slate-500">Supports Python (requirements.txt/pyproject.toml), Node (package.json), Rust (Cargo.toml), Go (go.mod), Java (pom.xml).</p>
        </div>
      `;
    }
  } catch (e) {
    container.innerHTML = `<div class="text-rose-400">Scan failed: ${escapeHtml(e.message)}</div>`;
  }
}

function installProjectDependencies() {
  setInstallerPrompt("Install this project's dependencies");
}

function installLocalFile() {
  const filePath = document.getElementById('installer-file-path')?.value?.trim();
  if (!filePath) {
    showToast('Please provide a file path (.deb, .rpm, .AppImage, .tar.gz)', 'warning');
    return;
  }
  setInstallerPrompt(`Install ${filePath}`);
}

function appendInstallerLog(line) {
  const logsContainer = document.getElementById('installer-terminal-logs');
  if (!logsContainer) return;
  const div = document.createElement('div');
  div.className = 'font-mono text-xs leading-relaxed text-slate-300 border-l border-cyan-500/20 pl-2';
  div.textContent = line;
  logsContainer.appendChild(div);
  logsContainer.scrollTop = logsContainer.scrollHeight;
}

function copyInstallCommand() {
  const cmd = document.getElementById('inst-command-text')?.textContent?.replace(/^\$\s*/, '');
  if (cmd) {
    navigator.clipboard.writeText(cmd).then(() => {
      showToast('Command copied to clipboard', 'success');
    });
  }
}

function clearInstallerLogs() {
  const logsContainer = document.getElementById('installer-terminal-logs');
  if (logsContainer) {
    logsContainer.innerHTML = '<div class="text-slate-500">// Terminal log view cleared</div>';
  }
}

// ==========================================================================
// DIRECT COMMAND RUNNER & DESKTOP TOOLS
// ==========================================================================
function promptDirectCommand() {
  const cmd = document.getElementById('direct-cmd-input')?.value;
  if (!cmd) {
    showToast('Enter a command to run', 'warning');
    return;
  }

  requestCommandPermission({
    command: cmd,
    description: 'Direct shell execution requested through AST safety gate.',
    safetyLevel: 'MODIFYING',
    riskScore: 0.35,
    onApprove: () => executeCommandDirect(cmd, null, null)
  });
}

function promptDownload() {
  const url = document.getElementById('download-url-input')?.value;
  const dest = document.getElementById('download-dest-input')?.value || '~/Downloads';
  const autoExtract = document.getElementById('download-auto-extract')?.checked;

  if (!url) {
    showToast('Please specify a download URL', 'warning');
    return;
  }

  requestCommandPermission({
    command: `ops-assistant download "${url}" --dest "${dest}" ${autoExtract ? '--auto-extract' : ''}`,
    description: `Downloads file from ${url} into ${dest} with hash integrity verification.`,
    safetyLevel: 'MODIFYING',
    riskScore: 0.30,
    onApprove: async () => {
      showToast('Starting stream download...', 'info');
      const container = document.getElementById('download-result-container');
      if (container) {
        container.classList.remove('hidden');
        container.innerHTML = '<span class="text-slate-400">Streaming bytes from remote host...</span>';
      }
      try {
        const res = await fetch('/api/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: url, destination: dest, auto_extract: autoExtract })
        });
        const data = await res.json();
        if (container) {
          if (data.success) {
            container.innerHTML = `
              <div class="text-white font-bold">&check; Download completed: ${escapeHtml(data.filename || 'file')} (${(data.size_mb || 0).toFixed(2)} MB) in ${dest}</div>
            `;
          } else {
            container.innerHTML = `<span class="text-rose-400">Download failed: ${escapeHtml(data.error)}</span>`;
          }
        }
      } catch (e) {
        if (container) container.innerHTML = `<span class="text-rose-400">Error: ${escapeHtml(e.message)}</span>`;
      }
    }
  });
}

async function desktopAction(action, params) {
  playScifiSound('execute');
  try {
    const res = await fetch('/api/desktop/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: action, ...params })
    });
    const data = await res.json();
    if (data.success) {
      showToast('Desktop action triggered', 'success');
    } else {
      showToast('Failed to trigger action: ' + data.error, 'error');
    }
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ==========================================================================
// MODAL & UTILITY HELPERS
// ==========================================================================
function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove('hidden');
}

function closeModal(id) {
  playScifiSound('click');
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('hidden');
}

function getSafetyBadgeClass(lvl) {
  if (lvl === 'READ_ONLY') return 'badge-readonly';
  if (lvl === 'MODIFYING') return 'badge-modifying';
  if (lvl === 'HIGH_RISK') return 'badge-highrisk';
  if (lvl === 'DESTRUCTIVE') return 'badge-destructive';
  return 'badge-readonly';
}

function getSafetyTextColor(lvl) {
  if (lvl === 'READ_ONLY') return 'text-sky-400';
  if (lvl === 'MODIFYING') return 'text-amber-400';
  if (lvl === 'HIGH_RISK') return 'text-rose-400';
  if (lvl === 'DESTRUCTIVE') return 'text-rose-500';
  return 'text-white';
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ==========================================================================
// EXPLAINABLE AI (XAI) MODAL & SEMANTIC DECONSTRUCTION
// ==========================================================================
let currentExplainCommandStr = '';

async function explainCommandModal(cmd) {
  if (!cmd || !cmd.trim()) return;
  playScifiSound('click');
  currentExplainCommandStr = cmd.trim();

  const cmdEl = document.getElementById('modal-explain-command');
  const sumEl = document.getElementById('modal-explain-summary');
  const safEl = document.getElementById('modal-explain-safety');
  const binEl = document.getElementById('modal-explain-binary');
  const flgEl = document.getElementById('modal-explain-flags');

  if (cmdEl) cmdEl.textContent = currentExplainCommandStr;
  if (sumEl) sumEl.innerHTML = '<span class="text-slate-400">Deconstructing command flags and semantics...</span>';
  if (safEl) safEl.textContent = 'ANALYZING';
  if (binEl) binEl.textContent = '...';
  if (flgEl) flgEl.innerHTML = '';

  openModal('modal-explain');

  try {
    const res = await fetch('/api/command/explain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: currentExplainCommandStr })
    });
    const data = await res.json();

    if (sumEl) {
      sumEl.textContent = data.ai_summary || data.summary || 'Command deconstruction complete.';
    }
    if (safEl) {
      safEl.textContent = data.safety_level || 'READ_ONLY';
      safEl.className = 'font-bold text-sm ' + getSafetyTextColor(data.safety_level || 'READ_ONLY');
    }
    if (binEl) {
      binEl.textContent = data.command_binary || data.binary || currentExplainCommandStr.split(' ')[0];
    }
    if (flgEl) {
      const flags = data.flags || [];
      if (flags.length === 0) {
        flgEl.innerHTML = '<div class="text-xs text-slate-400 font-mono italic">No explicit flag modifiers passed.</div>';
      } else {
        flgEl.innerHTML = flags.map(f => `
          <div class="p-3 rounded-xl bg-black/40 border border-white/10 flex items-start space-x-3 text-xs">
            <span class="font-mono font-bold text-cyan-300 px-2 py-0.5 rounded bg-cyan-950/40 border border-cyan-800/40 shrink-0">${escapeHtml(f.flag || f.name || '-')}</span>
            <div class="space-y-0.5 flex-1">
              <span class="font-semibold text-white block">${escapeHtml(f.description || f.meaning || 'Flag modifier')}</span>
              ${f.safety_impact ? `<span class="text-[10px] text-amber-300 font-mono block">Impact: ${escapeHtml(f.safety_impact)}</span>` : ''}
            </div>
          </div>
        `).join('');
      }
    }
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    if (sumEl) sumEl.innerHTML = `<span class="text-rose-400">Failed to deconstruct: ${escapeHtml(e.message)}</span>`;
  }
}

function copyExplainCommand() {
  if (currentExplainCommandStr) {
    navigator.clipboard.writeText(currentExplainCommandStr);
    showToast('Command copied to clipboard', 'info', 1500);
  }
}

// ==========================================================================
// SETTINGS MODAL & GEMINI CONFIGURATION
// ==========================================================================
async function openSettingsModal() {
  playScifiSound('click');
  openModal('modal-settings');

  // Load Gemini Config
  try {
    const res = await fetch('/api/config/gemini');
    const data = await res.json();
    const statusBadge = document.getElementById('settings-gemini-status');
    const modelSelect = document.getElementById('settings-gemini-model');
    const keyInput = document.getElementById('settings-gemini-key');

    if (statusBadge) {
      if (data.configured) {
        statusBadge.textContent = `Configured (${data.masked_key || 'API Key Saved'})`;
        statusBadge.className = 'text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
      } else {
        statusBadge.textContent = 'Not Configured';
        statusBadge.className = 'text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30';
      }
    }
    if (modelSelect && data.model) {
      modelSelect.value = data.model;
    }
    if (keyInput) {
      keyInput.value = '';
    }
  } catch (e) {}

  // Load Working Directory
  try {
    const res = await fetch('/api/system/cwd');
    const data = await res.json();
    const cwdInput = document.getElementById('settings-cwd-input');
    if (cwdInput && data.cwd) {
      cwdInput.value = data.cwd;
    }
  } catch (e) {}

  // Load Local Model Hub
  await loadModelHub();

  if (window.lucide) lucide.createIcons();
}

async function saveGeminiSettings() {
  playScifiSound('click');
  const keyInput = document.getElementById('settings-gemini-key');
  const modelSelect = document.getElementById('settings-gemini-model');
  const apiKey = keyInput ? keyInput.value.trim() : '';
  const model = modelSelect ? modelSelect.value : 'gemini-2.0-flash';

  try {
    const res = await fetch('/api/config/gemini', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey, model: model, set_provider: true })
    });
    const data = await res.json();
    if (data.success) {
      showToast('Gemini Copilot configuration updated', 'success', 2500);
      closeModal('modal-settings');
    } else {
      showToast('Failed to save settings: ' + (data.error || 'Unknown error'), 'error');
    }
  } catch (e) {
    showToast('Error saving settings: ' + e.message, 'error');
  }
}

async function saveWorkingDir() {
  playScifiSound('click');
  const cwdInput = document.getElementById('settings-cwd-input');
  const newPath = cwdInput ? cwdInput.value.trim() : '';
  if (!newPath) return;

  try {
    const res = await fetch('/api/system/cwd', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: newPath })
    });
    const data = await res.json();
    if (data.success) {
      showToast('Working directory set: ' + data.cwd, 'success', 2500);
    } else {
      showToast('Failed to set directory: ' + (data.error || 'Not found'), 'error');
    }
  } catch (e) {
    showToast('Error setting directory: ' + e.message, 'error');
  }
}

function togglePasswordVisibility(inputId) {
  const input = document.getElementById(inputId);
  if (input) {
    input.type = input.type === 'password' ? 'text' : 'password';
  }
}

// ==========================================================================
// BACKGROUND INSTALLATION STATUS & MODEL HUB MANAGEMENT
// ==========================================================================
let lastInstallStatus = null;

const MODEL_CATALOG_INFO = {
  "deterministic": { name: "Deterministic Rule Engine", size: "0 MB", ram: "< 50 MB", desc: "Sub-50ms triage, 16 failure taxonomies, zero RAM overhead", provider: "deterministic" },
  "smollm2-360m": { name: "SmolLM2-360M-Instruct", size: "218 MB", ram: "800 MB", desc: "Ultra-lightweight edge triage & micro-VM queries", provider: "gguf" },
  "qwen2.5-coder-0.5b": { name: "Qwen2.5-Coder-0.5B-Instruct", size: "379 MB", ram: "1.2 GB", desc: "Fast command syntax parsing & log triage", provider: "gguf" },
  "qwen2.5-coder-1.5b": { name: "Qwen2.5-Coder-1.5B-Instruct", size: "986 MB", ram: "2.5 GB", desc: "Balanced speed/precision, awk/sed/grep synthesis", provider: "gguf" },
  "llama-3.2-3b": { name: "Llama-3.2-3B-Instruct", size: "1.92 GB", ram: "4.5 GB", desc: "Multi-step incident reasoning & structured JSON", provider: "gguf" },
  "qwen2.5-coder-7b": { name: "Qwen2.5-Coder-7B-Instruct", size: "4.36 GB", ram: "8.5 GB", desc: "Deep Linux internals, SELinux, bash scripting", provider: "gguf" },
  "mistral-7b-instruct": { name: "Mistral-7B-Instruct-v0.3", size: "4.07 GB", ram: "8.0 GB", desc: "Multi-daemon log correlation & interactive REPL", provider: "gguf" },
  "deepseek-r1-distill-qwen-7b": { name: "DeepSeek-R1-Distill-7B", size: "4.58 GB", ram: "9.0 GB", desc: "Chain-of-Thought (CoT) root cause formal proofs", provider: "gguf" },
  "ollama": { name: "Local Ollama Daemon", size: "Custom", ram: "Host-managed", desc: "Connects to existing http://localhost:11434", provider: "ollama" }
};

async function checkInstallStatus() {
  try {
    const res = await fetch('/api/install-status');
    if (!res.ok) return;
    const data = await res.json();
    const st = data.status || {};
    const notifBar = document.getElementById('install-notification-bar');
    const badgePct = document.getElementById('install-badge-pct');
    const stepLabel = document.getElementById('install-step-label');
    const progBar = document.getElementById('install-progress-bar');
    const activeBadge = document.getElementById('settings-active-model-badge');

    const isEnhancing = (data.install_phase === 'enhancing' || data.install_phase === 'core_only') && 
                        (st.status === 'running' || st.status === 'downloading' || st.status === 'installing' || st.status === 'seeding') &&
                        st.is_alive;

    if (activeBadge) {
      const activeName = data.provider === 'deterministic' ? 'Deterministic Engine (0 MB)' :
                         data.provider === 'ollama' ? 'Ollama Daemon' :
                         (data.active_model_key || 'Auto');
      activeBadge.textContent = `Active: ${activeName}`;
    }

    if (notifBar) {
      if (isEnhancing) {
        notifBar.classList.remove('hidden');
        const pct = Math.min(100, Math.max(0, parseFloat(st.progress_pct || 0))).toFixed(1);
        if (badgePct) badgePct.textContent = `${pct}%`;
        if (stepLabel) stepLabel.textContent = st.step_label || 'Setting up background components...';
        if (progBar) progBar.style.width = `${pct}%`;
      } else {
        if (!notifBar.classList.contains('hidden') && lastInstallStatus && lastInstallStatus.isEnhancing && !isEnhancing) {
          // Just completed!
          if (progBar) progBar.style.width = '100%';
          if (stepLabel) stepLabel.textContent = 'Background enhancement completed! AI model ready.';
          showToast('Background setup completed! AI Model is now active.', 'success', 4000);
          setTimeout(() => {
            notifBar.classList.add('hidden');
          }, 3000);
        } else {
          notifBar.classList.add('hidden');
        }
      }
    }

    lastInstallStatus = { ...data, isEnhancing };

    // If modal-settings is open, refresh model hub
    const modalSettings = document.getElementById('modal-settings');
    if (modalSettings && !modalSettings.classList.contains('hidden')) {
      renderModelHubList(data);
    }
  } catch (e) {}
}

function renderModelHubList(installData) {
  const container = document.getElementById('settings-model-hub-list');
  if (!container) return;

  const installedModels = installData.installed_models || {};
  const activeKey = installData.active_model_key;
  const currentProvider = installData.provider;
  const downloads = installData.downloads || {};
  const trackerStatus = (installData.status && installData.status.status === 'downloading') ? installData.status : null;

  let html = '';

  for (const [key, info] of Object.entries(MODEL_CATALOG_INFO)) {
    const isDet = key === 'deterministic';
    const isOllama = key === 'ollama';
    const isDownloaded = isDet || isOllama || (installedModels[key] && installedModels[key].is_downloaded);
    const isActive = (isDet && currentProvider === 'deterministic') ||
                     (isOllama && currentProvider === 'ollama') ||
                     (!isDet && !isOllama && currentProvider === 'gguf' && activeKey === key);

    const activeDl = downloads[key] || (trackerStatus && trackerStatus.model_key === key ? trackerStatus : null);
    const isDownloading = activeDl && (activeDl.status === 'downloading' || activeDl.status === 'running');
    const dlPct = isDownloading ? (activeDl.percent || activeDl.progress_pct || 0) : 0;

    let badgeHtml = '';
    if (isActive) {
      badgeHtml = '<span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">ACTIVE</span>';
    } else if (isDownloading) {
      badgeHtml = `<span class="text-[10px] font-mono px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse">DOWNLOADING ${dlPct.toFixed(0)}%</span>`;
    } else if (isDownloaded) {
      badgeHtml = '<span class="text-[10px] font-mono px-2 py-0.5 rounded-md bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">DOWNLOADED</span>';
    } else {
      badgeHtml = '<span class="text-[10px] font-mono px-2 py-0.5 rounded-md bg-white/10 text-slate-400">AVAILABLE</span>';
    }

    let actionBtnHtml = '';
    if (isActive) {
      actionBtnHtml = '<button disabled class="px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 text-xs font-mono border border-emerald-500/20 cursor-default opacity-80">In Use ✓</button>';
    } else if (isDownloading) {
      actionBtnHtml = `<div class="text-xs font-mono text-amber-300 flex items-center space-x-1.5"><i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>${dlPct.toFixed(0)}%</span></div>`;
    } else if (isDownloaded) {
      actionBtnHtml = `<button onclick="switchActiveModel('${key}', '${info.provider}')" class="px-3 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-200 hover:text-white border border-cyan-500/40 text-xs font-mono transition cursor-pointer">Switch ↗</button>`;
    } else {
      actionBtnHtml = `<button onclick="downloadCatalogModel('${key}')" class="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-slate-200 hover:text-white border border-white/20 text-xs font-mono transition cursor-pointer flex items-center space-x-1"><i data-lucide="download" class="w-3 h-3"></i><span>Download</span></button>`;
    }

    html += `
      <div class="p-3 rounded-xl ${isActive ? 'bg-cyan-950/40 border-cyan-500/40' : 'bg-white/[0.02] border-white/10'} border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2.5 transition">
        <div class="flex-1 min-w-0">
          <div class="flex items-center space-x-2">
            <span class="text-xs font-semibold text-white font-sans truncate">${info.name}</span>
            ${badgeHtml}
          </div>
          <p class="text-[11px] text-slate-400 font-sans mt-0.5 line-clamp-1">${info.desc}</p>
          <div class="flex items-center space-x-3 text-[10px] font-mono text-slate-400 mt-1">
            <span>Disk: <strong class="text-slate-300 font-normal">${info.size}</strong></span>
            <span>RAM: <strong class="text-slate-300 font-normal">${info.ram}</strong></span>
          </div>
          ${isDownloading ? `
            <div class="w-full bg-white/10 rounded-full h-1.5 mt-2 overflow-hidden">
              <div class="bg-gradient-to-r from-amber-400 to-cyan-400 h-full rounded-full transition-all duration-200" style="width: ${dlPct}%"></div>
            </div>
          ` : ''}
        </div>
        <div class="shrink-0 self-end sm:self-center">
          ${actionBtnHtml}
        </div>
      </div>
    `;
  }

  container.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

async function loadModelHub() {
  try {
    const res = await fetch('/api/install-status');
    const data = await res.json();
    renderModelHubList(data);
  } catch (e) {}
}

async function switchActiveModel(modelKey, provider) {
  playScifiSound('click');
  try {
    showToast(`Switching active engine to ${modelKey}...`, 'info', 2000);
    const res = await fetch('/api/models/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_key: modelKey, provider: provider || 'gguf' })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message || `Switched to ${modelKey}`, 'success', 3000);
      playScifiSound('success');
      await checkInstallStatus();
      await loadModelHub();
    } else {
      showToast(data.error || 'Failed to switch model', 'error');
    }
  } catch (e) {
    showToast('Error switching model: ' + e.message, 'error');
  }
}

async function downloadCatalogModel(modelKey) {
  playScifiSound('click');
  try {
    showToast(`Initiating download for ${modelKey}...`, 'info', 2000);
    const res = await fetch('/api/models/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_key: modelKey })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Downloading ${modelKey} weights in background...`, 'success', 3000);
      await checkInstallStatus();
      await loadModelHub();
    } else {
      showToast(data.error || 'Failed to start download', 'error');
    }
  } catch (e) {
    showToast('Error starting download: ' + e.message, 'error');
  }
}

// ==========================================================================
// INTELLIGENT NATURAL LANGUAGE AUTO-COMPLETE SUBSYSTEM
// ==========================================================================

const autocompleteState = {
  isOpen: false,
  suggestions: [],
  selectedIndex: -1,
  currentQuery: '',
  cache: new Map(),
  debounceTimer: null,
  abortController: null,
};

function initAutocomplete() {
  const input = document.getElementById('agent-prompt-input');
  const dropdown = document.getElementById('autocomplete-dropdown');
  if (!input || !dropdown) return;

  // 1. Keystroke input listener with debouncing
  input.addEventListener('input', (e) => {
    const val = e.target.value;
    clearTimeout(autocompleteState.debounceTimer);
    if (!val || !val.trim()) {
      hideAutocomplete();
      return;
    }
    autocompleteState.debounceTimer = setTimeout(() => {
      fetchAutocompleteSuggestions(val.trim());
    }, 30);
  });

  // 2. Focus & Click listener on input
  input.addEventListener('focus', () => {
    const val = input.value.trim();
    if (val.length >= 1) {
      fetchAutocompleteSuggestions(val);
    }
  });

  // 3. Keyboard navigation listener (Keydown)
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') {
      if (!autocompleteState.isOpen || autocompleteState.suggestions.length === 0) {
        const val = input.value.trim();
        if (val) fetchAutocompleteSuggestions(val);
        return;
      }
      e.preventDefault();
      navigateAutocomplete(1);
      return;
    }

    if (e.key === 'ArrowUp') {
      if (autocompleteState.isOpen && autocompleteState.suggestions.length > 0) {
        e.preventDefault();
        navigateAutocomplete(-1);
      }
      return;
    }

    if (e.key === 'Tab') {
      if (autocompleteState.isOpen && autocompleteState.suggestions.length > 0) {
        e.preventDefault();
        acceptAutocomplete(false);
      }
      return;
    }

    if (e.key === 'ArrowRight') {
      // Auto-complete if at end of input line
      if (autocompleteState.isOpen && autocompleteState.suggestions.length > 0 && input.selectionStart === input.value.length) {
        e.preventDefault();
        acceptAutocomplete(false);
      }
      return;
    }

    if (e.key === 'Enter') {
      if (autocompleteState.isOpen && autocompleteState.selectedIndex >= 0) {
        e.preventDefault();
        acceptAutocomplete(true);
      }
      return;
    }

    if (e.key === 'Escape') {
      if (autocompleteState.isOpen) {
        e.preventDefault();
        hideAutocomplete();
      }
      return;
    }
  });

  // 4. Click outside handler to dismiss
  document.addEventListener('click', (e) => {
    if (!dropdown.contains(e.target) && e.target !== input) {
      hideAutocomplete();
    }
  });
}

async function fetchAutocompleteSuggestions(query) {
  const dropdown = document.getElementById('autocomplete-dropdown');
  if (!dropdown) return;

  autocompleteState.currentQuery = query;

  // Retrieve current active directory from settings or system state if available
  let cwd = '';
  const cwdInput = document.getElementById('settings-cwd-input');
  if (cwdInput && cwdInput.value.trim()) {
    cwd = cwdInput.value.trim();
  }

  const cacheKey = `${query}::${cwd}`;
  if (autocompleteState.cache.has(cacheKey)) {
    const cached = autocompleteState.cache.get(cacheKey);
    renderAutocompleteDropdown(cached, query);
    return;
  }

  if (autocompleteState.abortController) {
    autocompleteState.abortController.abort();
  }
  autocompleteState.abortController = new AbortController();

  try {
    const url = `/api/autocomplete?q=${encodeURIComponent(query)}&cwd=${encodeURIComponent(cwd)}&limit=8`;
    const res = await fetch(url, {
      signal: autocompleteState.abortController.signal,
      headers: { 'Accept': 'application/json' }
    });
    if (!res.ok) return;
    const data = await res.json();
    if (data && Array.isArray(data.suggestions)) {
      // Keep cache under 100 entries
      if (autocompleteState.cache.size > 100) {
        const firstKey = autocompleteState.cache.keys().next().value;
        autocompleteState.cache.delete(firstKey);
      }
      autocompleteState.cache.set(cacheKey, data.suggestions);

      // Only render if query matches current active query
      if (autocompleteState.currentQuery === query) {
        renderAutocompleteDropdown(data.suggestions, query);
      }
    }
  } catch (err) {
    if (err.name !== 'AbortError') {
      console.warn('Autocomplete fetch error:', err);
    }
  }
}

function formatCategoryBadge(cat) {
  let label = 'Linux Task';
  let badgeClass = 'autocomplete-badge-linux_task';
  let icon = 'terminal';

  if (cat === 'smart_intent') {
    label = 'Smart Intent';
    badgeClass = 'autocomplete-badge-smart_intent';
    icon = 'zap';
  } else if (cat === 'project') {
    label = 'Project Context';
    badgeClass = 'autocomplete-badge-project';
    icon = 'package';
  } else if (cat === 'history') {
    label = 'Recent History';
    badgeClass = 'autocomplete-badge-history';
    icon = 'clock';
  } else if (cat === 'cwd') {
    label = 'Active Directory';
    badgeClass = 'autocomplete-badge-cwd';
    icon = 'folder';
  } else if (cat === 'installed_tool') {
    label = 'Installed Tool';
    badgeClass = 'autocomplete-badge-linux_task';
    icon = 'wrench';
  }

  return { label, badgeClass, icon };
}

function highlightTextWithRanges(text, ranges) {
  if (!ranges || ranges.length === 0) return escapeHtml(text);
  let html = '';
  let lastIdx = 0;
  for (const [start, end] of ranges) {
    if (start > lastIdx) {
      html += escapeHtml(text.slice(lastIdx, start));
    }
    html += `<span class="autocomplete-highlight">${escapeHtml(text.slice(start, end))}</span>`;
    lastIdx = end;
  }
  if (lastIdx < text.length) {
    html += escapeHtml(text.slice(lastIdx));
  }
  return html;
}

function renderAutocompleteDropdown(suggestions, query) {
  const dropdown = document.getElementById('autocomplete-dropdown');
  if (!dropdown) return;

  if (!suggestions || suggestions.length === 0) {
    hideAutocomplete();
    return;
  }

  autocompleteState.suggestions = suggestions;
  autocompleteState.selectedIndex = -1;

  let itemsHtml = '';
  suggestions.forEach((item, idx) => {
    const badgeInfo = formatCategoryBadge(item.category);
    const highlightedTitle = highlightTextWithRanges(item.text, item.highlight_ranges || []);
    const itemIcon = item.icon || badgeInfo.icon;
    const preview = item.command_preview ? escapeHtml(item.command_preview) : escapeHtml(item.description || '');

    itemsHtml += `
      <div 
        class="autocomplete-item group" 
        id="autocomplete-item-${idx}" 
        data-index="${idx}"
        onclick="selectAutocompleteByIndex(${idx}, true)"
        onmouseenter="highlightAutocompleteIndex(${idx})"
        role="option"
        aria-selected="false">
        <div class="flex items-center space-x-3 min-w-0 pr-3">
          <div class="w-7 h-7 rounded-lg bg-white/5 group-hover:bg-cyan-400/15 flex items-center justify-center shrink-0 border border-white/10 group-hover:border-cyan-400/30 transition">
            <i data-lucide="${itemIcon}" class="w-3.5 h-3.5 text-cyan-300"></i>
          </div>
          <div class="min-w-0 truncate">
            <div class="autocomplete-text text-xs sm:text-sm font-sans font-semibold text-slate-100 group-hover:text-white truncate">
              ${highlightedTitle}
            </div>
            <div class="text-[11px] font-mono text-slate-400 truncate opacity-80 group-hover:opacity-100">
              ${preview}
            </div>
          </div>
        </div>

        <div class="flex items-center space-x-2 shrink-0">
          <span class="autocomplete-badge ${badgeInfo.badgeClass}">
            ${badgeInfo.label}
          </span>
          <button 
            type="button" 
            onclick="event.stopPropagation(); selectAutocompleteByIndex(${idx}, false)" 
            title="Complete (Tab / →)" 
            class="hidden sm:inline-flex opacity-0 group-hover:opacity-100 items-center justify-center p-1 rounded-md bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white transition">
            <i data-lucide="corner-down-left" class="w-3 h-3"></i>
          </button>
        </div>
      </div>
    `;
  });

  // Add navigation hints footer
  itemsHtml += `
    <div class="autocomplete-footer">
      <div class="flex items-center space-x-2">
        <span><span class="autocomplete-keycap">Tab</span> or <span class="autocomplete-keycap">→</span> Complete</span>
        <span><span class="autocomplete-keycap">Enter</span> Execute</span>
        <span><span class="autocomplete-keycap">↑</span><span class="autocomplete-keycap">↓</span> Navigate</span>
      </div>
      <div><span class="autocomplete-keycap">Esc</span> Close</div>
    </div>
  `;

  dropdown.innerHTML = itemsHtml;
  dropdown.classList.remove('hidden');
  autocompleteState.isOpen = true;

  if (window.lucide) {
    lucide.createIcons();
  }
}

function highlightAutocompleteIndex(index) {
  autocompleteState.selectedIndex = index;
  const items = document.querySelectorAll('.autocomplete-item');
  items.forEach((el, i) => {
    if (i === index) {
      el.classList.add('active');
      el.setAttribute('aria-selected', 'true');
    } else {
      el.classList.remove('active');
      el.setAttribute('aria-selected', 'false');
    }
  });
}

function navigateAutocomplete(delta) {
  const len = autocompleteState.suggestions.length;
  if (len === 0) return;

  if (autocompleteState.selectedIndex === -1) {
    autocompleteState.selectedIndex = (delta > 0) ? 0 : len - 1;
  } else {
    autocompleteState.selectedIndex = (autocompleteState.selectedIndex + delta + len) % len;
  }

  highlightAutocompleteIndex(autocompleteState.selectedIndex);

  // Scroll active item into view
  const targetItem = document.getElementById(`autocomplete-item-${autocompleteState.selectedIndex}`);
  if (targetItem) {
    targetItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
}

function selectAutocompleteByIndex(index, execute = false) {
  const item = autocompleteState.suggestions[index];
  if (!item) return;

  const input = document.getElementById('agent-prompt-input');
  if (input) {
    input.value = item.text;
    toggleClearPromptBtn(item.text);
  }

  hideAutocomplete();

  if (execute) {
    submitAgentPrompt(item.text);
  } else if (input) {
    input.focus();
    input.setSelectionRange(item.text.length, item.text.length);
  }
}

function acceptAutocomplete(execute = false) {
  if (!autocompleteState.isOpen || autocompleteState.suggestions.length === 0) return;
  const idx = autocompleteState.selectedIndex >= 0 ? autocompleteState.selectedIndex : 0;
  selectAutocompleteByIndex(idx, execute);
}

function hideAutocomplete() {
  autocompleteState.isOpen = false;
  autocompleteState.selectedIndex = -1;
  const dropdown = document.getElementById('autocomplete-dropdown');
  if (dropdown) {
    dropdown.classList.add('hidden');
  }
}



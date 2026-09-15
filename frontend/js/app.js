/**
 * J.A.R.V.I.S. Web Application — main orchestrator.
 * Connects to the FastAPI backend via WebSocket and wires all subsystems.
 */

import { Visualizer } from './visualizer.js';
import { VoiceInput, browserTTS } from './voice.js';
import { HUDLog } from './hud.js';

// ─── DOM refs ────────────────────────────────────────────────────────────────
const textInput   = document.getElementById('text-input');
const sendBtn     = document.getElementById('send-btn');
const micBtn      = document.getElementById('mic-btn');
const conversation = document.getElementById('conversation');
const timeEl      = document.querySelector('.header-time');
const wsDot       = document.getElementById('ws-dot');

// ─── State ────────────────────────────────────────────────────────────────────
let ws = null;
let currentJarvisMsg = null;
let reconnectTimer = null;
let audioEl = null;
let elevenlabsAvailable = false;

// ─── Subsystems ───────────────────────────────────────────────────────────────
const hud  = new HUDLog();
const viz  = new Visualizer();
const voice = new VoiceInput({
  onStart: () => {
    viz.setListening();
    micBtn.classList.add('listening');
    micBtn.title = 'Stop listening';
    hud.log('system', 'VOICE: Microphone active');
  },
  onEnd: () => {
    viz.setIdle();
    micBtn.classList.remove('listening');
    micBtn.title = 'Activate voice input';
    hud.log('system', 'VOICE: Recognition ended');
  },
  onResult: ({ interim, final, isFinal }) => {
    textInput.value = isFinal ? '' : interim;
    if (isFinal && final.trim()) {
      textInput.value = '';
      sendMessage(final.trim());
    }
  },
  onError: (err) => {
    hud.log('error', `VOICE: ${err}`);
    viz.setIdle();
    micBtn.classList.remove('listening');
  },
});

// ─── Clock ────────────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  timeEl.textContent = now.toLocaleTimeString('en-GB', { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ─── WebSocket ────────────────────────────────────────────────────────────────
function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${proto}://${location.host}/ws`;
  hud.log('process', `WS: Connecting to ${url}`);

  ws = new WebSocket(url);

  ws.onopen = () => {
    hud.log('success', 'WS: Connection established');
    wsDot.classList.remove('offline');
    clearTimeout(reconnectTimer);
  };

  ws.onclose = () => {
    hud.log('error', 'WS: Connection lost — reconnecting...');
    wsDot.classList.add('offline');
    reconnectTimer = setTimeout(connect, 3000);
  };

  ws.onerror = () => {
    hud.log('error', 'WS: Connection error');
  };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    handleServerMessage(msg);
  };
}

// ─── Message Handling ─────────────────────────────────────────────────────────
function handleServerMessage(msg) {
  switch (msg.type) {
    case 'connected':
      hud.log('success', 'JARVIS: System online');
      appendSystemMessage(msg.message);
      break;

    case 'jarvis_start':
      currentJarvisMsg = appendMessage('jarvis', '');
      viz.setProcessing();
      break;

    case 'jarvis_token':
      if (currentJarvisMsg) {
        const bubble = currentJarvisMsg.querySelector('.message-bubble');
        if (bubble) bubble.textContent += msg.token;
        conversation.scrollTop = conversation.scrollHeight;
      }
      break;

    case 'jarvis_end':
      currentJarvisMsg = null;
      if (!elevenlabsAvailable) {
        // Use browser TTS as fallback
        browserTTS(msg.full_text);
        viz.setSpeaking();
        const wordCount = msg.full_text.split(' ').length;
        const duration = wordCount * 500; // rough ms estimate
        setTimeout(() => viz.setIdle(), duration);
      }
      break;

    case 'audio':
      elevenlabsAvailable = true;
      playAudioB64(msg.data, msg.format);
      break;

    case 'goal_block':
      appendGoalBlock(msg.content);
      break;

    case 'hud_log':
      hud.log(msg.level, msg.message);
      break;

    case 'hal_result':
      hud.log('hal', `HAL: Result → ${JSON.stringify(msg.result)}`);
      break;

    case 'system':
      appendSystemMessage(msg.message);
      break;
  }
}

// ─── Send message ─────────────────────────────────────────────────────────────
function sendMessage(text) {
  if (!text.trim()) return;
  appendMessage('user', text);
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'chat', text }));
    hud.log('input', `SIR: "${text.slice(0, 60)}${text.length > 60 ? '…' : ''}"`);
  } else {
    hud.log('error', 'WS: Not connected — message queued');
  }
}

// ─── DOM helpers ─────────────────────────────────────────────────────────────
function appendMessage(role, text) {
  // Remove any typing indicator
  document.querySelector('.typing-indicator-wrap')?.remove();

  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;

  const header = document.createElement('div');
  header.className = 'message-header';
  header.textContent = role === 'user' ? '» SIR' : '◈ J.A.R.V.I.S.';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = text;

  wrap.appendChild(header);
  wrap.appendChild(bubble);
  conversation.appendChild(wrap);
  conversation.scrollTop = conversation.scrollHeight;
  return wrap;
}

function appendGoalBlock(content) {
  const wrap = document.createElement('div');
  wrap.className = 'message jarvis';

  const header = document.createElement('div');
  header.className = 'message-header';
  header.textContent = '◈ GOAL COMPILER OUTPUT';

  const block = document.createElement('div');
  block.className = 'goal-block';
  block.textContent = content;

  wrap.appendChild(header);
  wrap.appendChild(block);
  conversation.appendChild(wrap);
  conversation.scrollTop = conversation.scrollHeight;
}

function appendSystemMessage(text) {
  const div = document.createElement('div');
  div.style.cssText = 'text-align:center;font-size:0.6rem;color:var(--text-dim);letter-spacing:0.15em;padding:8px 0;text-transform:uppercase;';
  div.textContent = `─── ${text} ───`;
  conversation.appendChild(div);
  conversation.scrollTop = conversation.scrollHeight;
}

// ─── Audio playback ───────────────────────────────────────────────────────────
function playAudioB64(b64, format) {
  const mime = format === 'mp3' ? 'audio/mpeg' : `audio/${format}`;
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const blob = new Blob([bytes], { type: mime });
  const url = URL.createObjectURL(blob);

  if (audioEl) {
    audioEl.pause();
    audioEl.src = '';
  }

  audioEl = new Audio(url);
  audioEl.onplay = () => viz.setSpeaking();
  audioEl.onended = () => {
    viz.setIdle();
    URL.revokeObjectURL(url);
  };
  audioEl.onerror = () => {
    viz.setIdle();
    hud.log('error', 'AUDIO: Playback failed');
  };
  audioEl.play().catch(err => {
    hud.log('error', `AUDIO: ${err.message}`);
  });
}

// ─── HAL quick-action buttons ─────────────────────────────────────────────────
document.querySelectorAll('.hal-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const action = btn.dataset.action;
    const target = btn.dataset.target || '';
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'hal_command', action, target, params: {} }));
      hud.log('hal', `HAL: Manual dispatch — ${action} → ${target || 'default'}`);
    }
  });
});

// ─── Event listeners ─────────────────────────────────────────────────────────
sendBtn.addEventListener('click', () => {
  const text = textInput.value.trim();
  if (text) { sendMessage(text); textInput.value = ''; }
});

textInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    const text = textInput.value.trim();
    if (text) { sendMessage(text); textInput.value = ''; }
  }
});

micBtn.addEventListener('click', async () => {
  if (!voice.available) {
    hud.log('warning', 'VOICE: Speech recognition not supported in this browser');
    return;
  }
  if (voice.listening) {
    voice.stop();
  } else {
    const stream = await voice.start();
    if (stream) {
      viz.attachMicStream(stream);
    }
  }
});

// ─── Boot ─────────────────────────────────────────────────────────────────────
connect();

/**
 * HUD construction log panel — real-time diagnostics display.
 */

const MAX_LOG_ENTRIES = 200;

export class HUDLog {
  constructor() {
    this.container = document.getElementById('hud-log');
    this.entries = 0;
    this._writeSystemBoot();
  }

  _writeSystemBoot() {
    const lines = [
      { level: 'system',  msg: '══════════════════════════════' },
      { level: 'success', msg: 'J.A.R.V.I.S. v1.0.0 ONLINE' },
      { level: 'system',  msg: '══════════════════════════════' },
      { level: 'system',  msg: 'MODULE: Claude Opus 5 — READY' },
      { level: 'system',  msg: 'MODULE: Voice Pipeline — INIT' },
      { level: 'system',  msg: 'MODULE: HAL Bridge — STANDBY' },
      { level: 'system',  msg: 'MODULE: WebSocket — CONNECTING' },
    ];
    lines.forEach((l, i) => {
      setTimeout(() => this.log(l.level, l.msg), i * 120);
    });
  }

  log(level, message) {
    if (this.entries >= MAX_LOG_ENTRIES) {
      this.container.firstChild?.remove();
      this.entries--;
    }

    const now = new Date();
    const ts = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;

    const entry = document.createElement('div');
    entry.className = `log-entry ${level}`;
    entry.innerHTML = `<span class="log-time">[${ts}]</span><span class="log-msg">${escapeHtml(message)}</span>`;

    this.container.appendChild(entry);
    this.container.scrollTop = this.container.scrollHeight;
    this.entries++;
  }

  clear() {
    this.container.innerHTML = '';
    this.entries = 0;
  }
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

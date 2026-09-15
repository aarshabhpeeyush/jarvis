/**
 * Audio wave visualizer and Arc Reactor HUD animation controller.
 * Reacts to both voice input (microphone) and JARVIS speaking (audio playback).
 */

const WAVE_BAR_COUNT = 48;

export class Visualizer {
  constructor() {
    this.container = document.getElementById('voice-visualizer');
    this.arcReactor = document.getElementById('arc-reactor');
    this.modeBadge = document.querySelector('.mode-badge');
    this.bars = [];
    this.animFrame = null;
    this.audioCtx = null;
    this.analyser = null;
    this.dataArray = null;
    this.mode = 'idle'; // idle | listening | speaking

    this._buildBars();
    this._buildArcTicks();
    this._idleAnimation();
  }

  _buildBars() {
    this.container.innerHTML = '';
    for (let i = 0; i < WAVE_BAR_COUNT; i++) {
      const bar = document.createElement('div');
      bar.className = 'wave-bar';
      this.container.appendChild(bar);
      this.bars.push(bar);
    }
  }

  _buildArcTicks() {
    const tickCount = 12;
    const outer = this.arcReactor;
    const size = 200;
    for (let i = 0; i < tickCount; i++) {
      const tick = document.createElement('div');
      tick.className = 'arc-tick';
      const angle = (i / tickCount) * 360;
      const len = i % 3 === 0 ? 14 : 8;
      tick.style.cssText = `
        position:absolute;width:1px;height:${len}px;
        background:var(--amber-border);
        top:${(size/2 - size/2)}px;left:50%;
        transform-origin:0 ${size/2}px;
        transform:rotate(${angle}deg) translateX(-50%);
      `;
      outer.appendChild(tick);
    }
  }

  _idleAnimation() {
    if (this.mode !== 'idle') return;
    cancelAnimationFrame(this.animFrame);
    const animate = () => {
      if (this.mode !== 'idle') return;
      const t = Date.now() / 1000;
      this.bars.forEach((bar, i) => {
        const v = 4 + 2 * Math.sin(t * 1.2 + i * 0.3) + Math.random() * 1.5;
        bar.style.height = `${v}px`;
        bar.classList.remove('active');
      });
      this.animFrame = requestAnimationFrame(animate);
    };
    this.animFrame = requestAnimationFrame(animate);
  }

  /** Attach a MediaStream from the microphone for real-time analysis. */
  attachMicStream(stream) {
    this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = this.audioCtx.createMediaStreamSource(stream);
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 128;
    this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    source.connect(this.analyser);
  }

  /** Attach an AudioBuffer or AudioElement for playback analysis. */
  attachAudioElement(audioEl) {
    if (!this.audioCtx) {
      this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    const source = this.audioCtx.createMediaElementSource(audioEl);
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 128;
    this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    source.connect(this.analyser);
    this.analyser.connect(this.audioCtx.destination);
  }

  setListening() {
    this.mode = 'listening';
    this.arcReactor.classList.remove('speaking');
    this.arcReactor.classList.add('listening');
    this.modeBadge.textContent = '● LISTENING';
    this.modeBadge.className = 'mode-badge listening';
    this._analyserLoop();
  }

  setSpeaking() {
    this.mode = 'speaking';
    this.arcReactor.classList.remove('listening');
    this.arcReactor.classList.add('speaking');
    this.modeBadge.textContent = '◈ SPEAKING';
    this.modeBadge.className = 'mode-badge speaking';
    this._analyserLoop();
  }

  setIdle() {
    this.mode = 'idle';
    this.arcReactor.classList.remove('speaking', 'listening');
    this.modeBadge.textContent = '○ STANDBY';
    this.modeBadge.className = 'mode-badge';
    this._idleAnimation();
  }

  setProcessing() {
    this.mode = 'processing';
    cancelAnimationFrame(this.animFrame);
    const animate = () => {
      if (this.mode !== 'processing') return;
      const t = Date.now() / 300;
      this.bars.forEach((bar, i) => {
        const v = 6 + 20 * Math.abs(Math.sin(t + i * 0.2));
        bar.style.height = `${v}px`;
        bar.classList.toggle('active', v > 18);
      });
      this.animFrame = requestAnimationFrame(animate);
    };
    this.animFrame = requestAnimationFrame(animate);
    this.modeBadge.textContent = '⟳ PROCESSING';
    this.modeBadge.className = 'mode-badge';
  }

  _analyserLoop() {
    cancelAnimationFrame(this.animFrame);
    const animate = () => {
      if (this.mode !== 'listening' && this.mode !== 'speaking') return;
      if (this.analyser && this.dataArray) {
        this.analyser.getByteFrequencyData(this.dataArray);
        const step = Math.floor(this.dataArray.length / WAVE_BAR_COUNT);
        this.bars.forEach((bar, i) => {
          const val = this.dataArray[i * step] || 0;
          const h = 4 + (val / 255) * 50;
          bar.style.height = `${h}px`;
          bar.classList.toggle('active', val > 40);
        });
      } else {
        // Simulated activity if no analyser connected yet
        const t = Date.now() / 200;
        this.bars.forEach((bar, i) => {
          const v = 4 + 20 * Math.abs(Math.sin(t + i * 0.35));
          bar.style.height = `${v}px`;
          bar.classList.toggle('active', v > 14);
        });
      }
      this.animFrame = requestAnimationFrame(animate);
    };
    this.animFrame = requestAnimationFrame(animate);
  }
}

/**
 * Voice input — Web Speech API with automatic end-of-speech detection.
 * Falls back gracefully if speech recognition is unavailable.
 */

export class VoiceInput {
  constructor({ onResult, onStart, onEnd, onError }) {
    this.onResult = onResult;
    this.onStart = onStart;
    this.onEnd = onEnd;
    this.onError = onError;
    this.recognition = null;
    this.listening = false;
    this.stream = null;
    this._init();
  }

  _init() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn('Web Speech API not available — text input only.');
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = false;
    this.recognition.interimResults = true;
    this.recognition.lang = 'en-GB'; // British English for Sir
    this.recognition.maxAlternatives = 1;

    this.recognition.onstart = () => {
      this.listening = true;
      this.onStart?.();
    };

    this.recognition.onresult = (e) => {
      let interim = '';
      let final = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) final += t;
        else interim += t;
      }
      this.onResult?.({ interim, final, isFinal: !!final });
    };

    this.recognition.onend = () => {
      this.listening = false;
      this.onEnd?.();
    };

    this.recognition.onerror = (e) => {
      this.listening = false;
      this.onError?.(e.error);
    };
  }

  get available() {
    return !!this.recognition;
  }

  async start() {
    if (!this.recognition) return false;
    try {
      // Request mic permission for visualizer
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.recognition.start();
      return this.stream;
    } catch (err) {
      this.onError?.(err.message);
      return false;
    }
  }

  stop() {
    if (this.recognition && this.listening) {
      this.recognition.stop();
    }
    if (this.stream) {
      this.stream.getTracks().forEach(t => t.stop());
      this.stream = null;
    }
  }

  toggle() {
    if (this.listening) {
      this.stop();
    } else {
      this.start();
    }
  }
}


/** Browser TTS fallback when ElevenLabs is not configured. */
export function browserTTS(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = 'en-GB';
  utt.rate = 0.95;
  utt.pitch = 0.9;

  // Pick a British male voice if available
  const voices = window.speechSynthesis.getVoices();
  const britishMale = voices.find(v =>
    (v.lang === 'en-GB' || v.lang.startsWith('en-GB')) && /male|daniel|george/i.test(v.name)
  ) || voices.find(v => v.lang === 'en-GB') || null;

  if (britishMale) utt.voice = britishMale;
  window.speechSynthesis.speak(utt);
  return utt;
}

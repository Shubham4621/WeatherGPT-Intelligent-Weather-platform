import type { Language } from '../i18n';
import { recognitionLocale } from './speechRecognition';

export interface VoiceOption { lang: string; name: string; default?: boolean }
export interface SpeechUtterancePort {
  lang: string; voice: VoiceOption | null; rate: number;
  onstart: (() => void) | null; onend: (() => void) | null; onerror: (() => void) | null;
}
export interface SynthesisPort {
  speaking: boolean; cancel(): void; speak(utterance: SpeechUtterancePort): void; getVoices(): VoiceOption[];
}
export type UtteranceFactory = (text: string) => SpeechUtterancePort;

export function preferredVoice(voices: VoiceOption[], language: Language): { voice: VoiceOption | null; fallback: boolean } {
  const locale = recognitionLocale(language).toLowerCase();
  const prefix = locale.split('-')[0];
  const voice = voices.find((item) => item.lang.toLowerCase() === locale)
    ?? voices.find((item) => item.lang.toLowerCase().startsWith(`${prefix}-`))
    ?? voices.find((item) => item.default)
    ?? voices[0]
    ?? null;
  return { voice, fallback: !voice || (voice.lang.toLowerCase() !== locale && !voice.lang.toLowerCase().startsWith(`${prefix}-`)) };
}

export class SpeechSynthesisService {
  constructor(
    private readonly synthesis: SynthesisPort | null = typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis as unknown as SynthesisPort : null,
    private readonly makeUtterance?: UtteranceFactory,
  ) {}

  speak(text: string, language: Language, callbacks: { start?: () => void; end?: () => void; error?: () => void } = {}): { ok: boolean; fallback: boolean } {
    if (!this.synthesis || (!this.makeUtterance && typeof SpeechSynthesisUtterance === 'undefined') || !text.trim()) return { ok: false, fallback: false };
    this.stop();
    try {
      const utterance = this.makeUtterance
        ? this.makeUtterance(text.trim())
        : new SpeechSynthesisUtterance(text.trim()) as unknown as SpeechUtterancePort;
      const selected = preferredVoice(this.synthesis.getVoices(), language);
      utterance.lang = recognitionLocale(language);
      utterance.voice = selected.voice;
      utterance.rate = 1;
      utterance.onstart = callbacks.start ?? null;
      utterance.onend = callbacks.end ?? null;
      utterance.onerror = callbacks.error ?? null;
      this.synthesis.speak(utterance);
      return { ok: true, fallback: selected.fallback };
    } catch {
      return { ok: false, fallback: false };
    }
  }

  stop(): void {
    try { this.synthesis?.cancel(); } catch { /* Keep the chat usable if browser playback fails. */ }
  }
}

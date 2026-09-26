import type { Language } from '../i18n';

export interface RecognitionAlternative { transcript: string }
export interface RecognitionResult extends ArrayLike<RecognitionAlternative> { isFinal: boolean }
export interface RecognitionEvent { resultIndex: number; results: ArrayLike<RecognitionResult> }
export interface RecognitionErrorEvent { error: string }
export interface RecognitionPort {
  lang: string; interimResults: boolean; continuous: boolean;
  onstart: (() => void) | null; onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null; onend: (() => void) | null;
  start(): void; stop(): void; abort(): void;
}
export type RecognitionConstructor = new () => RecognitionPort;

export function recognitionLocale(language: Language): string {
  return language === 'mr' ? 'mr-IN' : language === 'hi' ? 'hi-IN' : 'en-IN';
}

export function getRecognitionConstructor(): RecognitionConstructor | null {
  if (typeof window === 'undefined') return null;
  const speechWindow = window as Window & { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
}

/** Browser-native recognition adapter. The application does not capture or retain audio. */
export class SpeechRecognitionService {
  constructor(private readonly create: () => RecognitionPort | null = () => {
    const Constructor = getRecognitionConstructor();
    return Constructor ? new Constructor() : null;
  }) {}

  createSession(language: Language): RecognitionPort | null {
    const recognition = this.create();
    if (!recognition) return null;
    recognition.lang = recognitionLocale(language);
    recognition.interimResults = true;
    recognition.continuous = false;
    return recognition;
  }
}

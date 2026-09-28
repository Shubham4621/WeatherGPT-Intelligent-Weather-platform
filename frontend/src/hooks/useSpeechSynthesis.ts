import { useCallback, useEffect, useRef, useState } from 'react';
import type { Language } from '../i18n';
import { SpeechSynthesisService } from '../services/speechSynthesis';

export function useSpeechSynthesis(service = new SpeechSynthesisService()) {
  const [speaking, setSpeaking] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [fallbackVoice, setFallbackVoice] = useState(false);
  const serviceRef = useRef(service);
  const stop = useCallback(() => { serviceRef.current.stop(); setSpeaking(false); }, []);
  const speak = useCallback((text: string, language: Language) => {
    setUnavailable(false); setFallbackVoice(false);
    const result = serviceRef.current.speak(text, language, {
      start: () => setSpeaking(true),
      end: () => setSpeaking(false),
      error: () => { setSpeaking(false); setUnavailable(true); },
      cancelled: () => setSpeaking(false),
    });
    if (!result.ok) { setSpeaking(false); setUnavailable(true); return; }
    setFallbackVoice(result.fallback);
  }, []);
  useEffect(() => () => serviceRef.current.stop(), []);
  return { speaking, unavailable, fallbackVoice, speak, stop };
}

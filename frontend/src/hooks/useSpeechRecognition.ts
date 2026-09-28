import { useCallback, useEffect, useRef, useState } from 'react';
import type { Language } from '../i18n';
import { SpeechRecognitionService, type RecognitionPort } from '../services/speechRecognition';

export type RecognitionStatus = 'idle' | 'requesting' | 'listening' | 'processing' | 'ready' | 'error';
export type RecognitionError = 'unsupported' | 'permission' | 'no_speech' | 'recognition';

function discardRecognition(recognition: RecognitionPort | null) {
  if (!recognition) return;
  recognition.onstart = null;
  recognition.onresult = null;
  recognition.onerror = null;
  recognition.onend = null;
  try { recognition.abort(); } catch { /* The browser may already have stopped the session. */ }
}

export function useSpeechRecognition(language: Language, service = new SpeechRecognitionService()) {
  const [status, setStatus] = useState<RecognitionStatus>('idle');
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [error, setError] = useState<RecognitionError | null>(null);
  const recognitionRef = useRef<RecognitionPort | null>(null);
  const finalRef = useRef('');
  const errorRef = useRef(false);

  const cancel = useCallback(() => {
    discardRecognition(recognitionRef.current);
    recognitionRef.current = null;
    finalRef.current = '';
    errorRef.current = false;
    setTranscript(''); setInterimTranscript(''); setError(null); setStatus('idle');
  }, []);

  const start = useCallback(() => {
    discardRecognition(recognitionRef.current);
    finalRef.current = ''; errorRef.current = false;
    setTranscript(''); setInterimTranscript(''); setError(null); setStatus('requesting');
    const recognition = service.createSession(language);
    if (!recognition) { setError('unsupported'); setStatus('error'); return; }
    recognitionRef.current = recognition;
    recognition.onstart = () => setStatus('listening');
    recognition.onresult = (event) => {
      let finalText = ''; let interimText = '';
      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results[index];
        const value = result?.[0]?.transcript ?? '';
        if (result?.isFinal) finalText += value;
        else interimText += value;
      }
      finalRef.current = finalText.trim();
      setTranscript(finalRef.current);
      setInterimTranscript(interimText.trim());
    };
    recognition.onerror = (event) => {
      errorRef.current = true;
      const reason: RecognitionError = event.error === 'not-allowed' || event.error === 'service-not-allowed' ? 'permission' : event.error === 'no-speech' ? 'no_speech' : 'recognition';
      setError(reason); setStatus('error');
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      setInterimTranscript('');
      if (errorRef.current) return;
      if (finalRef.current) { setTranscript(finalRef.current); setStatus('ready'); }
      else { setError('no_speech'); setStatus('error'); }
    };
    try { recognition.start(); } catch { setError('recognition'); setStatus('error'); recognitionRef.current = null; }
  }, [language, service]);

  const stop = useCallback(() => {
    if (!recognitionRef.current) return;
    setStatus('processing');
    try { recognitionRef.current.stop(); } catch { setError('recognition'); setStatus('error'); recognitionRef.current = null; }
  }, []);

  useEffect(() => () => { discardRecognition(recognitionRef.current); recognitionRef.current = null; }, []);
  return { status, transcript, interimTranscript, error, start, stop, cancel };
}

import { useEffect } from 'react';
import { Mic, MicOff, X } from 'lucide-react';
import { useLanguage, t } from '../../i18n';
import { useSpeechRecognition } from '../../hooks/useSpeechRecognition';

interface VoiceInputProps { disabled?: boolean; onTranscript: (transcript: string) => void }

export default function VoiceInput({ disabled = false, onTranscript }: VoiceInputProps) {
  const { language } = useLanguage();
  const voice = useSpeechRecognition(language);
  const active = voice.status === 'requesting' || voice.status === 'listening' || voice.status === 'processing';
  useEffect(() => { if (voice.status === 'ready' && voice.transcript) onTranscript(voice.transcript); }, [voice.status, voice.transcript, onTranscript]);
  const errorMessage = voice.error ? t(language, ({
    unsupported: 'Voice input is not supported in this browser. You can continue using text chat.',
    permission: 'Microphone permission was denied. Please allow microphone access in your browser settings.',
    no_speech: 'No speech detected. Please try again.',
    recognition: 'Voice recognition failed. Please try again or use text chat.',
  } as const)[voice.error]) : '';
  return <div className="relative flex shrink-0 items-center gap-2">
    <button type="button" disabled={disabled} onClick={active ? voice.stop : voice.start}
      aria-label={active ? t(language, 'Stop voice input') : t(language, 'Start voice input')}
      title={active ? t(language, 'Stop voice input') : t(language, 'Start voice input')}
      className={`flex h-11 w-11 items-center justify-center rounded-xl border transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-50 ${voice.status === 'listening' ? 'animate-pulse border-rose-300 bg-rose-50 text-rose-700' : 'border-line bg-white text-muted hover:bg-slate-50 hover:text-ink'}`}>
      {active ? <MicOff size={18} aria-hidden="true" /> : <Mic size={18} aria-hidden="true" />}
    </button>
    {voice.status === 'ready' && <button type="button" disabled={disabled} onClick={() => { voice.cancel(); onTranscript(''); }}
      aria-label={t(language, 'Discard voice transcript')} title={t(language, 'Discard voice transcript')}
      className="flex h-9 items-center gap-1 rounded-lg px-2 text-xs text-muted transition hover:bg-slate-100 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-50">
      <X size={14} aria-hidden="true" />{t(language, 'Discard')}
    </button>}
    <span role="status" aria-live="polite" className="sr-only">{active ? t(language, voice.status === 'processing' ? 'Processing transcript' : voice.status === 'requesting' ? 'Requesting microphone permission' : 'Listening…') : voice.status === 'ready' ? t(language, 'Transcript ready. Review and send when ready.') : ''}</span>
    {(active || errorMessage) && <span role={errorMessage ? 'alert' : undefined} aria-live="polite" className={`absolute bottom-full left-0 z-10 mb-2 w-max max-w-[min(18rem,80vw)] rounded-lg px-3 py-2 text-xs shadow-lg ${errorMessage ? 'bg-rose-50 text-rose-800 ring-1 ring-rose-200' : 'bg-slate-900 text-white'}`}>
      {errorMessage || <>{voice.status === 'requesting' ? t(language, 'Requesting microphone permission') : voice.status === 'processing' ? t(language, 'Processing transcript') : t(language, 'Listening…')}{voice.interimTranscript && <span className="block opacity-75">{voice.interimTranscript}</span>}</>}
    </span>}
  </div>;
}

import { Volume2, VolumeX } from 'lucide-react';
import { useLanguage, t } from '../../i18n';
import { useSpeechSynthesis } from '../../hooks/useSpeechSynthesis';

interface VoiceOutputProps { text: string }

export default function VoiceOutput({ text }: VoiceOutputProps) {
  const { language } = useLanguage();
  const voice = useSpeechSynthesis();
  return <div className="mt-2 flex flex-wrap items-center justify-end gap-2">
    <button type="button" onClick={() => voice.speaking ? voice.stop() : voice.speak(text, language)}
      aria-label={voice.speaking ? t(language, 'Stop speaking') : t(language, 'Read response aloud')}
      title={voice.speaking ? t(language, 'Stop speaking') : t(language, 'Read response aloud')}
      className="inline-flex h-9 items-center gap-2 rounded-lg px-3 text-xs font-medium text-brand transition hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand">
      {voice.speaking ? <><VolumeX size={16} aria-hidden="true" />{t(language, 'Speaking…')}</> : <><Volume2 size={16} aria-hidden="true" />{t(language, 'Read aloud')}</>}
    </button>
    {voice.unavailable && <span role="status" className="text-xs text-muted">{t(language, 'Voice playback is unavailable. You can still read the response normally.')}</span>}
    {!voice.unavailable && voice.fallbackVoice && <span role="status" className="text-xs text-muted">{t(language, 'Requested language voice unavailable; using a browser fallback voice.')}</span>}
  </div>;
}

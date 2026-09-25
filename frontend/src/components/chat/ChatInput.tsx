import { ArrowUp } from 'lucide-react';
import type { FormEvent } from 'react';
import { t, useLanguage } from '../../i18n';

interface ChatInputProps {
  value: string;
  loading: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
}

export default function ChatInput({ value, loading, onChange, onSend }: ChatInputProps) {
  const { language } = useLanguage();
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSend();
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 rounded-2xl border border-line bg-white p-2 shadow-sm focus-within:border-brand focus-within:ring-4 focus-within:ring-blue-100">
      <label htmlFor="chat-message" className="sr-only">{t(language, 'Ask WeatherGPT')}</label>
      <input id="chat-message" name="message" value={value} onChange={(event) => onChange(event.target.value)} disabled={loading} maxLength={1000} placeholder={t(language, 'Ask about current weather in a city…')} className="h-11 min-w-0 flex-1 bg-transparent px-3 text-sm text-ink outline-none placeholder:text-slate-400 disabled:opacity-60" />
      <button type="submit" disabled={loading || !value.trim()} aria-label={t(language, 'Send message')} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand text-white transition hover:bg-brand-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50">
        {loading ? <span className="loading-dot" aria-hidden="true" /> : <ArrowUp size={19} aria-hidden="true" />}
      </button>
    </form>
  );
}

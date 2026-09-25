import { useEffect, useRef, useState } from 'react';
import { ArrowDown, CloudSun, Sparkles } from 'lucide-react';
import ChatInput from './ChatInput';
import ChatMessage from './ChatMessage';
import TypingIndicator from './TypingIndicator';
import { ChatApiError, sendChatMessage } from '../../services/chatApi';
import type { ChatMessageRecord } from '../../types/chat';
import { t, useLanguage } from '../../i18n';

const SUGGESTIONS = [
  "What's the weather in Dhule?",
  'Will it rain tomorrow in Dhule?',
  'Should I carry an umbrella tomorrow in Dhule?',
  'How hot is it in Nashik?',
  "What's the humidity in Mumbai?",
  'Tell me the current weather in Pune.',
];

export default function ChatPanel() {
  const { language } = useLanguage();
  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nextId = useRef(1);
  const endOfMessages = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endOfMessages.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }, [messages, loading, error]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || loading) return;
    setInput('');
    setError(null);
    setMessages((previous) => [...previous, { id: nextId.current++, role: 'user', content }]);
    setLoading(true);
    try {
      const response = await sendChatMessage(content, language);
      setMessages((previous) => [...previous, { id: nextId.current++, role: 'assistant', content: response.message, response }]);
    } catch (requestError) {
      const message = requestError instanceof ChatApiError ? requestError.message : 'WeatherGPT could not complete that request. Please try again.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main id="main" className="mx-auto flex min-h-[calc(100vh-73px)] max-w-5xl flex-col px-4 pb-6 pt-6 sm:px-8 sm:pt-10">
      <div className="mb-5">
        <p className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-brand"><Sparkles size={14} aria-hidden="true" /> {t(language, 'Current weather assistant')}</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-ink">{t(language, 'Ask WeatherGPT')}</h1>
        <p className="mt-2 text-sm leading-6 text-muted">Ask about current conditions or the provider forecast for a city.</p>
      </div>

      <section aria-label="WeatherGPT conversation" className="flex min-h-[60vh] flex-1 flex-col overflow-hidden rounded-3xl border border-line bg-slate-50/70 shadow-card">
        <div className="flex items-center gap-3 border-b border-line bg-white px-5 py-4 sm:px-6">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand text-white"><CloudSun size={21} aria-hidden="true" /></span>
          <div><p className="font-semibold text-ink">{t(language, 'WeatherGPT assistant')}</p><p className="text-xs text-muted">{t(language, 'Grounded in current provider data')} · {language === 'mr' ? 'मराठी' : language === 'hi' ? 'हिन्दी' : 'English'}</p></div>
          {messages.length > 0 && <button type="button" onClick={() => { setMessages([]); setError(null); }} disabled={loading} className="ml-auto rounded-lg px-3 py-2 text-xs font-medium text-muted hover:bg-slate-100 hover:text-ink disabled:opacity-50">Clear chat</button>}
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-4 sm:p-6" aria-live="polite" aria-relevant="additions text">
          {messages.length === 0 && (
            <div className="mx-auto flex max-w-2xl flex-col items-center py-7 text-center sm:py-12">
              <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-100 text-brand"><CloudSun size={29} strokeWidth={1.5} aria-hidden="true" /></span>
              <h2 className="mt-4 text-xl font-semibold text-ink">What would you like to know?</h2>
              <p className="mt-2 max-w-md text-sm leading-6 text-muted">I can look up current weather conditions and measurements for a city.</p>
              <div className="mt-6 grid w-full gap-2 sm:grid-cols-2">
                {SUGGESTIONS.map((suggestion) => <button key={suggestion} type="button" onClick={() => void send(suggestion)} disabled={loading} className="group flex min-h-12 items-center justify-between gap-3 rounded-xl border border-line bg-white px-4 py-3 text-left text-sm text-ink transition hover:border-blue-200 hover:bg-blue-50/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-50"><span>{suggestion}</span><ArrowDown className="-rotate-45 text-slate-400 transition group-hover:text-brand" size={15} aria-hidden="true" /></button>)}
              </div>
            </div>
          )}
          {messages.map((message) => <ChatMessage key={message.id} message={message} />)}
          {loading && <TypingIndicator />}
          {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
          <div ref={endOfMessages} />
        </div>

        <div className="border-t border-line bg-white p-3 sm:p-5">
          <ChatInput value={input} loading={loading} onChange={setInput} onSend={() => void send(input)} />
          <p className="mt-2 text-center text-[11px] text-muted">Current weather and forecasts use real provider data.</p>
        </div>
      </section>
    </main>
  );
}
